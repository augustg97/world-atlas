"""Close in, is a grey thing grey, and does the year turn? (registers A13, A16)

Below a 0.45 km texel the ground's picture is Sentinel-2 cloudless, read into albedo by its own table
(earth.frag.glsl: S2_CURVE, AIR_LT, AIR_I) and joined to the shipped month: the month's brightness always, and since
release 1.8 the month's COLOUR as a shift, Blue Marble's month against Blue Marble at the picture's own season
(web/fields/albedo_ref.webp, build/season_ref.py), whole. Release 1.7 took the month's colour over the picture's own
at half strength (S2_SEASON, S2_WARM); until then the join was made in Blue Marble's display values and read through
Blue Marble's table, and a city came out khaki. This checks the constants, what the join does to grey ground, and
how much of the year's change of colour reaches the close view.

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
    season_short_pct AT THE 23 CLOSE-WATER PLACES, how much of Blue Marble's own change of colour between July and
                     January, April and October (colour = albedo over its brightness, 5 km cells with no water)
                     FAILS to reach the close view: 100 less the close view's change along Blue Marble's, as a
                     percentage of it, the median over places and months where Blue Marble changes by more than 0.03.
                     0 is the whole season; release 1.7's half strength scores about 50.
    season_off_pct   the close view's change of colour ACROSS Blue Marble's direction (a hue the month does not
                     have), as a percentage of Blue Marble's change: the median likewise

For scale the release 1.6 join is emulated beside it (display-space ratio, Blue Marble's table).

WHAT THIS DOES NOT CHECK. It is an emulation in Python of a formula that lives in GLSL: the constants are read from
the shader, the formula is written twice. Sentinel-2's own grey is taken as the witness of what is grey; nothing
independent says a roof is neutral. The season is scored against Blue Marble itself, which is the claim (the close
view follows the month as the far view does), not against the ground: whether Blue Marble's month is right is the
far view's question. The reference month per place is a fit (season_ref.py) with no witness. The water terms of the
join, the night, the thinned air close in (airCut) and windows under snow are not exercised.

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


def code(ratio):
    """detail.js seasonCode and the shader's detUnpack, there and back: a colour ratio as the byte the window carries."""
    c = np.clip(np.round(np.log(np.maximum(ratio, 0.08) / 0.08) / np.log(2.5 / 0.08) * 255), 0, 255)
    return 0.08 * np.exp(c / 255 * np.log(2.5 / 0.08))


def join_new(fine, low, bm, ref, C):
    """The release 1.8 join, inland: Sentinel-2 `fine` and its 5 km mean `low` (display, 0..1), the shipped month `bm`
    and Blue Marble at the picture's own season `ref` (display) -> (albedo, scene light at the standard Sun)."""
    aN, a = T.bm_albedo(bm, C["lut"]), T.bm_albedo(ref, C["lut"])
    aL = np.maximum((np.interp(low, T.KNOTS, C["curve"]) - C["I"]) / C["LT"], 0.0)
    lum = np.clip(luma(aN) / np.maximum(luma(aL), 0.01), 0.4, 2.5)
    alb = np.maximum((np.interp(fine, T.KNOTS, C["curve"]) - C["I"]) / C["LT"], 0.004) * lum[..., None]
    g = np.maximum(a[..., 1], 1e-3)
    aR = np.stack([code(a[..., 0] / g), np.ones_like(g), code(a[..., 2] / g)], -1)       # as the window carries it: albedo over its green
    shift = aN / np.maximum(luma(aN), 1e-3)[..., None] - aR / np.maximum(luma(aR), 1e-3)[..., None]
    alb = np.maximum(alb + luma(alb)[..., None] * shift, 0.25 * alb)
    alb = alb / np.maximum(1.0, alb.max(-1) / 0.95)[..., None]
    return snow(alb, bm, C)


def snow(alb, bm, C):
    """Under snow the shader shows the shipped month, not the picture (earth.frag.glsl, `snowy`): summer ground does not show through."""
    t = np.clip((bm.min(-1) - 0.70) / 0.20, 0, 1)
    w = (t * t * (3 - 2 * t))[..., None]
    alb = alb * (1 - w) + T.bm_albedo(bm, C["lut"]) * w
    return alb, alb * C["LT"] + C["I"]


def join_half(fine, low, bm, ref, C):
    """The release 1.7 join, inland: the month's colour over the picture's own less the cameras' standing difference, at half strength."""
    sB = T.bm_albedo(bm, C["lut"]) * C["LT"] + C["I"]
    sL = np.interp(low, T.KNOTS, C["curve"])
    lum = luma(sB) / luma(sL)
    chroma = np.clip(sB / (sL * lum[..., None] * C["warm"]), 0.7, 1.4) ** C["season"]
    s = np.interp(fine, T.KNOTS, C["curve"]) * np.clip(lum, 0.5, 2.0)[..., None] * chroma
    alb = np.maximum((s - C["I"]) / C["LT"], 0.004)
    alb = alb / np.maximum(1.0, alb.max(-1) / 0.95)[..., None]
    return snow(alb, bm, C)


def join_old(fine, low, bm, ref, C):
    """The release 1.6 join, inland: the picture times the shipped month over the picture's own 5 km mean, in display
    values, read through Blue Marble's table."""
    j = fine * np.clip(bm / np.maximum(low, 0.03), 0.3, 3.0)
    j = j / np.maximum(1.0, j.max(-1) / 0.97)[..., None]
    alb = T.bm_albedo(np.clip(j, 0, 1), C["lut"])
    return alb, alb * C["LT"] + C["I"]


def shipped_month(lons, lats, month=MONTH):
    """A shipped month (1..12), or the season reference ("ref"), sampled bilinearly at a place's grid: display values 0..1."""
    from PIL import Image
    from scipy import ndimage as nd
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(os.path.join(ROOT, "web", "fields", "albedo_ref.webp" if month == "ref" else f"albedo_{month:02d}.webp")).convert("RGB")
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
        ref = shipped_month(d["lons"], d["lats"], "ref")
        mx, mn = fine.max(-1), fine.min(-1)
        grey = ((mx - mn) / np.maximum(mx, 0.02) < 0.10) & ~d["truth"] & (mx > 0.15)
        if grey.sum() < 1000:
            raise SystemExit(f"audit_closecolour: {n} has only {int(grey.sum())} grey texels")
        res = {}
        for name, fn in (("new", join_new), ("old", join_old)):
            alb, scene = fn(fine, low, ship, ref, C)
            res[name] = float(np.abs(scene[grey][:, 0] / scene[grey][:, 2] - 1).mean())
            if name == "new":
                target = luma(T.bm_albedo(ship, C["lut"]) * C["LT"] + C["I"])
                inland = box(d["truth"].astype(np.float64), k) < 0.02
                shift = float(np.abs(box(luma(scene), k)[inland] / box(target, k)[inland] - 1).mean()) if inland.sum() > 1000 else float("nan")
        rows.append(dict(name=n, grey=float(grey.mean()), new=res["new"], old=res["old"], shift=shift))
    shifts = [r["shift"] for r in rows if np.isfinite(r["shift"])]
    # ---- the season: at every close-water place, how much of Blue Marble's own change of colour reaches the close view
    import glob
    short, off, short_half, srows = [], [], [], []
    chroma = lambda sc: sc / luma(sc)[..., None]
    for p in sorted(glob.glob(os.path.join(REF, "*.npz"))):
        n = os.path.basename(p)[:-4]
        if "." in n:
            continue
        d = np.load(p)
        fine = d["s2"].astype(np.float64) / 255
        k = max(3, int(round(CELL_M / float(d["my"]))) | 1)
        inland = box(d["truth"].astype(np.float64), k) < 0.02
        if inland.sum() < 1000:
            continue
        low, ref = box(fine, k), shipped_month(d["lons"], d["lats"], "ref")
        sea = {m: shipped_month(d["lons"], d["lats"], m) for m in (7, 1, 4, 10)}
        # in ALBEDO, where the atlas keeps the ground. (In scene light the same change of ground reads differently in
        # the two views whenever the month's brightness changes: the air's share of the light changes with it, and
        # Sentinel-2's ground starts nearer the air's colour than Blue Marble's does. That is the two pictures, not the join.)
        far = {m: chroma(T.bm_albedo(sea[m], C["lut"]))[inland].mean(0) for m in sea}
        near = {name: {m: chroma(box(fn(fine, low, sea[m], ref, C)[0], k))[inland].mean(0) for m in sea} for name, fn in (("new", join_new), ("half", join_half))}
        for m in (1, 4, 10):
            dF = far[m] - far[7]
            if np.linalg.norm(dF) < 0.03:
                continue
            dN, dH = near["new"][m] - near["new"][7], near["half"][m] - near["half"][7]
            along = float(dN @ dF / (dF @ dF))
            short.append(100 * (1 - along)); off.append(100 * float(np.linalg.norm(dN - along * dF) / np.linalg.norm(dF)))
            short_half.append(100 * (1 - float(dH @ dF / (dF @ dF))))
            srows.append(dict(name=n, month=m, far=float(np.linalg.norm(dF)), kept=100 * along, kept_half=100 - short_half[-1], off=off[-1]))
    if len(short) < 12:
        raise SystemExit(f"audit_closecolour: only {len(short)} place-months have a season to score")
    summary = dict(air_drift_e3=round(float(air), 1), table_drift_e3=round(float(table), 1), fit_outside_pct=round(float(outside), 1),
                   grey_cast_pct=round(100 * float(np.mean([r["new"] for r in rows])), 1), grey_cast_worst_pct=round(100 * max(r["new"] for r in rows), 1),
                   mean_shift_pct=round(100 * float(np.mean(shifts)), 1), season_short_pct=round(float(np.median(short)), 1), season_off_pct=round(float(np.median(off)), 1),
                   half_season_short_pct=round(float(np.median(short_half)), 1), season_scored=len(short), season_short_worst_pct=round(float(np.max(short)), 1), old_grey_cast_pct=round(100 * float(np.mean([r["old"] for r in rows])), 1),
                   old_grey_cast_worst_pct=round(100 * max(r["old"] for r in rows), 1))
    return summary, rows, srows


def selftest():
    C = constants()
    grey = np.full((1, 3), 0.5)
    # the Blue Marble display value whose scene light equals the Sentinel-2 curve's for 0.5, channel by channel
    want = (np.interp(0.5, T.KNOTS, C["curve"]) - C["I"]) / C["LT"]
    bm_same = np.array([[np.interp(want[k], C["lut"][:, k], T.KNOTS) for k in range(3)]])
    # 1. a grey texel in a grey cell, the month being the picture's own season: drawn grey, at the month's brightness
    alb, scene = join_new(grey, grey, bm_same, bm_same, C)
    assert abs(scene[0, 0] / scene[0, 2] - 1) < 0.01, scene
    # 2. the month's ground half again as bright, the same colour: the texel's ALBEDO half again as bright and the same
    #    colour (in scene light it then stands a little warmer against the same air, as brighter ground does)
    a_same = T.bm_albedo(bm_same, C["lut"])
    disp = lambda al: np.array([[np.interp(al[0, k], C["lut"][:, k], T.KNOTS) for k in range(3)]])
    alb2, scene2 = join_new(grey, grey, disp(1.5 * a_same), disp(1.5 * a_same), C)
    assert abs(luma(alb2)[0] / luma(alb)[0] - 1.5) < 0.03 and np.abs(alb2[0] / luma(alb2)[0] - alb[0] / luma(alb)[0]).max() < 0.02 and scene2[0, 0] > scene2[0, 2], (alb, alb2, scene2)
    # 3. Blue Marble's standing colour for the ground is not a season: an olive month over an olive reference leaves the grey texel grey
    olive = np.array([[0.30, 0.32, 0.19]])
    _, sn = join_new(grey, grey, olive, olive, C)
    _, so = join_old(grey, grey, olive, olive, C)
    an, _ = join_new(grey, grey, olive, olive, C)
    assert np.abs(an[0] / luma(an)[0] - alb[0] / luma(alb)[0]).max() < 0.02 and abs(sn[0, 0] / sn[0, 2] - 1) < 0.10 < 0.2 < abs(so[0, 0] / so[0, 2] - 1), (sn, so)
    # 4. a month redder than the reference: the texel's colour moves by Blue Marble's own move, in albedo over brightness, whole
    red = olive * np.array([1.25, 0.95, 0.9])
    a0, _ = join_new(grey, grey, olive, olive, C)
    a1, _ = join_new(grey, grey, red, olive, C)
    aN, aR = T.bm_albedo(red, C["lut"]), T.bm_albedo(olive, C["lut"])
    moved, asked = a1[0] / luma(a1)[0] - a0[0] / luma(a0)[0], aN[0] / luma(aN)[0] - aR[0] / luma(aR)[0]
    assert np.abs(moved - asked).max() < 0.05 * np.abs(asked).max() + 0.01 and abs(luma(a1)[0] / luma(a0)[0] - luma(aN)[0] / luma(aR)[0]) < 0.03, (moved, asked)
    # 5. release 1.7's join applies about half of it
    h0, _ = join_half(grey, grey, olive, olive, C)
    h1, _ = join_half(grey, grey, red, olive, C)
    mh = h1[0] / luma(h1)[0] - h0[0] / luma(h0)[0]
    assert 0.2 < (mh @ asked) / (asked @ asked) < 0.8, (mh, asked)
    # 6. the byte the window carries holds a colour ratio to under 1%
    r = np.array([0.1, 0.45, 0.8, 1.0, 1.7, 2.4])
    assert np.abs(code(r) / r - 1).max() < 0.01
    # 7. the constants in the shader are the standard air's
    LT, I = T.standard_air()
    assert np.abs(C["LT"] - LT).max() < 2e-3 and np.abs(C["I"] - I).max() < 2e-3, (C["LT"], LT, C["I"], I)
    print("  ok   audit_closecolour selftest: grey stays grey; the month's brightness is the ground's, in albedo; Blue Marble's standing colour is not a season; a season moves the colour by Blue Marble's own move, whole; release 1.7's moved it by half; the byte holds 1%; the air constants are the shader's own")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    summary, rows, srows = audit()
    if "--json" not in sys.argv:
        for r in srows:
            print(f"  {r['name']:12s} month {r['month']:2d}: Blue Marble's colour moves {r['far']:.3f} from July's; the close view keeps {r['kept']:5.0f}% of it (release 1.7: {r['kept_half']:4.0f}%), {r['off']:4.0f}% across it")
        for r in rows:
            print(f"  {r['name']:10s} grey texels {100 * r['grey']:4.1f}% of the box  drawn off grey by {100 * r['new']:5.1f}% (release 1.6: {100 * r['old']:5.1f}%)  5 km brightness moved {100 * r['shift']:.1f}%")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
