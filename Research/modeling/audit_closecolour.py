"""Close in, is a grey thing grey? (register A13)

Below a 0.45 km texel the ground's picture is Sentinel-2 cloudless, read into albedo by its own table
(earth.frag.glsl: S2_CURVE, AIR_LT, AIR_I) and joined to the shipped month in scene light: the month's brightness
always, half of the month's colour change (S2_SEASON), none of Blue Marble's standing warmth (S2_WARM). Until
release 1.7 the join was made in Blue Marble's display values and read through Blue Marble's table, and a city came
out khaki. This checks the constants and what the join does to grey ground.

    air_drift_e3     the shader's AIR_LT and AIR_I against the shader's OWN lighting and atmosphere evaluated at the
                     standard Sun (s2_transfer.standard_air, from TAU_R, TAU_A, SKY_L, TRANS_K, SUN_E, ...): the
                     largest difference, in thousandths. Retune the air and forget the table, and this fails.
    table_drift_e3   the shader's S2_CURVE and S2_WARM against a fresh fit (s2_transfer.fit): largest difference, thousandths
    fit_outside_pct  cells of land where Sentinel-2 by the table and Blue Marble by its own differ by over 10% in
                     scene light, the worst of the three channels, percent
    grey_cast_pct    AT ELEVEN CITY PLACES (the close-water set's), for texels Sentinel-2 photographs grey (saturation
                     under 0.10, not water), how far from grey they are drawn: |red / blue - 1| of the scene light at
                     the standard Sun, mean over the places, percent. The join is emulated here from the shader's
                     constants (inland form: no water terms), for July.
    grey_cast_worst_pct   the same, the worst place
    mean_shift_pct   how far the join moves a 5 km cell's mean brightness from the shipped month's: mean over the places

For scale the release 1.6 join is emulated beside it (display-space ratio, Blue Marble's table).

WHAT THIS DOES NOT CHECK. It is an emulation in Python of a formula that lives in GLSL: the constants are read from
the shader, the formula is written twice. Sentinel-2's own grey is taken as the witness of what is grey; nothing
independent says a roof is neutral. S2_SEASON (one half) was set by eye on six views and is not scored. The water
terms of the join, the night, and windows under snow are not exercised.

    ./venv/bin/python Research/modeling/audit_closecolour.py [--json]
    ./venv/bin/python Research/modeling/audit_closecolour.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2_transfer as T

ROOT = T.ROOT
REF = os.path.join(ROOT, "reference", "closewater")
CITIES = ("manhattan", "paris", "boston", "amsterdam", "rotterdam", "lyon", "laport", "sandiego", "albany", "cairo", "dhaka")
MONTH = 7
CELL_M = 4890.0


def constants(src=None):
    src = src or T.shader_source()
    m = re.search(r"const vec3 S2_WARM = vec3\(([^)]*)\) / ([0-9.]+);", src)
    if not m:
        raise RuntimeError("earth.frag.glsl has no S2_WARM of the form vec3(...) / n")
    warm = np.array([float(v) for v in m.group(1).split(",")]) / float(m.group(2))
    return dict(curve=T.const_floats(src, "S2_CURVE", 9), LT=T.const_vec3(src, "AIR_LT"), I=T.const_vec3(src, "AIR_I"), warm=warm,
                warm_raw=np.array([float(v) for v in m.group(1).split(",")]), season=T.const_float(src, "S2_SEASON"), lut=T.const_table(src, "ALB_LUT", 9))


def box(a, n):
    """Mean over an n x n box, edges repeated: the 5 km mean the shader reads from a mipmap."""
    from scipy import ndimage as nd
    return nd.uniform_filter(a.astype(np.float64), size=(n, n) + (1,) * (a.ndim - 2), mode="nearest")


def luma(c):
    return c @ T.LUMA


def join_new(fine, low, bm, C):
    """The release 1.7 join, inland: Sentinel-2 `fine` and its 5 km mean `low` (display, 0..1), the shipped month `bm`
    (display) -> (albedo, scene light at the standard Sun)."""
    sB = T.bm_albedo(bm, C["lut"]) * C["LT"] + C["I"]
    sL = np.interp(low, T.KNOTS, C["curve"])
    lum = luma(sB) / luma(sL)
    chroma = np.clip(sB / (sL * lum[..., None] * C["warm"]), 0.7, 1.4) ** C["season"]
    s = np.interp(fine, T.KNOTS, C["curve"]) * np.clip(lum, 0.5, 2.0)[..., None] * chroma
    alb = np.maximum((s - C["I"]) / C["LT"], 0.004)
    alb = alb / np.maximum(1.0, alb.max(-1) / 0.95)[..., None]
    return alb, alb * C["LT"] + C["I"]


def join_old(fine, low, bm, C):
    """The release 1.6 join, inland: the picture times the shipped month over the picture's own 5 km mean, in display
    values, read through Blue Marble's table."""
    j = fine * np.clip(bm / np.maximum(low, 0.03), 0.3, 3.0)
    j = j / np.maximum(1.0, j.max(-1) / 0.97)[..., None]
    alb = T.bm_albedo(np.clip(j, 0, 1), C["lut"])
    return alb, alb * C["LT"] + C["I"]


def shipped_month(lons, lats, month=MONTH):
    from PIL import Image
    from scipy import ndimage as nd
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(os.path.join(ROOT, "web", "fields", f"albedo_{month:02d}.webp")).convert("RGB")
    W, H = im.size
    x0, x1 = int((lons.min() + 180) / 360 * W) - 2, int((lons.max() + 180) / 360 * W) + 3
    y0, y1 = int((90 - lats.max()) / 180 * H) - 2, int((90 - lats.min()) / 180 * H) + 3
    a = np.asarray(im.crop((x0, y0, x1, y1))).astype(np.float64) / 255
    X, Y = np.meshgrid((lons + 180) / 360 * W - 0.5 - x0, (90 - lats) / 180 * H - 0.5 - y0)
    return np.stack([nd.map_coordinates(a[..., k], [Y, X], order=1, mode="nearest") for k in range(3)], -1)


def audit():
    src = T.shader_source()
    C = constants(src)
    LT, I = T.standard_air(src)
    air = 1000 * max(np.abs(C["LT"] - LT).max(), np.abs(C["I"] - I).max())
    s2, bm, land = T.load()
    curve, gain, ref = T.fit(s2, bm, land, C["lut"], LT, I, log=lambda *_: None)
    table = 1000 * max(np.abs(C["curve"] - curve).max(), np.abs(C["warm_raw"] - gain).max())
    outside = 100 * (1 - min(w for _, w in T.residuals(s2, ref, land, curve, gain)))
    rows = []
    for n in CITIES:
        p = os.path.join(REF, f"{n}.npz")
        if not os.path.exists(p):
            raise SystemExit(f"audit_closecolour: reference/closewater/{n}.npz is missing. Run Research/modeling/closewater_fetch.py")
        d = np.load(p)
        fine = d["s2"].astype(np.float64) / 255
        k = max(3, int(round(CELL_M / float(d["my"]))) | 1)
        low = box(fine, k)
        ship = shipped_month(d["lons"], d["lats"])
        mx, mn = fine.max(-1), fine.min(-1)
        grey = ((mx - mn) / np.maximum(mx, 0.02) < 0.10) & ~d["truth"] & (mx > 0.15)
        if grey.sum() < 1000:
            raise SystemExit(f"audit_closecolour: {n} has only {int(grey.sum())} grey texels")
        res = {}
        for name, fn in (("new", join_new), ("old", join_old)):
            alb, scene = fn(fine, low, ship, C)
            res[name] = float(np.abs(scene[grey][:, 0] / scene[grey][:, 2] - 1).mean())
            if name == "new":
                target = luma(T.bm_albedo(ship, C["lut"]) * C["LT"] + C["I"])
                inland = box(d["truth"].astype(np.float64), k) < 0.02
                shift = float(np.abs(box(luma(scene), k)[inland] / box(target, k)[inland] - 1).mean()) if inland.sum() > 1000 else float("nan")
        rows.append(dict(name=n, grey=float(grey.mean()), new=res["new"], old=res["old"], shift=shift))
    shifts = [r["shift"] for r in rows if np.isfinite(r["shift"])]
    summary = dict(air_drift_e3=round(float(air), 1), table_drift_e3=round(float(table), 1), fit_outside_pct=round(float(outside), 1),
                   grey_cast_pct=round(100 * float(np.mean([r["new"] for r in rows])), 1), grey_cast_worst_pct=round(100 * max(r["new"] for r in rows), 1),
                   mean_shift_pct=round(100 * float(np.mean(shifts)), 1), old_grey_cast_pct=round(100 * float(np.mean([r["old"] for r in rows])), 1),
                   old_grey_cast_worst_pct=round(100 * max(r["old"] for r in rows), 1))
    return summary, rows


def selftest():
    C = constants()
    # 1. a grey texel in a grey cell whose shipped month is the same grey ground: drawn grey, at the month's brightness
    grey = np.full((1, 3), 0.5)
    bm_same = None
    # the Blue Marble display value whose scene light equals the Sentinel-2 curve's for 0.5, channel by channel
    want = (np.interp(0.5, T.KNOTS, C["curve"]) * C["warm"] - C["I"]) / C["LT"]
    bm_same = np.array([[np.interp(want[k], C["lut"][:, k], T.KNOTS) for k in range(3)]])
    alb, scene = join_new(grey, grey, bm_same, C)
    assert abs(scene[0, 0] / scene[0, 2] - 1) < 0.01, scene
    # 2. the month twice as bright: the texel twice as bright in scene light, still grey
    sB = T.bm_albedo(bm_same, C["lut"]) * C["LT"] + C["I"]
    bright = np.array([[np.interp(((2 * sB[0, k]) - C["I"][k]) / C["LT"][k], C["lut"][:, k], T.KNOTS) for k in range(3)]])
    _, scene2 = join_new(grey, grey, bright, C)
    assert abs(luma(scene2)[0] / luma(scene)[0] - 2) < 0.05 and abs(scene2[0, 0] / scene2[0, 2] - 1) < 0.01, (scene, scene2)
    # 3. a month redder than the picture by 30%: half of it is applied (S2_SEASON), the rest is not
    red = sB.copy(); red[0, 0] *= 1.3
    bm_red = np.array([[np.interp((red[0, k] - C["I"][k]) / C["LT"][k], C["lut"][:, k], T.KNOTS) for k in range(3)]])
    _, scene3 = join_new(grey, grey, bm_red, C)
    got = (scene3[0, 0] / scene3[0, 2]) / (scene[0, 0] / scene[0, 2])
    assert 1.3 ** (C["season"] * 0.6) < got < 1.3 ** min(1.0, C["season"] * 1.4), got
    # 4. the old join gives the grey texel the cell's colour: an olive month makes it olive, and the new one does not
    olive = np.array([[0.30, 0.32, 0.19]])
    _, so = join_old(grey, grey, olive, C)
    _, sn = join_new(grey, grey, olive, C)
    assert abs(so[0, 0] / so[0, 2] - 1) > 2 * abs(sn[0, 0] / sn[0, 2] - 1), (so, sn)
    # 5. the constants in the shader are the standard air's
    LT, I = T.standard_air()
    assert np.abs(C["LT"] - LT).max() < 2e-3 and np.abs(C["I"] - I).max() < 2e-3, (C["LT"], LT, C["I"], I)
    print("  ok   audit_closecolour selftest: grey stays grey; the month's brightness is kept; half of its colour change; the old join's cast is seen; the air constants are the shader's own")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    summary, rows = audit()
    if "--json" not in sys.argv:
        for r in rows:
            print(f"  {r['name']:10s} grey texels {100 * r['grey']:4.1f}% of the box  drawn off grey by {100 * r['new']:5.1f}% (release 1.6: {100 * r['old']:5.1f}%)  5 km brightness moved {100 * r['shift']:.1f}%")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
