#!/usr/bin/env python3
"""Cloud grain: the fine structure of real cloud, as three tileable ORDERING fields (register B1).

    ./venv/bin/python build/fetch_sources.py cloudtex      # three VIIRS scenes from NASA GIBS, 8 MB
    ./venv/bin/python build/cloud_grain.py                  # -> web/fields/cloudgrain.jpg (1024 x 1024, RGB)
    ./venv/bin/python build/cloud_grain.py --preview        # also scratchpad/cloudgrain_preview.jpg
    ./venv/bin/python build/cloud_grain.py --selftest

Why it exists. Closer than about 10 km a pixel the atlas knows how MUCH cloud there is and has no record
of its shape, so it generated one from noise, and three versions in a row looked like pepper, cracked mud
and confetti. Real cloud is not noise: it has cells, fibres, streets and ragged edges. This step takes
those from photographs.

What an ordering field is. Take a real cloud scene at 2 km a pixel and replace each pixel's brightness by
its RANK, 0 to 1, among its neighbours. The field then answers one question exactly: "if cloud covered a
share p of this sky, WHICH pixels would it be?" - those ranked above 1 - p. The shader asks that with its
own p (from the cloud climatology and the far-field photograph), so amount still comes from observation
of amount, and shape now comes from observation of shape. A rank field is uniform by construction, so a
cut at 1 - p covers p: no quantile curve to measure, and the mean does not move with zoom.

Three scenes, three kinds of cloud, one channel each:

    R  sheet      stratocumulus, closed and open cells         (Namibian deck)
    G  cumulus    shallow broken cumulus over open sea          (southern Indian Ocean trades)
    B  frontal    layered and fibrous cloud of a mid-latitude storm, with its broken edges (Southern Ocean)

None is one of the fifteen scenes the texture audit scores against (Research/modeling/cloud_texture.py):
different oceans, a different year. A match made by construction would not be evidence.

The scenes are made periodic (opposite edges cross-faded, keeping contrast) because the shader tiles them,
2048 km to a tile. Where a scene is clear sea, brightness says nothing about order, so order there comes
from distance to the nearest cloud: cloud grows outward from where it is as the share rises.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "data", "cloudtex")
OUT = os.path.join(ROOT, "web", "fields", "cloudgrain.jpg")
PX, KM = 1024, 2.0
OVERLAP = 224                      # the scenes are fetched PX + OVERLAP wide: the tile, and what its edges fade over
LUMA = np.array([0.2126, 0.7152, 0.0722])
# channel: (file, window km of the local rank, share of the rank that is local)
SCENES = {
    "sheet": ("sheet_2023-09-05.png", 240.0, 0.75),
    "cumulus": ("cumulus_2023-08-03.png", 400.0, 0.45),
    "frontal": ("frontal_2023-01-22.png", 200.0, 0.80),
}
# GIBS corrected reflectance: reflectance x 255 goes through this table to the picture (as cloud_texture.py)
_GX = np.array([0, 30, 60, 120, 190, 255.0]); _GY = np.array([0, 110, 160, 210, 240, 255.0])


def reflectance(path):
    img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    assert img.shape[:2] == (PX + OVERLAP, PX + OVERLAP), f"{path}: {img.shape}"
    rgb = np.interp(img, _GY, _GX) / 255.0
    # cloud is white; land and sunglint are not. Taking the dimmest channel keeps cloud and drops most of the rest.
    return rgb.min(-1)


def periodic(r, overlap=OVERLAP):
    """Cross-fade opposite edges over `overlap` pixels so the field tiles; returns the tile, `overlap` smaller
    each way and at the scene's own scale. The fade is variance-preserving: a plain average of two unrelated
    strips halves their contrast and leaves a soft band along every seam."""
    def fade(a):
        n = a.shape[1]
        core = a[:, overlap:n].copy()                      # width n - overlap: the tile
        left, right = a[:, :overlap], core[:, -overlap:]    # the strip just before the tile, and the tile's own end
        w = np.linspace(0, 1, overlap, dtype=np.float32)[None, :]
        w = w * w * (3 - 2 * w)
        m = np.mean(right) * (1 - w) + np.mean(left) * w
        blend = m + ((right - np.mean(right)) * (1 - w) + (left - np.mean(left)) * w) / np.sqrt((1 - w) ** 2 + w ** 2)
        core[:, -overlap:] = blend                         # the end now runs into what precedes the start
        return core
    return fade(fade(r).T).T


def rank01(x):
    order = np.argsort(x, axis=None, kind="stable")
    r = np.empty(x.size, dtype=np.float32)
    r[order] = (np.arange(x.size, dtype=np.float32) + 0.5) / x.size
    return r.reshape(x.shape)


def ordering(r, window_km, local_share):
    """Rank field of a periodic reflectance field: `local_share` of it among neighbours within about
    `window_km`, the rest among the whole tile, then made exactly uniform."""
    # clear sea carries no order of its own: lend it the cloud's, spread outward at three widths
    # (and below reflectance 0.05 there is only the sea and the picture's own coding blocks: no order is taken from it)
    r = np.clip(r - 0.05, 0, None)
    e = r + 0.20 * ndi.gaussian_filter(r, 3, mode="wrap") + 0.12 * ndi.gaussian_filter(r, 10, mode="wrap") + 0.06 * ndi.gaussian_filter(r, 30, mode="wrap")
    e = e + 1e-4 * np.random.default_rng(7).random(e.shape, dtype=np.float32)       # break exact ties the same way every build
    g = rank01(e)
    # local rank: at K levels, the share of the neighbourhood below that level; then read off at the pixel's own level
    K = 48
    levels = np.quantile(e, (np.arange(K) + 0.5) / K)
    sig = window_km / KM / 2.355
    below = np.stack([ndi.gaussian_filter((e < L).astype(np.float32), sig, mode="wrap") for L in levels])   # K x H x W
    pos = np.clip(g * K - 0.5, 0, K - 1.001)                # where the pixel's own level falls among the K
    i = np.floor(pos).astype(int); f = pos - i
    yy, xx = np.mgrid[0:e.shape[0], 0:e.shape[1]]
    loc = below[i, yy, xx] * (1 - f) + below[i + 1, yy, xx] * f
    return rank01(local_share * loc + (1 - local_share) * g)


def build():
    out = {}
    for name, (f, win, share) in SCENES.items():
        p = os.path.join(SRC, f)
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}; run build/fetch_sources.py cloudtex")
        r = periodic(reflectance(p))
        out[name] = (r, ordering(r, win, share))
    return out


# kind: (m0, ratio). m0 is the mean reflectance of the cloudy part of a broken field; ratio is the brightest
# core over that mean in the shader's rule, which draws a piece as peak * t^k: it is 1 + k, with k chosen so
# the rule has the photographs' own spread (standard deviation over mean) of cloudy reflectance.
# MEASURED on the eighteen candidate scenes of 2023 (cloudy = dimmest channel above 0.12), none of them a
# scene the texture audit scores against:
#   sheets            mean 0.27-0.36, spread 0.34-0.41  ->  k 0.5
#   shallow cumulus   mean 0.31-0.40, spread 0.46-0.53  ->  k 0.8
#   storm cloud       mean 0.39-0.50, spread 0.38-0.44  ->  k 0.6
# (The audit's own Amazon and Congo scenes are wider still, 0.55-0.63; they are not used here.)
# The shader holds the same numbers.
KIND = {"sheet": (0.35, 1.5), "cumulus": (0.33, 1.8), "frontal": (0.45, 1.6)}


def pieces(r, a, m0, ratio, cmax=0.96):
    """The shader's rule, in numpy: cloud whose light averaged over all the sky is a. It covers a / m0 of the
    sky until that is all of it; a piece brightens from its edge to its core as the rank does."""
    p = np.clip(a / m0, 0.02, 1.0)
    m = min(a / p, cmax)
    peak = min(cmax, m * ratio)
    t = np.clip((r - (1 - p)) / p, 0, 1)
    return peak * t ** (peak / m - 1.0)


def checks(fields):
    for name, (r, o) in fields.items():
        h = np.histogram(o, bins=20, range=(0, 1))[0] / o.size
        assert np.abs(h - 0.05).max() < 0.002, (name, h)
        # it tiles: the step across the wrap is like a step inside (two unrelated edges would differ by 1/3, six times that)
        inside = np.abs(np.diff(o, axis=1)).mean(); wrap = np.abs(o[:, 0] - o[:, -1]).mean()
        inside_y = np.abs(np.diff(o, axis=0)).mean(); wrap_y = np.abs(o[0, :] - o[-1, :]).mean()
        assert wrap < 2.0 * inside and wrap_y < 2.0 * inside_y, (name, inside, wrap, inside_y, wrap_y)
        # order follows the photograph: the top fifth by rank is brighter than the bottom fifth
        assert r[o > 0.8].mean() > r[o < 0.2].mean() + 0.03, name
        # a cut at 1 - p covers p, and the pieces average to the reflectance asked for
        for a in (0.05, 0.15, 0.30, 0.60, 0.85):
            c = pieces(o, a, *KIND[name])
            p = min(1.0, a / KIND[name][0])
            assert abs((c > 0).mean() - p) < 0.01 and abs(c.mean() - a) < 0.01, (name, a, (c > 0).mean(), c.mean())
        print(f"  {name:8} scene cloud share (reflectance > 0.30) {float((r > 0.3).mean()):.2f}; rank uniform within {np.abs(h - 0.05).max():.4f}; wrap step {wrap / inside:.2f}, {wrap_y / inside_y:.2f} of an inside step")


def write(fields):
    rgb = np.stack([np.clip(fields[k][1] * 255.0, 0, 255).astype(np.uint8) for k in ("sheet", "cumulus", "frontal")], -1)
    # JPEG at full chroma resolution. The three channels are unrelated fields: WebP's lossy coder halves the
    # chroma resolution and cost 4.5% of the rank range; this costs under 2.5%.
    Image.fromarray(rgb).save(OUT, quality=93, subsampling=0)
    back = np.asarray(Image.open(OUT).convert("RGB"), dtype=np.float32) / 255.0
    err = float(np.abs(back - rgb / 255.0).mean())
    assert err < 0.025, err
    for c, k in enumerate(("sheet", "cumulus", "frontal")):               # still uniform after coding: a cut at 1 - p covers p
        for p_ in (0.1, 0.3, 0.5, 0.8):
            got = float((back[..., c] > 1 - p_).mean())
            assert abs(got - p_) < 0.012, (k, p_, got)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {os.path.getsize(OUT) / 1e3:.0f} kB, mean coding error {err:.3f} of the rank range")


def preview(fields):
    """Each scene as photographed, then drawn by the shader's rule at three amounts of light (0.06, 0.18, 0.40)."""
    rows = []
    for name, (r, o) in fields.items():
        tiles = [np.clip(r / 0.9, 0, 1)] + [pieces(o, a, *KIND[name]) for a in (0.06, 0.18, 0.40)]
        rows.append(np.concatenate([np.roll(t, (PX // 2, PX // 2), (0, 1))[256:768, 128:896] for t in tiles], 1))   # rolled: the wrap seam crosses the middle
    im = np.concatenate(rows, 0)
    sea = np.array([0.03, 0.06, 0.12]); white = np.array([1.0, 1.0, 1.0])
    pic = sea + (white - sea) * im[..., None]
    p = os.path.join(ROOT, "scratchpad", "cloudgrain_preview.jpg")
    Image.fromarray((np.clip(pic, 0, 1) ** (1 / 1.8) * 255).astype(np.uint8)).save(p, quality=88)
    print("preview:", p)


def selftest():
    rng = np.random.default_rng(1)
    # 1. periodic(): a ramp has the worst possible seam; after it the wrap step is an inside step
    n = PX + OVERLAP
    f = ndi.gaussian_filter(rng.random((n, n), dtype=np.float32), 4) * 6 + np.mgrid[0:n, 0:n][1].astype(np.float32) / n
    q = periodic(f)
    assert q.shape == (PX, PX) and np.abs(q[:, 0] - q[:, -1]).mean() < 1.6 * np.abs(np.diff(q, axis=1)).mean()
    yy, xx = np.mgrid[0:PX, 0:PX].astype(np.float32)
    # 2. ordering(): uniform, and it keeps the order of a field that is already homogeneous
    g = ndi.gaussian_filter(rng.random((PX, PX), dtype=np.float32), 6, mode="wrap")
    o = ordering(g, 200.0, 0.5)
    assert np.abs(np.histogram(o, bins=10, range=(0, 1))[0] / o.size - 0.1).max() < 0.002
    assert np.corrcoef(o.ravel(), rank01(g).ravel())[0, 1] > 0.9
    # 3. the local part does what it is for: add a tile-wide swell (periodic, three standard deviations high)
    #    and a cut still covers every quarter of the tile nearly alike; ranked over the whole tile it does not
    swell = g + 3.0 * g.std() * np.sin(2 * np.pi * xx / PX)
    spread = lambda o_: (lambda q: max(q) - min(q))([(o_[:, i * 256:(i + 1) * 256] > 0.7).mean() for i in range(4)])
    s_loc, s_glob = spread(ordering(swell, 200.0, 1.0)), spread(ordering(swell, 200.0, 0.0))
    assert s_loc < 0.10 and s_glob > 3 * s_loc, (s_loc, s_glob)
    # 4. pieces(): share and mean
    c = pieces(o, 0.15, 0.35, 1.5)
    assert abs((c > 0).mean() - 0.15 / 0.35) < 0.01 and abs(c.mean() - 0.15) < 0.005
    print("cloud_grain selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); sys.exit(0)
    F = build()
    checks(F)
    if a.preview:
        preview(F)
    write(F)
    from stamp import stamp          # the file's URL does not change when its bytes do: the stamp is what reloads it
    print("data version:", stamp())
