"""A clear-sky composite of NASA EPIC, to separate the ground from the cloud over it (register A7).

One EPIC frame cannot say whether land reads brighter than the atlas because the GROUND is brighter
or because small cloud sits on it. Seventeen days of the same view can: cloud moves, ground does not.
For each reference frame this fetches the EPIC image nearest the same sub-spacecraft longitude on
each of the surrounding days, reprojects every one onto the reference frame's geometry, and keeps,
per pixel, the third-darkest day (the darkest two are left out: cloud shadow and bad lines).

    ./venv/bin/python Research/modeling/epic_clearsky.py --fetch          # ~100 frames, ~300 MB, reference/epic/clearsky/
    ./venv/bin/python Research/modeling/epic_clearsky.py --tag clr        # needs atlas renders with clouds OFF:
        "$HOME/Modeling Studio/.venv/bin/python" Research/modeling/epic_render.py clr air,daylight,ice
    ./venv/bin/python Research/modeling/epic_clearsky.py --selftest

Prints, for land and for water, the atlas's display value against the composite's, by channel and by
how bright the atlas draws the ground, and writes side-by-side pairs to Research/figures/epic/clearsky_*.jpg.

Limits, stated: the days differ by up to about 50 minutes of local solar time (the nearest frame is
not at the same longitude), so only pixels well inside the disc and well inside daylight are scored
(view and Sun cosines above 0.5). A composite of 17 days is not cloud-free where cloud is permanent
(the ITCZ, the wet-season Amazon): the count of days that agree is reported so those pixels can be left out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epic_compare as E  # noqa: E402

CS = os.path.join(E.REF, "clearsky")
HALF = 8                       # days either side of the reference frame
KEEP = 2                       # index of the day kept after sorting by luminance (0 = darkest)
# reference frames worth compositing: the ones with land near the middle of the disc
TARGETS = ["20250320105646", "20250320180857", "20250621050744", "20240922062844", "20251221100447", "20251221171656"]


def curl(url, out=None, t=180):
    cmd = ["curl", "-s", "-f", "-m", str(t), "--retry", "3", "--retry-delay", "4"]
    if out:
        r = subprocess.run(cmd + ["-o", out + ".part", url])
        if r.returncode == 0:
            os.replace(out + ".part", out)
        return r.returncode == 0
    return subprocess.run(cmd + [url], capture_output=True, text=True).stdout


def fetch():
    os.makedirs(CS, exist_ok=True)
    frames = {f["image"][8:]: f for f in E.load_frames()}
    index, jobs = {}, []
    for n in TARGETS:
        ref = frames[n]
        day0 = dt.date(int(n[:4]), int(n[4:6]), int(n[6:8]))
        picks = []
        for k in range(-HALF, HALF + 1):
            d = (day0 + dt.timedelta(days=k)).isoformat()
            try:
                meta = json.loads(curl(f"https://epic.gsfc.nasa.gov/api/natural/date/{d}", t=60) or "[]")
            except json.JSONDecodeError:
                meta = []
            if not meta:
                continue                                    # EPIC has gaps; a missing day is just a missing day
            b = min(meta, key=lambda x: abs(((x["centroid_coordinates"]["lon"] - ref["lon"] + 540) % 360) - 180))
            if abs(((b["centroid_coordinates"]["lon"] - ref["lon"] + 540) % 360) - 180) > 14:
                continue
            png = os.path.join(CS, b["image"] + ".png")
            y, m, dd = b["date"][:4], b["date"][5:7], b["date"][8:10]
            if not os.path.exists(png):
                jobs.append((f"https://epic.gsfc.nasa.gov/archive/natural/{y}/{m}/{dd}/png/{b['image']}.png", png))
            picks.append(dict(image=b["image"], lon=b["centroid_coordinates"]["lon"], lat=b["centroid_coordinates"]["lat"],
                              dist=float(np.linalg.norm([b["dscovr_j2000_position"][k2] for k2 in "xyz"]) / E.R_KM)))
        index[n] = picks
        print(f"{n}: {len(picks)} days")
    with ThreadPoolExecutor(3) as ex:
        ok = list(ex.map(lambda j: curl(*j), jobs))
    print(f"fetched {sum(ok)} of {len(jobs)} new frames")
    for n in index:
        index[n] = [p for p in index[n] if os.path.exists(os.path.join(CS, p["image"] + ".png"))]
    with open(os.path.join(CS, "index.json"), "w") as fh:
        json.dump(index, fh, indent=1)


def project(P, lon0, lat0, dist):
    """Unit-sphere points -> (x, y) in limb radii and the view cosine, for a camera `dist` radii above
    (lon0, lat0), north up. The inverse of epic_compare.disc_geometry."""
    c = E.unit(lon0, lat0)
    l, p = np.radians(lon0), np.radians(lat0)
    right = np.array([-np.sin(l), np.cos(l), 0.0])
    up = np.array([-np.sin(p) * np.cos(l), -np.sin(p) * np.sin(l), np.cos(p)])
    v = P - c * dist
    depth = -(v @ c)
    ta = np.tan(np.arcsin(1 / dist))
    n = np.linalg.norm(v, axis=-1)
    mu = -(P * v).sum(-1) / n
    return (v @ right) / depth / ta, (v @ up) / depth / ta, mu


def sample(a, px, py):
    """Bilinear sample of an (h, w, 3) float image at float pixel coordinates."""
    h, w, _ = a.shape
    x0 = np.clip(np.floor(px).astype(int), 0, w - 2); y0 = np.clip(np.floor(py).astype(int), 0, h - 2)
    fx = np.clip(px - x0, 0, 1)[..., None]; fy = np.clip(py - y0, 0, 1)[..., None]
    return (a[y0, x0] * (1 - fx) + a[y0, x0 + 1] * fx) * (1 - fy) + (a[y0 + 1, x0] * (1 - fx) + a[y0 + 1, x0 + 1] * fx) * fy


def composite(ref, picks):
    """The clear-sky composite on the reference frame's common geometry, and how many days agree with it."""
    g = E.disc_geometry(ref["lon"], ref["lat"], ref["dist"])
    stack = []
    for p in picks:
        a = np.asarray(Image.open(os.path.join(CS, p["image"] + ".png")).convert("RGB"), dtype=np.float32)
        cx, cy, r = E.fit_disc(a)
        x, y, mu = project(g["P"], p["lon"], p["lat"], p["dist"])
        s = sample(a, cx + x * r, cy - y * r)
        s[(mu < 0.3) | ~g["hit"]] = np.nan
        stack.append(s)
    stack = np.array(stack)                                  # (days, N, N, 3)
    lum = stack @ E.LUMA
    order = np.argsort(np.where(np.isnan(lum), 1e9, lum), axis=0)
    nvalid = (~np.isnan(lum)).sum(0)
    k = np.minimum(KEEP, np.maximum(nvalid - 1, 0))
    pick = np.take_along_axis(order, k[None], 0)[0]
    out = np.take_along_axis(stack, pick[None, ..., None], 0)[0]
    chosen = np.take_along_axis(lum, pick[None], 0)[0]
    agree = (np.abs(lum - chosen[None]) < 6).sum(0)          # days within 6 levels of the kept one
    out[nvalid < 5] = np.nan
    return out, agree, g


def table(title, x, y, edges):
    """Median of y (EPIC) in bins of x (atlas), per channel."""
    print(f"\n{title}\n  atlas value    n      atlas R   G   B     EPIC R   G   B     EPIC - atlas")
    lum = x @ E.LUMA
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (lum >= lo) & (lum < hi)
        if m.sum() < 400:
            continue
        a, e = np.median(x[m], 0), np.median(y[m], 0)
        print(f"  {lo:3.0f}-{hi:3.0f}   {m.sum():7d}     {a[0]:4.0f}{a[1]:4.0f}{a[2]:4.0f}      {e[0]:4.0f}{e[1]:4.0f}{e[2]:4.0f}      {e[0]-a[0]:+4.0f}{e[1]-a[1]:+4.0f}{e[2]-a[2]:+4.0f}")


def run(tag, as_json=False):
    index = json.load(open(os.path.join(CS, "index.json")))
    frames = {f["image"][8:]: f for f in E.load_frames()}
    land_a, land_e, sea_a, sea_e, per = [], [], [], [], {}
    for n, picks in index.items():
        ref = frames[n]
        comp, agree, g = composite(ref, picks)
        shot = os.path.join(E.SHOTS, f"epic_{tag}_{n}.jpg")
        if not os.path.exists(shot):
            raise SystemExit(f"no clouds-off render {shot}; run epic_render.py {tag} air,daylight,ice")
        mine = Image.open(shot).convert("RGB")
        B = E.to_common(mine, mine.width / 2, mine.height / 2, ref["discFrac"] * mine.height / 2)
        water = np.where(g["hit"], E.sample_field("water.webp", g["lon"], g["lat"]), 0)
        sun = E.unit(*E.sub_solar(ref))
        mu0 = g["P"] @ sun
        ok = g["hit"] & (g["mu"] > 0.5) & (mu0 > 0.5) & ~np.isnan(comp[..., 0]) & (agree >= 4)
        # ice and snow are their own question (register A8) and the atlas's sea ice is being rebuilt
        ok &= np.abs(g["lat"]) < 60
        L, S = ok & (water < 0.1), ok & (water > 0.9)
        land_a.append(B[L]); land_e.append(comp[L]); sea_a.append(B[S]); sea_e.append(comp[S])
        per[n] = dict(days=len(picks), land_px=int(L.sum()),
                      land_diff=[round(float(v), 1) for v in np.median(comp[L] - B[L], 0)] if L.sum() else None,
                      sea_diff=[round(float(v), 1) for v in np.median(comp[S] - B[S], 0)] if S.sum() else None)
        os.makedirs(E.FIG, exist_ok=True)
        pair = np.concatenate([np.nan_to_num(comp), B], axis=1).clip(0, 255).astype(np.uint8)
        Image.fromarray(pair).save(os.path.join(E.FIG, f"clearsky_{n}_{tag}.jpg"), quality=88)
    la, le, sa, se = map(np.concatenate, (land_a, land_e, sea_a, sea_e))
    res = dict(land_rgb_diff=[round(float(v), 1) for v in np.median(le - la, 0)],
               sea_rgb_diff=[round(float(v), 1) for v in np.median(se - sa, 0)],
               land_abs=round(float(np.abs(le - la).mean()), 1), sea_abs=round(float(np.abs(se - sa).mean()), 1),
               clearsky_land_err=round(float(np.linalg.norm(np.median(le - la, 0))), 1),
               clearsky_sea_err=round(float(np.linalg.norm(np.median(se - sa, 0))), 1))
    if not as_json:
        for n, p in per.items():
            print(f"{n}: {p['days']} days, land px {p['land_px']}, EPIC - atlas land {p['land_diff']} sea {p['sea_diff']}")
        table("LAND, clear sky: by how bright the atlas draws it", la, le, [0, 30, 40, 50, 60, 70, 85, 100, 120, 140, 170, 256])
        table("WATER, clear sky", sa, se, [0, 20, 30, 40, 50, 60, 80, 256])
    with open(os.path.join(E.HERE, f"clearsky_scores_{tag}.json"), "w") as fh:
        json.dump(dict(tag=tag, summary=res, frames=per), fh, indent=1)
    print(json.dumps(res))
    return res


def selftest():
    # 1. project() inverts disc_geometry()
    g = E.disc_geometry(20.0, 6.5, 244.7)
    x, y, mu = project(g["P"], 20.0, 6.5, 244.7)
    yy, xx = np.mgrid[0:E.N, 0:E.N]
    h = g["hit"]
    ex = (np.abs(x - (xx - (E.N - 1) / 2) / E.RD)[h]).max(); ey = (np.abs(y - ((E.N - 1) / 2 - yy) / E.RD)[h]).max()
    assert ex < 1e-6 and ey < 1e-6, (ex, ey)
    assert np.abs(mu - g["mu"])[h].max() < 1e-6
    # 2. a camera 10 degrees east sees a point on the reference axis 10 degrees west of its own centre
    x2, y2, _ = project(E.unit(20.0, 0.0)[None], 30.0, 0.0, 244.7)
    assert x2[0] < 0 and abs(y2[0]) < 1e-9 and abs(x2[0] + np.sin(np.radians(10)) * (1 + 0.0)) < 0.01, (x2, y2)
    # 3. the kept day is the third darkest
    lum = np.array([50, 10, 30, 20, 90, 40.0])
    assert np.sort(lum)[KEEP] == 30
    print("epic_clearsky selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true"); ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tag", default="clr"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.fetch:
        fetch()
    else:
        run(a.tag, a.json)
