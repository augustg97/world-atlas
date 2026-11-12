"""The season Sentinel-2 was photographed in, as a picture: web/fields/albedo_ref.webp (register A16).

Close in, the ground is Sentinel-2 cloudless (one mosaic of 2016, each place at whatever time of its year was
clearest) and the month's colour is Blue Marble's (twelve months, 5 km). To give the picture the MONTH's colour the
shader needs to know how far the month is from the picture's own season, and until release 1.8 it did not: it took
the month's colour over the picture's, which also holds the two cameras' difference for that kind of ground (a city
is olive in Blue Marble and grey in Sentinel-2), and so applied it at half strength, by eye.

This writes Blue Marble AT THE PICTURE'S OWN SEASON, place by place: for every 20 km cell the month whose Blue Marble
is most like Sentinel-2 there (by the table s2_transfer.py fits), smoothed over 60 km as a time of year (months are a
circle), and the two shipped months either side of that time blended. The shader then takes the month's colour over
THIS picture's, Blue Marble over Blue Marble, which is the season and nothing else, at full strength.

Land only: the sea's share of each 5 km cell is taken out (the shipped picture's sea is one fill colour), as the
shader takes it out of the month, and cells that are all sea are filled from the nearest land so that a coast reads
its own land's season.

    ./venv/bin/python build/season_ref.py            # needs reference/s2global (Research/modeling/s2_transfer.py --fetch)
    ./venv/bin/python build/season_ref.py --selftest
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Research", "modeling"))
OUT = os.path.join(ROOT, "web", "fields")


def circular_smooth(month, weight, sigma):
    """Months (0..11, any shape) smoothed as angles with Gaussian `sigma` cells, counting only cells with weight.
    Returns (fractional month 0..12, how much weight was in reach). Longitude wraps."""
    from scipy import ndimage as nd
    a = month * (2 * np.pi / 12)
    f = lambda v: nd.gaussian_filter(v, sigma, mode=("nearest", "wrap"))
    c, s, w = f(np.cos(a) * weight), f(np.sin(a) * weight), f(weight.astype(np.float64))
    out = (np.arctan2(s, c) * (12 / (2 * np.pi))) % 12
    return out, w


def blend_weights(frac):
    """For a fractional month field, the weight of each of the twelve months: (12, ...) summing to 1, the two
    months either side of the time, linearly."""
    lo = np.floor(frac).astype(int) % 12
    t = frac - np.floor(frac)
    w = np.zeros((12,) + frac.shape, np.float32)
    np.put_along_axis(w, lo[None], (1 - t)[None].astype(np.float32), 0)
    hi = (lo + 1) % 12
    w2 = np.zeros_like(w)
    np.put_along_axis(w2, hi[None], t[None].astype(np.float32), 0)
    return w + w2


def reference_month():
    """The picture's own time of year on the 20 km grid (1024 x 2048), as a fractional month 0..12 (0 = mid January)."""
    import s2_transfer as T
    src = T.shader_source()
    lut = T.const_table(src, "ALB_LUT", 9)
    LT, I = T.standard_air(src)
    s2, bm, land = T.load()
    curve, gain, _ = T.fit(s2, bm, land, lut, LT, I, log=lambda *_: None)
    scene_bm = T.bm_albedo(bm, lut) * LT + I
    mine = T.s2_scene(s2, curve, gain)
    best = np.abs(np.log(scene_bm / mine[None])).sum(-1).argmin(0)
    frac, reach = circular_smooth(best.astype(np.float64), land, 3.0)
    # beyond the reach of any fitted cell (ice, the far north): high summer, when a cloudless mosaic is made
    lat = 90 - (np.arange(best.shape[0]) + 0.5) * 180 / best.shape[0]
    summer = np.where(lat[:, None] >= 0, 6.0, 0.0) * np.ones_like(frac)
    frac = np.where(reach > 1e-3, frac, summer)
    return frac, best, land


def main():
    from PIL import Image
    from scipy import ndimage as nd
    import s2_transfer as T
    Image.MAX_IMAGE_PIXELS = None
    frac, best, land = reference_month()
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    counts = np.bincount(best[land], minlength=12)
    print("  the month each fitted cell is most like: " + ", ".join(f"{n} {100 * c / counts.sum():.0f}%" for n, c in zip(names, counts)))
    w20 = blend_weights(frac)                                       # (12, 1024, 2048)
    fill = T.const_vec3(T.shader_source(), "OCEAN_FILL")
    water = np.asarray(Image.open(os.path.join(OUT, "water.webp")).convert("L")).astype(np.float32) / 255
    H, W = water.shape
    acc = np.zeros((H, W, 3), np.float32)
    for m in range(12):
        if not w20[m].any():
            continue
        wm = np.asarray(Image.fromarray(w20[m]).resize((W, H), Image.BILINEAR))
        im = np.asarray(Image.open(os.path.join(OUT, f"albedo_{m + 1:02d}.webp")).convert("RGB")).astype(np.float32) / 255
        acc += wm[..., None] * im
        del im
    # land only: the sea's share out, as the shader does it (earth.frag.glsl, landShip); all-sea cells from the nearest land
    share = np.clip(1 - water, 0, 1)
    ok = share > 0.3
    landc = np.clip((acc - (water[..., None] * fill.astype(np.float32))) / np.maximum(share, 0.3)[..., None], 0, 1)
    idx = nd.distance_transform_edt(~ok, return_distances=False, return_indices=True)
    landc = landc[idx[0], idx[1]]
    p = os.path.join(OUT, "albedo_ref.webp")
    Image.fromarray(np.round(landc * 255).astype(np.uint8)).save(p, "WEBP", quality=86, method=4)
    print(f"  wrote albedo_ref.webp {W} x {H}, {os.path.getsize(p) / 1e6:.2f} MB")
    np.save(os.path.join(ROOT, "reference", "s2global", "ref_month.npy"), frac.astype(np.float32))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stamp import stamp
    stamp()


def selftest():
    # a patch of June beside a patch of December across the date line of the year: the smoothed time of year stays
    # in winter or summer and never passes through spring by averaging 5 and 11 to 8
    m = np.full((40, 80), 11.0); m[:, :40] = 0.0                    # December | January
    f, _ = circular_smooth(m, np.ones_like(m), 3.0)
    assert ((f > 10.9) | (f < 0.1) | ((f > 11) & (f < 12))).all() and not ((f > 2) & (f < 9)).any(), (f.min(), f.max())
    # weights: 6.25 is three quarters July (index 6) and a quarter August
    w = blend_weights(np.array([[6.25, 11.5]]))
    assert abs(w[6, 0, 0] - 0.75) < 1e-6 and abs(w[7, 0, 0] - 0.25) < 1e-6 and abs(w[11, 0, 1] - 0.5) < 1e-6 and abs(w[0, 0, 1] - 0.5) < 1e-6 and np.allclose(w.sum(0), 1)
    # unweighted cells do not vote
    m = np.zeros((20, 40)); m[:, 20:] = 6.0
    wt = np.zeros_like(m); wt[:, :20] = 1
    f, reach = circular_smooth(m, wt, 2.0)
    assert (np.minimum(f, 12 - f)[reach > 1e-3] < 0.05).all()
    print("  ok   season_ref selftest: months average round the year, not across it; two months either side; unfitted cells do not vote")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
