"""Score the atlas's lit globe against NASA EPIC full-disc photographs (register A1).

EPIC (DSCOVR, Earth-Sun L1) photographs the whole sunlit disc every one to two hours and
publishes, with each frame, where the spacecraft and the Sun were. The app can stand its camera
at the same place and instant (ATLAS.refView). This script puts each pair in one frame - a disc
of unit radius with north up - and prints the numbers that decide whether the render reads as
the photograph: brightness and contrast, the limb, clear-ocean and desert colour, cloud cover,
sun glint.

What it can and cannot say. The atlas holds a typical year; EPIC shows one day's weather. So
WHERE the clouds are is not scored, only how much there is and how bright. Colour is compared in
display values (sRGB 0-255), as a viewer sees both.

    ./venv/bin/python Research/modeling/epic_compare.py --tag r0            # score renders scratchpad/epic_r0_*.jpg
    ./venv/bin/python Research/modeling/epic_compare.py --selftest
    ./venv/bin/python Research/modeling/epic_compare.py --tag r1 --json     # last line is the summary for audit_all

EPIC imagery is public domain (NASA). The frames live in reference/epic/ (gitignored); the list
and geometry are in reference/epic/frames.json, rebuilt by --fetch.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REF = os.path.join(ROOT, "reference", "epic")
SHOTS = os.path.join(ROOT, "scratchpad")
FIG = os.path.join(ROOT, "Research", "figures", "epic")
R_KM = 6371.0088
N = 900                    # the common frame is N x N with the limb at radius RD
RD = 400.0
Image.MAX_IMAGE_PIXELS = None

# The frames: (date, target sub-spacecraft longitudes). Two per season, four longitudes.
WANT = [("2025-03-20", [20, -80]), ("2025-06-21", [100, -160]), ("2024-09-22", [100, -160]), ("2025-12-21", [20, -80])]


# ------------------------------------------------------------------------------ geometry

def unit(lon, lat):
    lo, la = np.radians(lon), np.radians(lat)
    return np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def disc_geometry(lon0, lat0, dist):
    """lon, lat, mu (cosine of the view zenith) and rho (radius, limb = 1) for the common frame.
    Perspective from `dist` Earth radii above (lon0, lat0), north up - the app's camera.unproject."""
    yy, xx = np.mgrid[0:N, 0:N]
    x = (xx - (N - 1) / 2) / RD
    y = ((N - 1) / 2 - yy) / RD
    rho = np.hypot(x, y)
    c = unit(lon0, lat0)
    l, p = np.radians(lon0), np.radians(lat0)
    right = np.array([-np.sin(l), np.cos(l), 0.0])
    up = np.array([-np.sin(p) * np.cos(l), -np.sin(p) * np.sin(l), np.cos(p)])
    ta = np.tan(np.arcsin(1 / dist))                       # the limb's angle from the axis
    d = (-c)[None, None, :] + (x * ta)[..., None] * right + (y * ta)[..., None] * up
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    o = c * dist
    b = d @ o
    disc = b * b - (dist * dist - 1)
    hit = (disc > 0) & (rho < 1)
    t = -b - np.sqrt(np.where(hit, disc, 0))
    P = o + t[..., None] * d
    lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    lat = np.degrees(np.arcsin(np.clip(P[..., 2], -1, 1)))
    mu = np.where(hit, -(P * d).sum(2), 0)
    return dict(lon=lon, lat=lat, mu=mu, rho=rho, hit=hit, P=P, d=d)


def to_common(img, cx, cy, r):
    """Resample an image whose disc is centred (cx, cy) with radius r px into the common frame."""
    s = r / RD
    w, h = img.size
    box = (cx - (N / 2) * s, cy - (N / 2) * s, cx + (N / 2) * s, cy + (N / 2) * s)
    return np.asarray(img.transform((N, N), Image.EXTENT, box, Image.BICUBIC), dtype=np.float32)


def fit_disc(a):
    """Centre and radius of the lit disc from its area and centroid (EPIC sees a full disc)."""
    m = a.mean(2) > 12
    ys, xs = np.nonzero(m)
    return xs.mean(), ys.mean(), float(np.sqrt(m.sum() / np.pi))


def sub_solar(fr):
    """Sub-solar lon/lat from EPIC's own J2000 vectors. The sub-spacecraft longitude fixes the
    Earth's rotation angle, so no sidereal-time formula of ours is involved: an independent witness.

    EPIC carries TWO times per frame: `date`, and the one in the image name, about five minutes
    later. The centroid longitude belongs to the image-name time (measured: with `date` the app's
    Sun sat 1.1-1.2 degrees east of this value in every frame, which is five minutes of rotation;
    with the image-name time the two agree to under 0.1). `t` in frames.json is the image-name time."""
    dv = np.array([fr["dscovr"][k] for k in "xyz"]); sv = np.array([fr["sun"][k] for k in "xyz"])
    ra_d = np.degrees(np.arctan2(dv[1], dv[0])); ra_s = np.degrees(np.arctan2(sv[1], sv[0]))
    lon = (fr["lon"] + (ra_s - ra_d) + 540) % 360 - 180
    lat = np.degrees(np.arcsin(sv[2] / np.linalg.norm(sv)))
    # J2000 -> equator of date: precession moves declination by n cos(RA), n = 20.04 arcsec a year.
    # (Its effect on right ascension is common to both vectors and cancels in the difference above.)
    years = float(fr.get("date", "2000")[:4]) - 2000.0
    lat += 20.04 / 3600 * years * np.cos(np.radians(ra_s))
    return lon, lat


_fields = {}


def sample_field(name, lon, lat):
    """Nearest sample of one of the app's own shipped rasters (the audit reads what the app reads)."""
    if name not in _fields:
        im = Image.open(os.path.join(ROOT, "web", "fields", name)).convert("L")
        im = im.resize((2880, 1440), Image.BOX)
        _fields[name] = np.asarray(im, dtype=np.float32) / 255
    f = _fields[name]
    h, w = f.shape
    col = np.clip(((lon + 180) / 360 * w).astype(int), 0, w - 1)
    row = np.clip(((90 - lat) / 180 * h).astype(int), 0, h - 1)
    return f[row, col]


# ------------------------------------------------------------------------------- measures

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def measures(a, g, water, sun):
    """Everything scored for one image `a` (N x N x 3, display values) in geometry `g`."""
    lum = a @ LUMA
    hit, mu, rho = g["hit"], g["mu"], g["rho"]
    cs = g["P"] @ sun                                          # cosine of the solar zenith
    white = (a.min(2) > 150) & ((a.max(2) - a.min(2)) < 45)   # cloud, snow or ice as a viewer sees it
    core = hit & (mu > 0.35)
    out = {}
    out["mean_lum"] = float(lum[hit].mean())
    out["p05"], out["p50"], out["p95"] = [float(v) for v in np.percentile(lum[core], [5, 50, 95])]
    out["contrast"] = float(lum[core].std())
    out["mean_rgb"] = [float(v) for v in a[hit].mean(0)]
    out["white_frac"] = float(white[core].mean())
    out["bright_frac"] = float((lum[core] > 120).mean())
    # limb: brightness and blueness against the cosine of the view angle
    prof, blue = [], []
    for lo, hi in [(0.8, 1.0), (0.6, 0.8), (0.4, 0.6), (0.2, 0.4), (0.1, 0.2), (0.0, 0.1)]:
        m = hit & (mu > lo) & (mu <= hi)
        prof.append(float(lum[m].mean())); rgb = a[m].mean(0); blue.append(float(rgb[2] / max(1.0, rgb[0])))
    out["limb_lum"] = prof
    # the same by channel, from the centre to a cosine of 0.2: what disc_err scores
    dp = []
    for lo, hi in ((0.8, 1.0), (0.6, 0.8), (0.45, 0.6), (0.3, 0.45), (0.2, 0.3)):
        mm = g["hit"] & (g["mu"] > lo) & (g["mu"] <= hi)
        dp.append([float(v) for v in a[mm].mean(0)])
    out["disc_rgb"] = dp
    # The outermost bin is two pixels wide and is decided by how the disc radius was fitted, not by
    # the limb, so the score uses the next one in: cos 0.1-0.2 against the centre.
    out["limb_ratio"] = prof[-2] / prof[0]
    out["limb_blue"] = blue
    out["halo"] = [float(lum[(rho > lo) & (rho <= hi)].mean()) for lo, hi in [(1.004, 1.012), (1.012, 1.03), (1.03, 1.06)]]
    # clear ocean: the darkest fifth of well-lit water away from the glint
    v = unit(*g["sub"])
    hvec = (sun + v) / np.linalg.norm(sun + v)                 # the specular point on a sphere
    ang = np.degrees(np.arccos(np.clip(g["P"] @ hvec, -1, 1)))
    w = hit & (water > 0.98) & (mu > 0.5) & (cs > 0.5) & (ang > 25) & ~white
    if w.sum() > 500:
        k = lum[w] <= np.percentile(lum[w], 20)
        out["ocean_rgb"] = [float(x) for x in a[w][k].mean(0)]
    # the glint: clear water at the specular point against clear water 20-30 degrees away
    wc = hit & (water > 0.98) & ~white
    near, far = wc & (ang < 6), wc & (ang > 20) & (ang < 30)
    out["glint_water_px"] = int(near.sum())
    if near.sum() > 200 and far.sum() > 500:
        out["glint_ratio"] = float(np.percentile(lum[near], 30) / max(1.0, np.percentile(lum[far], 30)))
    # named clear-sky ground: the median of non-white pixels in a box, where it is in view
    L, B = g["lon"], g["lat"]
    for name, (w0, e0, s0, n0) in {"sahara": (0, 28, 17, 28), "arabia": (42, 54, 18, 26), "australia": (122, 138, -29, -21),
                                   "amazon": (-68, -55, -8, 0), "congo": (15, 27, -3, 3), "greenland": (-48, -32, 68, 78)}.items():
        m = hit & (mu > 0.45) & (cs > 0.45) & (L > w0) & (L < e0) & (B > s0) & (B < n0)
        if name != "greenland":
            m &= ~white
        if m.sum() > 400:
            out["land_" + name] = [float(x) for x in np.median(a[m], axis=0)]
    return out


def registration(a, g, water):
    """Does the photograph's coastline sit where the geometry says? Correlation of 'redder than
    blue' with our land mask over cloud-free pixels, at the nominal placement and over small shifts."""
    lum = a @ LUMA
    landness = a[..., 0] - a[..., 2]
    ok = g["hit"] & (g["mu"] > 0.4) & (lum < 130)
    land = 1 - water
    best = (-1, 0, 0)
    for dy in range(-8, 9, 2):
        for dx in range(-8, 9, 2):
            s = np.roll(np.roll(landness, dy, 0), dx, 1)
            c = np.corrcoef(s[ok], land[ok])[0, 1]
            if c > best[0]:
                best = (float(c), dx, dy)
    nominal = float(np.corrcoef(landness[ok], land[ok])[0, 1])
    return nominal, best


# ---------------------------------------------------------------------------------- driver

def load_frames():
    with open(os.path.join(REF, "frames.json")) as fh:
        return json.load(fh)


def fetch():
    os.makedirs(REF, exist_ok=True)
    pick = []
    for date, lons in WANT:
        meta = json.loads(subprocess.run(["curl", "-s", "-m", "60", f"https://epic.gsfc.nasa.gov/api/natural/date/{date}"],
                                         capture_output=True, text=True, check=True).stdout)
        if not meta:
            raise SystemExit(f"EPIC has no natural-colour frames for {date}; choose another date in WANT")
        for tl in lons:
            b = min(meta, key=lambda x: abs(((x["centroid_coordinates"]["lon"] - tl + 540) % 360) - 180))
            y, m, d = b["date"][:4], b["date"][5:7], b["date"][8:10]
            png = os.path.join(REF, b["image"] + ".png")
            if not os.path.exists(png):
                subprocess.run(["curl", "-s", "-m", "180", "-o", png,
                                f"https://epic.gsfc.nasa.gov/archive/natural/{y}/{m}/{d}/png/{b['image']}.png"], check=True)
            a = np.asarray(Image.open(png).convert("RGB"), dtype=np.float32)
            cx, cy, r = fit_disc(a)
            dist = float(np.linalg.norm([b["dscovr_j2000_position"][k] for k in "xyz"]) / R_KM)
            nm = b["image"][8:]
            t = f"{nm[:4]}-{nm[4:6]}-{nm[6:8]}T{nm[8:10]}:{nm[10:12]}:{nm[12:14]}Z"
            pick.append(dict(image=b["image"], date=b["date"], t=t, lat=b["centroid_coordinates"]["lat"], lon=b["centroid_coordinates"]["lon"],
                             dscovr=b["dscovr_j2000_position"], sun=b["sun_j2000_position"], cx=cx, cy=cy, r=r, dist=dist, discFrac=2 * r / a.shape[0]))
    with open(os.path.join(REF, "frames.json"), "w") as fh:
        json.dump(pick, fh, indent=1)
    print(f"{len(pick)} frames in {REF}")
    # what the page needs to stand its camera in the same place (web/js/refshots.js reads this)
    with open(os.path.join(ROOT, "web", "dev", "epic_frames.json"), "w") as fh:
        json.dump([dict(n=p["image"][8:], t=p["t"], lon=p["lon"], lat=p["lat"], dist=round(p["dist"], 2), f=round(p["discFrac"], 4)) for p in pick], fh, indent=1)


def run(tag, as_json=False, figures=True):
    frames = load_frames()
    rows = []
    for fr in frames:
        n = fr["image"][8:]
        shot = os.path.join(SHOTS, f"epic_{tag}_{n}.jpg")
        if not os.path.exists(shot):
            shot = shot[:-4] + ".png"
        if not os.path.exists(shot):
            raise SystemExit(f"no render for {n} with tag {tag!r} in {SHOTS}. In the page (1024 x 1024 window): "
                             f"await (await import('/js/refshots.js')).renderEpic('{tag}')")
        epic = Image.open(os.path.join(REF, fr["image"] + ".png")).convert("RGB")
        mine = Image.open(shot).convert("RGB")
        g = disc_geometry(fr["lon"], fr["lat"], fr["dist"])
        g["sub"] = (fr["lon"], fr["lat"])
        water = np.where(g["hit"], sample_field("water.webp", g["lon"], g["lat"]), 0)
        slon, slat = sub_solar(fr)
        sun = unit(slon, slat)
        A = to_common(epic, fr["cx"], fr["cy"], fr["r"])
        B = to_common(mine, mine.width / 2, mine.height / 2, fr["discFrac"] * mine.height / 2)
        reg_e, reg_m = registration(A, g, water), registration(B, g, water)
        me, mm = measures(A, g, water, sun), measures(B, g, water, sun)
        phase = float(np.degrees(np.arccos(np.clip(sun @ unit(fr["lon"], fr["lat"]), -1, 1))))
        rows.append(dict(frame=n, date=fr["date"], sub=[fr["lon"], fr["lat"]], sun=[float(slon), float(slat)], phase=phase,
                         reg_epic=reg_e, reg_atlas=reg_m, epic=me, atlas=mm))
        if figures:
            os.makedirs(FIG, exist_ok=True)
            pair = np.concatenate([A, B], axis=1).clip(0, 255).astype(np.uint8)
            Image.fromarray(pair).save(os.path.join(FIG, f"{n}_{tag}.jpg"), quality=88)
    summary = summarise(rows)
    with open(os.path.join(HERE, f"epic_scores_{tag}.json"), "w") as fh:
        json.dump(dict(tag=tag, summary=summary, frames=rows), fh, indent=1)
    if not as_json:
        report(rows, summary, tag)
    print(json.dumps(summary))
    return summary


def _mean(rows, side, key, idx=None):
    v = [r[side][key] if idx is None else r[side][key][idx] for r in rows if key in r[side]]
    return float(np.mean(v)) if v else float("nan")


def summarise(rows):
    """The numbers the ratchet holds. All are |atlas - EPIC| style distances: lower is better."""
    s = {}
    s["frames"] = len(rows)
    s["lum_err"] = round(float(np.mean([abs(r["atlas"]["mean_lum"] - r["epic"]["mean_lum"]) for r in rows])), 2)
    s["contrast_err"] = round(float(np.mean([abs(r["atlas"]["contrast"] - r["epic"]["contrast"]) for r in rows])), 2)
    s["white_err"] = round(float(np.mean([abs(r["atlas"]["white_frac"] - r["epic"]["white_frac"]) for r in rows])), 3)
    # The disc from its centre to a view cosine of 0.2, in five rings, each channel: mean |atlas - EPIC|.
    # limb_err below scores only the ratio of the outermost ring to the centre, which a disc that is
    # uniformly too dim toward the edge can pass (it did, in the verify round: see MODEL-GAPS A1).
    s["disc_err"] = round(float(np.mean([np.abs(np.array(r["atlas"]["disc_rgb"]) - np.array(r["epic"]["disc_rgb"])).mean() for r in rows])), 2)
    s["limb_err"] = round(float(np.mean([abs(r["atlas"]["limb_ratio"] - r["epic"]["limb_ratio"]) for r in rows])), 3)
    oc = [np.linalg.norm(np.array(r["atlas"]["ocean_rgb"]) - np.array(r["epic"]["ocean_rgb"])) for r in rows if "ocean_rgb" in r["atlas"] and "ocean_rgb" in r["epic"]]
    s["ocean_rgb_err"] = round(float(np.mean(oc)), 1)
    ld = [np.linalg.norm(np.array(r["atlas"][k]) - np.array(r["epic"][k])) for r in rows for k in r["epic"] if k.startswith("land_") and k in r["atlas"]]
    s["land_rgb_err"] = round(float(np.mean(ld)), 1)
    s["halo_err"] = round(float(np.mean([abs(r["atlas"]["halo"][1] - r["epic"]["halo"][1]) for r in rows])), 2)
    gl = [abs(r["atlas"]["glint_ratio"] - r["epic"]["glint_ratio"]) for r in rows if "glint_ratio" in r["atlas"] and "glint_ratio" in r["epic"]]
    s["glint_err"] = round(float(np.mean(gl)), 2) if gl else None
    # the harness's own validity: how far the photograph's coast sits from where the geometry puts it
    s["epic_shift_px"] = max(max(abs(r["reg_epic"][1][1]), abs(r["reg_epic"][1][2])) for r in rows)
    return s


def report(rows, s, tag):
    f3 = lambda v: "(" + ",".join(f"{x:3.0f}" for x in v) + ")"
    print(f"\nEPIC against the atlas, render tag {tag!r}. Display values 0-255; EPIC first, atlas second.\n")
    print(f"{'frame':15} {'phase':>5} {'reg E/A':>11} {'mean lum':>11} {'p05':>7} {'p50':>9} {'p95':>9} {'contrast':>9} {'white %':>9} {'limb/ctr':>10} {'halo':>9}")
    for r in rows:
        e, a = r["epic"], r["atlas"]
        print(f"{r['frame']:15} {r['phase']:5.1f} {r['reg_epic'][0]:5.2f}/{r['reg_atlas'][0]:4.2f} "
              f"{e['mean_lum']:5.0f}/{a['mean_lum']:<5.0f} {e['p05']:3.0f}/{a['p05']:<3.0f} {e['p50']:4.0f}/{a['p50']:<4.0f} {e['p95']:4.0f}/{a['p95']:<4.0f} "
              f"{e['contrast']:4.0f}/{a['contrast']:<4.0f} {e['white_frac']*100:4.0f}/{a['white_frac']*100:<4.0f} {e['limb_ratio']:4.2f}/{a['limb_ratio']:<4.2f} {e['halo'][1]:4.1f}/{a['halo'][1]:<4.1f}")
    print("\nlimb profile, mean luminance by cos(view zenith) 1.0-0.8 ... 0.1-0.0, all frames")
    for side in ("epic", "atlas"):
        print(f"  {side:6}", " ".join(f"{np.mean([r[side]['limb_lum'][i] for r in rows]):6.1f}" for i in range(6)),
              "  blue/red", " ".join(f"{np.mean([r[side]['limb_blue'][i] for r in rows]):5.2f}" for i in range(6)))
    print("\nclear ocean (darkest fifth of lit water), clear ground (median of non-white pixels), glint ratio")
    for r in rows:
        e, a = r["epic"], r["atlas"]
        bits = [f"ocean {f3(e['ocean_rgb'])} {f3(a['ocean_rgb'])}"] if "ocean_rgb" in e and "ocean_rgb" in a else []
        bits += [f"{k[5:]} {f3(e[k])} {f3(a[k])}" for k in e if k.startswith("land_") and k in a]
        if "glint_ratio" in e and "glint_ratio" in a:
            bits.append(f"glint {e['glint_ratio']:.2f} / {a['glint_ratio']:.2f}")
        print(f"  {r['frame']}  " + "  ·  ".join(bits))
    print("\nsub-solar point from EPIC's own vectors (the app's ephemeris is checked against these in audit_all)")
    for r in rows:
        print(f"  {r['frame']}  lon {r['sun'][0]:9.3f}  lat {r['sun'][1]:8.3f}   best coast registration of the photograph: shift {r['reg_epic'][1][1:]} px, r={r['reg_epic'][1][0]:.2f}")
    print()


def selftest():
    """Known answers: the centre of the disc is the sub-point, the limb is at rho=1, and a synthetic
    'photograph' built from our own water mask registers at zero shift with correlation near 1."""
    g = disc_geometry(30.0, -12.0, 230.0)
    c = (N - 1) // 2
    assert abs(g["lon"][c, c] - 30.0) < 0.3 and abs(g["lat"][c, c] + 12.0) < 0.3, (g["lon"][c, c], g["lat"][c, c])
    assert g["hit"][c, c + int(RD) - 3] and not g["hit"][c, c + int(RD) + 3]
    assert g["mu"][c, c] > 0.999 and g["mu"][c, c + int(RD) - 2] < 0.15
    north = g["lat"][c - 200, c] > g["lat"][c + 200, c]
    east = ((g["lon"][c, c + 200] - g["lon"][c, c - 200] + 540) % 360 - 180) > 0
    assert north and east, "north must be up and east to the right"
    water = np.where(g["hit"], sample_field("water.webp", g["lon"], g["lat"]), 0)
    fake = np.zeros((N, N, 3), dtype=np.float32)
    fake[..., 0] = 90 * (1 - water); fake[..., 2] = 90 * water; fake[..., 1] = 40
    fake[~g["hit"]] = 0
    nominal, best = registration(fake, g, water)
    assert nominal > 0.95 and best[1] == 0 and best[2] == 0, (nominal, best)
    shifted = np.roll(fake, 6, axis=1)
    _, b2 = registration(shifted, g, water)
    assert b2[1] == -6 and b2[2] == 0, b2
    # the sub-solar point at the March 2025 equinox instant is on the equator
    fr = dict(dscovr=dict(x=1.0, y=0.0, z=0.0), sun=dict(x=1.0, y=0.0, z=0.0), lon=12.0)
    lo, la = sub_solar(fr)
    assert abs(lo - 12.0) < 1e-9 and abs(la) < 1e-9
    print("epic_compare selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r0")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.fetch:
        fetch()
    else:
        run(args.tag, as_json=args.json, figures=not args.no_figures)
