"""What reflectance does a Blue Marble pixel value stand for? (register A7)

The shader used to read Blue Marble's 8-bit colour as sRGB, (value/255)^2.2, and call it albedo.
Against EPIC's clear-sky composite (epic_clearsky.py) dark land came out 20-50 display levels too
dark while bright desert and open sea matched: the signature of a wrong transfer curve. Blue Marble
is a picture, made to look right on a screen; nothing says its values are sRGB of reflectance.

This script asks the composite directly:
  1. check shader_model against the atlas's own clouds-off render (the instrument first);
  2. invert the model on EPIC's clear-sky value: the albedo EPIC implies at each pixel;
  3. tabulate implied albedo against the Blue Marble value, per channel, using only pixels where at
     least `--agree` of the ~16 days show the same brightness (cloud moves; ground does not);
  4. --fit: a nine-knot table per channel (the shader's ALB_LUT), fitted on three frames and scored
     on the other three, then refitted on all six and printed as GLSL.

    "$HOME/Modeling Studio/.venv/bin/python" Research/modeling/epic_render.py clr air,daylight,ice
    ./venv/bin/python Research/modeling/land_transfer.py [--fit] [--agree 9] [--json]

What the table is NOT: a measurement of surface reflectance. It is the albedo that reproduces EPIC's
view, which is straight back along the sunlight (phase 4-12 degrees) where vegetation and rough
ground hide their own shadows and read brighter than from elsewhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epic_compare as E  # noqa: E402
import epic_clearsky as C  # noqa: E402
import shader_model as S  # noqa: E402

KNOTS = 9
_alb = {}


def bmng_value(t_iso, lon, lat):
    """The shipped albedo texture's 8-bit value at the clock's date: the two bracketing months, mixed
    as web/js does (keyframes at mid-month, cyclic)."""
    d = dt.datetime.fromisoformat(t_iso.replace("Z", "+00:00"))
    days = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    x = d.month - 1 + (d.day - 1 + d.hour / 24) / days[d.month - 1] - 0.5
    i0 = int(np.floor(x)) % 12; f = x - np.floor(x); i1 = (i0 + 1) % 12
    out = 0
    for i, w in ((i0, 1 - f), (i1, f)):
        if i not in _alb:
            _alb[i] = np.asarray(Image.open(os.path.join(E.ROOT, "web", "fields", f"albedo_{i + 1:02d}_p.webp")).convert("RGB"), dtype=np.float32)
        a = _alb[i]; h, w_, _ = a.shape
        col = np.clip(((lon + 180) / 360 * w_).astype(int), 0, w_ - 1); row = np.clip(((90 - lat) / 180 * h).astype(int), 0, h - 1)
        out = out + w * a[row, col]
    return out


def gather(tag, K, agree_min):
    index = json.load(open(os.path.join(C.CS, "index.json")))
    frames = {f["image"][8:]: f for f in E.load_frames()}
    V, G, I, DE, DA, FR = [], [], [], [], [], []
    for k, (n, picks) in enumerate(index.items()):
        ref = frames[n]
        cache = os.path.join(C.CS, f"composite_{n}.npz")
        g = E.disc_geometry(ref["lon"], ref["lat"], ref["dist"])
        if os.path.exists(cache):
            z = np.load(cache); comp, agree = z["comp"], z["agree"]
        else:
            comp, agree, g = C.composite(ref, picks)
            np.savez_compressed(cache, comp=comp, agree=agree)
        mine = Image.open(os.path.join(E.SHOTS, f"epic_{tag}_{n}.jpg")).convert("RGB")
        B = E.to_common(mine, mine.width / 2, mine.height / 2, ref["discFrac"] * mine.height / 2)
        water = np.where(g["hit"], E.sample_field("water.webp", g["lon"], g["lat"]), 0)
        sun = E.unit(*E.sub_solar(ref))
        mu0 = g["P"] @ sun
        ok = g["hit"] & (g["mu"] > 0.6) & (mu0 > 0.6) & ~np.isnan(comp[..., 0]) & (agree >= agree_min) & (water < 0.05) & (np.abs(g["lat"]) < 60)
        L = S.light(mu0[ok], g["mu"][ok], -(g["d"][ok] @ sun), K)
        V.append(bmng_value(ref["t"], g["lon"][ok], g["lat"][ok]))
        G.append(S.land_gain(L)); I.append(L["inscat"])
        DE.append(comp[ok]); DA.append(B[ok]); FR.append(np.full(ok.sum(), k))
    return tuple(map(np.concatenate, (V, G, I, DE, DA, FR)))


def fit_lut(v, implied):
    """Nine knots per channel, equally spaced in pixel value. Each knot is a local line through the
    medians of 8-level bins; below the data the curve runs to zero, above it the line continues (white is
    snow and is handled by the shader's snow rule, not by this table); never decreasing."""
    xs = np.linspace(0, 255, KNOTS)
    lut = np.zeros((KNOTS, 3))
    for c in range(3):
        bx, by, bw = [], [], []
        for lo in range(0, 256, 8):
            m = (v[:, c] >= lo) & (v[:, c] < lo + 8)
            if m.sum() >= 150:
                bx.append(np.median(v[m, c])); by.append(np.median(implied[m, c])); bw.append(np.sqrt(m.sum()))
        bx, by, bw = map(np.array, (bx, by, bw))
        have = []
        for k, x in enumerate(xs):
            near = np.abs(bx - x) <= 22
            if near.sum() >= 3 and bx[near].min() <= x + 4 and bx[near].max() >= x - 4:
                A = np.stack([bx[near] - x, np.ones(near.sum())], 1) * bw[near, None]
                lut[k, c] = np.linalg.lstsq(A, by[near] * bw[near], rcond=None)[0][1]
                have.append(k)
        lo_k, hi_k = have[0], have[-1]
        for k in range(lo_k):                                   # toward black: straight to zero
            lut[k, c] = lut[lo_k, c] * xs[k] / xs[lo_k]
        slope = (lut[hi_k, c] - lut[hi_k - 2, c]) / (xs[hi_k] - xs[hi_k - 2])
        for k in range(hi_k + 1, KNOTS):                        # above the data: the channel's own line continues
            lut[k, c] = lut[hi_k, c] + slope * (xs[k] - xs[hi_k])
        lut[:, c] = np.maximum.accumulate(np.clip(lut[:, c], 0.0, 1.0))
    return lut


def score(v, gain, ins, d_epic, K):
    """Clear-sky land error in display levels with the table in K: median signed, and mean absolute."""
    pred = S.display(S.decode_albedo(v, K) * gain + ins, K)
    return np.median(pred - d_epic, 0), float(np.abs(pred - d_epic).mean())


def main(tag, fit, agree_min, as_json):
    K = S.consts()
    v, gain, ins, d_epic, d_atlas, fr = gather(tag, K, agree_min)
    rebuilt = S.display(S.decode_albedo(v, K) * gain + ins, K)
    res = rebuilt - d_atlas
    med, mae = score(v, gain, ins, d_epic, K)
    out = dict(instrument_bias=round(float(np.abs(np.median(res, 0)).max()), 1), clearsky_land_abs=round(mae, 1),
               clearsky_land_bias=round(float(np.abs(med).max()), 1), pixels=int(len(v)))
    if as_json:
        print(json.dumps(out)); return
    print(f"pixels kept: the composite value is matched (within 6 levels) by at least {agree_min} of the days   [{len(v)} land pixels]")
    print(f"instrument check, rebuilt minus rendered (display levels): median {np.median(res, 0).round(1)}, "
          f"p10 {np.percentile(res, 10, 0).round(1)}, p90 {np.percentile(res, 90, 0).round(1)}")
    print(f"atlas against EPIC clear sky, as the shader stands: median atlas - EPIC {med.round(1)}, mean absolute {mae:.1f}")
    implied = (S.from_display(d_epic, K) - ins) / gain
    print("\nalbedo EPIC implies, against the Blue Marble value (medians; all six frames)")
    print("  BM value    as sRGB^2.2     n(R)   implied R      n(G)   implied G      n(B)   implied B")
    for lo, hi in zip(range(0, 256, 16), range(16, 257, 16)):
        cells = []
        for c in range(3):
            m = (v[:, c] >= lo) & (v[:, c] < hi)
            cells.append((int(m.sum()), float(np.median(implied[m, c])) if m.sum() > 200 else np.nan))
        print(f"  {lo:3d}-{hi:3d}      {((lo + hi) / 510) ** 2.2:6.3f}     {cells[0][0]:7d}    {cells[0][1]:6.3f}    {cells[1][0]:7d}    {cells[1][1]:6.3f}    {cells[2][0]:7d}    {cells[2][1]:6.3f}")
    if not fit:
        return
    nf = int(fr.max()) + 1
    train = np.isin(fr, [0, 2, 4]); test = ~train
    lut_half = fit_lut(v[train], implied[train])
    K0 = dict(K, ALB_LUT=None); K1 = dict(K, ALB_LUT=lut_half)
    print("\nheld-out test: table fitted on frames 0, 2, 4; scored on frames 1, 3, 5 (different longitudes or seasons)")
    for name, kk in (("sRGB^2.2", K0), ("fitted table", K1)):
        med, mae = score(v[test], gain[test], ins[test], d_epic[test], kk)
        print(f"  {name:13s} median atlas - EPIC {med.round(1)}   mean absolute {mae:.1f}")
    lut = fit_lut(v, implied)
    med, mae = score(v, gain, ins, d_epic, dict(K, ALB_LUT=lut))
    print(f"\nall six frames, table fitted on all: median {med.round(1)}, mean absolute {mae:.1f}; per frame mean absolute: "
          + " ".join(f"{score(v[fr == k], gain[fr == k], ins[fr == k], d_epic[fr == k], dict(K, ALB_LUT=lut))[1]:.1f}" for k in range(nf)))
    print("\n// Blue Marble value -> albedo, nine knots (0, 32, 64 ... 255). Research/modeling/land_transfer.py --fit")
    print(f"const vec3 ALB_LUT[{KNOTS}] = vec3[](" + ", ".join(f"vec3({r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f})" for r in lut) + ");")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="clr"); ap.add_argument("--fit", action="store_true")
    ap.add_argument("--agree", type=int, default=9); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    main(a.tag, a.fit, a.agree, a.json)
