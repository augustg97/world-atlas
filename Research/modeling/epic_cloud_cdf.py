"""Brightness distribution over open water, EPIC against the atlas (register A1 / B1).

Open ocean is a dark, uniform ground, so the distribution of brightness over it is the
distribution of cloud. Where the two curves part says which end of the cloud opacity curve is
wrong, without caring where any individual cloud is.

    ./venv/bin/python Research/modeling/epic_cloud_cdf.py r4 [--land]
"""
import sys, os
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epic_compare as E

P = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99.5]


def main(tag, land=False):
    acc = {"epic": [], "atlas": []}; chroma = {"epic": [], "atlas": []}
    for fr in E.load_frames():
        n = fr["image"][8:]
        g = E.disc_geometry(fr["lon"], fr["lat"], fr["dist"])
        water = np.where(g["hit"], E.sample_field("water.webp", g["lon"], g["lat"]), 0)
        A = E.to_common(Image.open(os.path.join(E.REF, fr["image"] + ".png")).convert("RGB"), fr["cx"], fr["cy"], fr["r"])
        m = Image.open(os.path.join(E.SHOTS, f"epic_{tag}_{n}.jpg")).convert("RGB")
        B = E.to_common(m, m.width / 2, m.height / 2, fr["discFrac"] * m.height / 2)
        w = g["hit"] & ((water < 0.02) if land else (water > 0.98)) & (g["mu"] > 0.55) & (np.abs(g["lat"]) < 55)
        if w.sum() < 2000:
            continue
        for k, X in (("epic", A), ("atlas", B)):
            lum = X @ E.LUMA
            acc[k].append(np.percentile(lum[w], P))
            br = w & (lum > 150)
            chroma[k].append((X[br].max(1) - X[br].min(1)).mean() if br.sum() > 50 else np.nan)
    print(f"luminance percentiles over {'land' if land else 'open water'}, cos(view) > 0.55, |lat| < 55, tag {tag}")
    print("pct   ", " ".join(f"{p:6}" for p in P))
    for k in acc:
        print(f"{k:6}", " ".join(f"{v:6.0f}" for v in np.mean(acc[k], 0)), f"  chroma of bright pixels {np.nanmean(chroma[k]):.1f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "r0", land="--land" in sys.argv)
