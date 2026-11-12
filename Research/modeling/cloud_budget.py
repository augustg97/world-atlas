"""Where the cloud's light is, and how it is seen: the shader's cloud laws against three witnesses (register B1).

Three questions the other cloud audits cannot answer, each asked of data the atlas is not made from.

  default    BY KIND AND LATITUDE. ISCCP's cloud light in each 10-degree band of open water, split as the
             build splits it (sheets, broken low cloud, everything else), beside what the shader's sheet law
             draws of the sheet light. Reads data/_cache/isccp_2007_2016.npz (fields_climate.py atmo).

  --survey   IS THE SOUTHERN OCEAN SHORT OF LIGHT, SEEN STRAIGHT DOWN? Twelve places at 42-55 S, four summer
             days each, VIIRS true colour at 4 km (NASA GIBS, public domain; --fetch, 6 MB into
             reference/gibs_clouds/so_survey). Mean reflectance of a scene, less ISCCP's other cloud there and
             the sea, is the room there is for sheet light; the shader's law (sheetLight, read out of the
             shader) is scored against it. Found in the tenth round: ISCCP has 0.136 of sheet light there,
             VIIRS has room for 0.065, and the law draws 0.070. The atlas was NOT short of light there; it drew
             the light as a veil.

  --angle T  HOW CLOUD BRIGHTENS TOWARD THE LIMB. NASA EPIC looks from the Sun's side, so across one frame the
             view's cosine and the Sun's fall together from the centre of the disc to its edge. The light sent
             back by open water (display values through the atlas's own transform, over the Sun's cosine) is
             binned by that cosine in seven latitude bands, EPIC and the atlas's render with tag T, eight
             frames pooled. Found in the tenth round: over the storm belts EPIC is level to a cosine of 0.5;
             over the tropics it doubles. Layered cloud does not close its gaps at a slant; heaped cloud does.

  --json     the numbers audit_all.py holds (needs the survey and renders with tag `cur`)
  --selftest

    ./venv/bin/python Research/modeling/cloud_budget.py --survey --fetch
    ./venv/bin/python Research/modeling/cloud_budget.py --angle cur
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cloud_texture as CT      # noqa: E402  (the VIIRS reflectance table and the scene box)
import shader_model as S        # noqa: E402

ISCCP = os.path.join(ROOT, "data", "_cache", "isccp_2007_2016.npz")
SURVEY = os.path.join(CT.REF, "so_survey")
PLACES = [(0, -52), (45, -52), (90, -52), (135, -52), (180, -55), (-135, -55), (-100, -55), (-45, -52),
          (0, -42), (90, -42), (180, -42), (-100, -42)]
DAYS = ["2023-12-20", "2024-01-10", "2024-12-28", "2025-01-20"]       # two summers, none a day the texture audit uses
SEA = 0.012                      # clear deep water in VIIRS's corrected reflectance (the darkest tenth of the trade scenes: 0.013-0.020)
BANDS = [(-65, -45), (-45, -25), (-25, -8), (-8, 8), (8, 25), (25, 45), (45, 65)]
BINS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


# ------------------------------------------------------------------ the shader's sheet law, read from its source

def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def sheet_law(path=S.SHADER):
    """(DECK_R, ramp lo, ramp hi, deck lo, deck hi) from sheetLight() and deckShare() in the shader."""
    src = open(path).read()
    r = re.search(r"const float DECK_R = ([\d.]+)", src)
    a = re.search(r"float sheetLight\(float amount\) \{ return DECK_R \* amount \* smoothstep\(([\d.]+), ([\d.]+), amount\); \}", src)
    d = re.search(r"float deckShare\(float amount\) \{ return smoothstep\(([\d.]+), ([\d.]+), amount\); \}", src)
    if not (r and a and d):
        raise SystemExit("cloud_budget: sheetLight / deckShare / DECK_R not found in the shader as written here; this copy has drifted")
    return float(r.group(1)), float(a.group(1)), float(a.group(2)), float(d.group(1)), float(d.group(2))


def sheet_light(share, law):
    """Light of sheet cloud averaged over all the sky, as the shader draws it (deck and weather together)."""
    return law[0] * share * smoothstep(law[1], law[2], share)


def deck_share(share, law):
    return smoothstep(law[3], law[4], share)


# ------------------------------------------------------------------------------------------- by kind and latitude

def isccp():
    if not os.path.exists(ISCCP):
        raise SystemExit(f"missing {ISCCP}; run build/fields_climate.py atmo")
    return dict(np.load(ISCCP))


def box(a, lon, lat, r=8):
    """A 17-degree box of a (180, 360) field about lon, lat, widened in longitude as a scene is."""
    i = int(90 - lat); hw = int(r / np.cos(np.radians(lat)))
    j = np.arange(int(lon + 180) - hw, int(lon + 180) + hw + 1) % 360
    return a[i - r:i + r + 1][:, j]


def by_band():
    d = isccp(); law = sheet_law()
    w = np.asarray(Image.open(os.path.join(ROOT, "web", "fields", "water.webp")).convert("L").resize((360, 180), Image.BOX), dtype=float) / 255
    lat = 90 - (np.arange(180) + 0.5)
    for mo, name in ((11, "December"), (2, "March"), (5, "June"), (8, "September")):
        print(f"\n{name}, open water. share of sky: all cloud, sheets, broken low | ISCCP light: the rest, sheets, broken low, ALL | sheet light drawn: as weather, as deck (of ISCCP's)")
        for b in range(-70, 70, 10):
            m = (lat >= b) & (lat < b + 10); ww = w[m] > 0.98
            f = lambda k: d[k][mo][m][ww].mean()
            sh = d["deck"][mo][m][ww]; sl = sheet_light(sh, law); dk = deck_share(sh, law)
            print(f"  {b:4d}..{b+10:<4d}  {f('total'):.2f} {f('deck'):.2f} {f('cu'):.2f} | {f('light'):.3f} {f('deck_light'):.3f} {f('cu_light'):.3f} {f('light') + f('deck_light') + f('cu_light'):.3f} |"
                  f" {(sl * (1 - dk)).mean():.3f} {(sl * dk).mean():.3f}  ({sl.mean() / max(f('deck_light'), 1e-6):.2f})")


# ------------------------------------------------------------------------- the Southern Ocean seen straight down

def survey_fetch():
    os.makedirs(SURVEY, exist_ok=True)
    for lon, lat in PLACES:
        b = CT.bbox(lon, lat)
        for day in DAYS:
            out = os.path.join(SURVEY, f"so_{lon}_{lat}_{day}.jpg")
            if os.path.exists(out):
                continue
            url = ("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
                   f"&LAYERS={CT.LAYER}&CRS=EPSG:4326&BBOX={b[0]:.4f},{b[1]:.4f},{b[2]:.4f},{b[3]:.4f}&WIDTH=512&HEIGHT=512&FORMAT=image/jpeg&TIME={day}")
            r = subprocess.run(["curl", "-s", "-f", "-m", "120", "--retry", "3", "-o", out + ".part", url])
            if r.returncode == 0:
                os.replace(out + ".part", out)
            print(("ok   " if r.returncode == 0 else "FAIL ") + os.path.basename(out))


def scene_mean(path):
    """Mean reflectance of a VIIRS scene; the black of a gap between swaths is not sea and is left out."""
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    lum = (np.interp(im, CT._GY, CT._GX) / 255.0) @ CT.LUMA
    return float(lum[im.sum(-1) > 0].mean())


def survey(verbose=True):
    d = isccp(); law = sheet_law()
    rows = []
    for lon, lat in PLACES:
        ms = []
        for day in DAYS:
            p = os.path.join(SURVEY, f"so_{lon}_{lat}_{day}.jpg")
            if not os.path.exists(p):
                raise SystemExit(f"missing {p}; run cloud_budget.py --survey --fetch")
            ms.append(scene_mean(p))
        f = lambda k: 0.5 * (box(d[k][11], lon, lat).mean() + box(d[k][0], lon, lat).mean())          # December and January
        sh = 0.5 * (box(d["deck"][11], lon, lat) + box(d["deck"][0], lon, lat))
        want = float(np.mean(ms)) - f("light") - f("cu_light") - SEA
        rows.append(dict(lon=lon, lat=lat, viirs=float(np.mean(ms)), days=ms, share=float(sh.mean()), isccp_sheet=float(f("deck_light")),
                         room=want, drawn=float(sheet_light(sh, law).mean()), rest=float(f("light")), cu=float(f("cu_light"))))
    if verbose:
        print("the Southern Ocean in summer, seen straight down: VIIRS mean reflectance (four days), ISCCP's cloud light by kind (December, January),")
        print("the room VIIRS leaves for sheet light (its mean less ISCCP's other cloud and the sea), and what the shader's sheet law draws")
        print("  place       VIIRS  (the days)              | ISCCP rest  low  sheet (share) | room   drawn")
        for r in rows:
            print(f"  {r['lon']:5d},{r['lat']:4d}  {r['viirs']:.3f}  ({' '.join('%.2f' % m for m in r['days'])})  |  {r['rest']:.3f} {r['cu']:.3f} {r['isccp_sheet']:.3f} ({r['share']:.2f})  | {r['room']:+.3f}  {r['drawn']:.3f}")
        for nm, k in (("52-55 S", [r for r in rows if r["lat"] < -50]), ("42 S", [r for r in rows if r["lat"] > -50]), ("all twelve", rows)):
            g = lambda key: float(np.mean([r[key] for r in k]))
            print(f"  {nm:10}: VIIRS {g('viirs'):.3f};  ISCCP all cloud {g('rest') + g('cu') + g('isccp_sheet'):.3f}, of it sheet {g('isccp_sheet'):.3f};  room for sheet {g('room'):.3f};  drawn {g('drawn'):.3f}")
    room = float(np.mean([r["room"] for r in rows])); drawn = float(np.mean([r["drawn"] for r in rows]))
    return dict(so_sheet_gap=round(abs(drawn - room), 3), room=room, drawn=drawn)


# --------------------------------------------------------------------------------- how cloud brightens to the limb

def apparent(X, cs, K):
    """Display values -> the light sent back, as a reflectance: through the atlas's display transform, over the Sun."""
    return (S.from_display(X, K) / K["SUN_E"] / cs[:, None]) @ CT.LUMA


def angle(tag, verbose=True):
    import epic_compare as E
    K = S.consts()
    nb = len(BINS) - 1
    acc = {b: {k: [np.zeros(nb), np.zeros(nb)] for k in ("epic", "atlas")} for b in BANDS}
    for fr in E.load_frames():
        n = fr["image"][8:]
        g = E.disc_geometry(fr["lon"], fr["lat"], fr["dist"])
        water = np.where(g["hit"], E.sample_field("water.webp", g["lon"], g["lat"]), 0)
        A = E.to_common(Image.open(os.path.join(E.REF, fr["image"] + ".png")).convert("RGB"), fr["cx"], fr["cy"], fr["r"])
        shot = os.path.join(E.SHOTS, f"epic_{tag}_{n}.jpg")
        if not os.path.exists(shot):
            raise SystemExit(f"no render {shot}; run epic_render.py {tag}")
        m = Image.open(shot).convert("RGB")
        B = E.to_common(m, m.width / 2, m.height / 2, fr["discFrac"] * m.height / 2)
        sun = E.unit(*E.sub_solar(fr)); cs = g["P"] @ sun
        v = E.unit(fr["lon"], fr["lat"]); hv = (sun + v) / np.linalg.norm(sun + v)
        glint = np.degrees(np.arccos(np.clip(g["P"] @ hv, -1, 1)))
        ok = g["hit"] & (water > 0.98) & (cs > 0.25) & (glint > 20)                  # open water, lit, away from the glint
        for b in BANDS:
            for i in range(nb):
                w = ok & (g["lat"] >= b[0]) & (g["lat"] < b[1]) & (g["mu"] >= BINS[i]) & (g["mu"] < BINS[i + 1])
                if w.sum() < 300:
                    continue
                for k, X in (("epic", A), ("atlas", B)):
                    acc[b][k][0][i] += apparent(X[w], cs[w], K).sum(); acc[b][k][1][i] += w.sum()
    if verbose:
        print(f"light sent back by open water against the view's cosine, eight frames pooled, tag {tag}")
        print("  band        " + " ".join(f"{BINS[i]:.1f}-{BINS[i + 1]:.1f}" for i in range(nb)))
        for b in BANDS:
            e, a = acc[b]["epic"], acc[b]["atlas"]; ok = e[1] > 3000
            f = lambda x: " ".join((f"{q:7.3f}" if o else "      .") for q, o in zip(x, ok))
            print(f"  {b[0]:4d}..{b[1]:<4d} EPIC  " + f(e[0] / np.maximum(e[1], 1)))
            print("              atlas " + f(a[0] / np.maximum(a[1], 1)))
            print("              ratio " + f(a[0] / np.maximum(e[0], 1e-9)))

    def level(bands, lo, hi):
        idx = [i for i in range(nb) if BINS[i] >= lo - 1e-9 and BINS[i + 1] <= hi + 1e-9]
        e = sum(acc[b]["epic"][0][idx].sum() for b in bands); a = sum(acc[b]["atlas"][0][idx].sum() for b in bands)
        return float(a / e)
    storm, trop = [BANDS[0], BANDS[-1]], [BANDS[3]]
    out = dict(storm_level=level(storm, 0.5, 0.9), storm_limb=level(storm, 0.3, 0.5), south_level=level([BANDS[0]], 0.5, 0.9), south_limb=level([BANDS[0]], 0.3, 0.5),
               north_level=level([BANDS[-1]], 0.5, 0.9), north_limb=level([BANDS[-1]], 0.3, 0.5), tropics_level=level(trop, 0.5, 0.9), tropics_limb=level(trop, 0.3, 0.5),
               subtropics_level=level([BANDS[1], BANDS[2], BANDS[4], BANDS[5]], 0.5, 0.9))
    if verbose:
        print("  the atlas's light over EPIC's, by regime: view cosine 0.5-0.9, then 0.3-0.5 (toward the limb)")
        for nm in ("storm", "south", "north", "tropics"):
            print(f"    {nm:8} {out[nm + '_level']:.3f}   {out[nm + '_limb']:.3f}")
        print(f"    subtropics (8-45 degrees) {out['subtropics_level']:.3f}")
    return out


# ------------------------------------------------------------------------------------------------------- selftest

def selftest():
    law = sheet_law()
    # 1. the sheet law: nothing of a tenth of the sky, all of a deck at ISCCP's sheet reflectance, and it only grows
    assert sheet_light(0.10, law) == 0.0 and abs(sheet_light(0.56, law) - law[0] * 0.56) < 1e-9
    x = np.linspace(0, 1, 201); y = sheet_light(x, law)
    assert (np.diff(y) >= -1e-12).all() and (np.diff(deck_share(x, law)) >= 0).all()
    assert deck_share(0.25, law) == 0.0 and deck_share(0.60, law) == 1.0, "a middling share is weather, the Peruvian deck is a deck"
    # 2. apparent(): a Lambert surface of reflectance 0.4 through the atlas's display transform reads 0.4 at every Sun height
    K = S.consts()
    cs = np.array([0.3, 0.5, 0.7, 0.9, 1.0])
    disp = S.display(K["SUN_E"] * 0.4 * cs[:, None] * np.ones((1, 3)), K)
    assert np.abs(apparent(disp, cs, K) - 0.4).max() < 0.004, apparent(disp, cs, K)
    # 3. scene_mean(): a swath gap is left out; the enhancement table is undone
    v = np.interp(np.array([0.3 * 255]), CT._GX, CT._GY)[0]
    im = np.zeros((64, 64, 3), dtype=np.uint8); im[:, :32] = int(round(v))
    tmp = os.path.join(ROOT, "scratchpad", "_cloud_budget_selftest.png"); os.makedirs(os.path.dirname(tmp), exist_ok=True)
    Image.fromarray(im).save(tmp)
    got = scene_mean(tmp); os.unlink(tmp)
    assert abs(got - 0.3) < 0.01, got
    # 4. box(): centred, wraps the antimeridian, and is wider in longitude at high latitude
    f = np.tile(np.arange(360.0)[None, :], (180, 1))
    assert box(f, 0, 0).shape == (17, 17) and box(f, 180, -55).shape[1] > 25 and abs(box(f, -100, -42).mean() - 80) < 1e-9
    print("cloud_budget selftest: ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--json" in sys.argv:
        s = survey(verbose=False); a = angle("cur", verbose=False)
        print(json.dumps(dict(so_sheet_gap=s["so_sheet_gap"], storm_level_err=round(abs(a["storm_level"] - 1), 3),
                              storm_limb_err=round(abs(a["storm_limb"] - 1), 3), tropics_level_err=round(abs(a["tropics_level"] - 1), 3))))
    elif "--survey" in sys.argv:
        if "--fetch" in sys.argv:
            survey_fetch()
        survey()
    elif "--angle" in sys.argv:
        angle(sys.argv[sys.argv.index("--angle") + 1])
    else:
        by_band()
