"""The colour table for Sentinel-2 cloudless (register A13): what a value in that picture is, on the atlas's own scale.

Close in (a texel finer than 0.45 km) the ground's picture is Sentinel-2 cloudless 2016 (EOX). Until release 1.7 it
was joined to the shipped month in Blue Marble's DISPLAY values and read through Blue Marble's albedo table: every
texel took Blue Marble's 5 km colour, and a city, which Blue Marble shows olive and Sentinel-2 photographs grey, was
khaki from edge to edge. This file fits the table that reads Sentinel-2's picture directly.

THE MODEL. Sentinel-2 cloudless is a photograph: white-balanced, tone-mapped, with the air's haze largely in it.
The atlas draws the ground from an albedo and puts its own air over it. So the picture is read as SCENE LIGHT, the
light the atlas would send to the camera, and the albedo is whatever gives that light through the atlas's own air:

    scene_c  = S2_GAIN_c * curve(picture_c)            one tone curve for the three channels, three gains
    albedo_c = (scene_c - AIR_I_c) / AIR_LT_c           the atlas's air at a standard Sun, taken out again

AIR_LT and AIR_I are not fitted: they are the shader's own lighting and atmosphere (earth.frag.glsl) evaluated for
ground at sea level, the Sun 30 degrees from the zenith, seen straight down, which is how Sentinel-2 sees the
mid-latitudes in summer. `standard_air()` computes them from the constants in the shader's source, and
audit_closecolour.py fails if the copies in the shader drift from it.

The curve and the gains ARE fitted, against the atlas's own scale: Blue Marble through its table (itself fitted to
NASA EPIC, land_transfer.py), on 20 km cells of land. Sentinel-2's season is not known cell by cell, so each cell
is compared with the month of Blue Marble it is most like, twice over. A grey value in the picture comes out grey
on the screen at the standard Sun by construction (one curve); the gains carry what is left, that Blue Marble's
land is a little warmer than Sentinel-2's.

    ./venv/bin/python Research/modeling/s2_transfer.py --fetch     # the picture at level 4 (512 tiles from EOX, 8 MB), once
    ./venv/bin/python Research/modeling/s2_transfer.py             # fit; prints the GLSL constants and the residuals
    ./venv/bin/python Research/modeling/s2_transfer.py --selftest

The picture lands in reference/s2global/ (ignored by git). EOX is a host the page already asks.
"""
from __future__ import annotations

import math
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "reference", "s2global")
SHADER = os.path.join(ROOT, "web", "shaders", "earth.frag.glsl")
KNOTS = np.linspace(0, 1, 9)
LUMA = np.array([0.2126, 0.7152, 0.0722])
SUN_ZENITH = 30.0


# ------------------------------------------------------------------------------- the shader's own constants
def shader_source():
    with open(SHADER) as fh:
        return fh.read()


def const_vec3(src, name):
    m = re.search(rf"const vec3 {name} = vec3\(([^)]*)\)", src)
    if not m:
        raise RuntimeError(f"earth.frag.glsl has no const vec3 {name}")
    return np.array([float(v) for v in m.group(1).split(",")])


def const_float(src, name):
    m = re.search(rf"const float {name} = ([0-9.eE+-]+)", src)
    if not m:
        raise RuntimeError(f"earth.frag.glsl has no const float {name}")
    return float(m.group(1))


def const_table(src, name, n):
    m = re.search(rf"const vec3 {name}\[{n}\] = vec3\[\]\((.*?)\);", src, re.S)
    if not m:
        raise RuntimeError(f"earth.frag.glsl has no const vec3 {name}[{n}]")
    t = np.array([[float(v) for v in t.split(",")] for t in re.findall(r"vec3\(([^)]*)\)", m.group(1))])
    assert t.shape == (n, 3), t.shape
    return t


def const_floats(src, name, n):
    m = re.search(rf"const float {name}\[{n}\] = float\[\]\(([^)]*)\)", src)
    if not m:
        raise RuntimeError(f"earth.frag.glsl has no const float {name}[{n}]")
    t = np.array([float(v) for v in m.group(1).split(",")])
    assert t.shape == (n,), t.shape
    return t


def standard_air(src=None, zenith=SUN_ZENITH):
    """(LT, I): scene = albedo * LT + I, by the shader's land lighting and its air, for sea-level ground with no
    cloud, the Sun `zenith` degrees from the zenith, seen straight down. Mirrors main() in earth.frag.glsl."""
    src = src or shader_source()
    TAU_R, TAU_A, SKY_L, TRANS_K = (const_vec3(src, n) for n in ("TAU_R", "TAU_A", "SKY_L", "TRANS_K"))
    SUN_E, AIR_MS, AER_W, ABOVE, LAND_LS = (const_float(src, n) for n in ("SUN_E", "AIR_MS", "AER_W", "AIR_ABOVE_HAZE", "LAND_LS"))
    mu0 = math.cos(math.radians(zenith))

    def airmass(mu):
        return 1 / (mu + 0.50572 * (6.07995 + math.degrees(math.asin(mu))) ** -1.6364)

    def hg(g, c):
        return (1 - g * g) / (1 + g * g - 2 * g * c) ** 1.5

    trans = np.exp(-TRANS_K * (1 / (mu0 + 0.055) - 0.948))
    rough = (1 - LAND_LS) + LAND_LS * 2 / (mu0 + 1 + 1e-3)
    light = SUN_E * trans * mu0 * rough + SKY_L
    amV, amS, cSV = airmass(1.0), airmass(mu0), mu0
    inscat = SUN_E * (amV / (amV + amS)) * (AIR_MS * 0.1875 * (1 + cSV * cSV) * (1 - np.exp(-TAU_R * (amV + amS)))
                                            + AER_W * 0.25 * (0.9 * hg(0.75, -cSV) + 0.1 * hg(-0.3, -cSV)) * (1 - np.exp(-TAU_A * (amV + amS))) * np.exp(-TAU_R * ABOVE * (amV + amS)))
    through = np.exp(-(TAU_R * 0.6 + TAU_A * 0.3) * (amV + 1))
    return light * through, inscat


def bm_albedo(c, lut):
    """Blue Marble's display values (..., 3) in 0..1 to albedo: albedoOf() in the shader, the snow branch excepted."""
    out = np.empty_like(c, dtype=np.float64)
    for k in range(3):
        out[..., k] = np.interp(c[..., k], KNOTS, lut[:, k])
    return out


def s2_scene(c, curve, gain):
    return np.interp(c, KNOTS, curve) * gain


def s2_albedo(c, curve, gain, LT, I):
    return np.maximum((s2_scene(c, curve, gain) - I) / LT, 0.004)


# ------------------------------------------------------------------------------------------------ the data
def fetch():
    import requests
    from PIL import Image
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(os.path.join(REF, "tiles"), exist_ok=True)
    S = requests.Session(); S.headers["User-Agent"] = "python-requests"
    Z = 4

    def get(rc):
        r, c = rc
        p = os.path.join(REF, "tiles", f"{Z}_{r}_{c}.jpg")
        if not os.path.exists(p):
            q = S.get(f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless/default/WGS84/{Z}/{r}/{c}.jpg", timeout=120)
            if q.status_code != 200:
                raise RuntimeError(f"tile {rc}: HTTP {q.status_code}")
            with open(p, "wb") as fh:
                fh.write(q.content)
        return np.array(Image.open(p).convert("RGB"))

    jobs = [(r, c) for r in range(2 ** Z) for c in range(2 ** (Z + 1))]
    out = np.zeros((2 ** Z * 256, 2 ** (Z + 1) * 256, 3), np.uint8)
    with ThreadPoolExecutor(8) as ex:
        for (r, c), a in zip(jobs, ex.map(get, jobs)):
            out[r * 256:(r + 1) * 256, c * 256:(c + 1) * 256] = a
    np.save(os.path.join(REF, "s2_z4.npy"), out)
    print(f"  wrote reference/s2global/s2_z4.npy {out.shape}")


def load():
    """Sentinel-2 and the twelve shipped months on 20 km cells, and which cells are land to fit on."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    p = os.path.join(REF, "s2_z4.npy")
    if not os.path.exists(p):
        raise RuntimeError("reference/s2global/s2_z4.npy is missing: run s2_transfer.py --fetch")
    small = lambda im: np.array(im.resize((2048, 1024), Image.BOX)).astype(np.float32) / 255
    s2 = small(Image.fromarray(np.load(p)))
    bm = np.stack([small(Image.open(os.path.join(ROOT, "web", "fields", f"albedo_{m:02d}.webp")).convert("RGB")) for m in range(1, 13)])
    wat = small(Image.open(os.path.join(ROOT, "web", "fields", "water.webp")).convert("L"))
    lat = 90 - (np.arange(1024) + 0.5) * 180 / 1024
    land = (wat < 0.02) & (bm.min(-1).max(0) < 0.6) & (np.abs(lat)[:, None] < 65)      # no water in the cell, never snow, both pictures have it
    return s2, bm, land


# ------------------------------------------------------------------------------------------------- the fit
def _hat(x):
    B = np.zeros((len(x), 9))
    t = np.clip(x, 0, 1) * 8
    i = np.minimum(t.astype(int), 7)
    f = t - i
    B[np.arange(len(x)), i] = 1 - f
    B[np.arange(len(x)), i + 1] += f
    return B


def fit_curve(x, y, w, smooth=6.0):
    """A rising piecewise-linear curve on KNOTS through points (x, y) with weights w: least squares on the
    increments (each >= 0), second differences penalised so knots the data does not reach follow their neighbours."""
    from scipy.optimize import lsq_linear
    C = np.tril(np.ones((9, 9)))
    A = np.vstack([(_hat(x) @ C) * w[:, None], smooth * (np.diff(np.eye(9), 2, axis=0) @ C)])
    b = np.concatenate([y * w, np.zeros(7)])
    return C @ lsq_linear(A, b, bounds=(0, np.inf)).x


def binned(x, y, bins=64, least=40):
    """Medians of y in bins of x (the last bin, where the picture clips, left out): (x mean, y median, weight)."""
    e = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(x, e) - 1, 0, bins - 1)
    out = []
    for i in range(bins - 1):
        m = idx == i
        if m.sum() > least:
            out.append((x[m].mean(), np.median(y[m]), min(m.sum(), 2000) ** 0.5))
    return out


def fit(s2, bm, land, lut, LT, I, passes=3, log=print):
    scene_bm = bm_albedo(bm, lut) * LT + I                         # 12 months of scene light by the atlas's own table
    ref = scene_bm.mean(0)
    gain = np.ones(3)
    curve = None
    for it in range(passes):
        # the curve, with the gains as they stand: all three channels pooled
        pts = [p for k in range(3) for p in binned(s2[..., k][land], ref[..., k][land] / gain[k])]
        x, y, w = (np.array(v) for v in zip(*pts))
        curve = fit_curve(x, y, w)
        # the gains, with the curve as it stands: the median ratio per channel, green held at 1
        r = np.array([np.median(ref[..., k][land] / np.interp(s2[..., k][land], KNOTS, curve)) for k in range(3)])
        gain = r / r[1]
        curve = curve * r[1]
        # the month each cell is most like, for the next pass
        mine = s2_scene(s2, curve, gain)
        best = np.abs(np.log(scene_bm / mine[None])).sum(-1).argmin(0)
        ref = np.take_along_axis(scene_bm, best[None, ..., None], 0)[0]
        log(f"  pass {it}: gain {gain.round(3)}  curve {curve.round(3)}")
    return curve, gain, ref


def residuals(s2, ref, land, curve, gain):
    """The fit's error in scene light, per channel: (median ratio, share of cells within 10%)."""
    mine = s2_scene(s2, curve, gain)
    out = []
    for k in range(3):
        r = mine[..., k][land] / ref[..., k][land]
        out.append((float(np.median(r)), float((np.abs(r - 1) < 0.10).mean())))
    return out


def glsl(curve, gain, LT, I):
    f = lambda a: ", ".join(f"{v:.3f}" for v in a)
    return (f"const float S2_CURVE[9] = float[]({f(curve)});\n"
            f"const vec3 S2_GAIN = vec3({f(gain)});\n"
            f"const vec3 AIR_LT = vec3({f(LT)});\n"
            f"const vec3 AIR_I = vec3({f(I)});")


def selftest():
    # 1. the fit recovers a known curve and known gains from made-up cells, and a grey comes out grey on the screen
    rng = np.random.default_rng(3)
    true_curve = 0.06 + 0.36 * KNOTS ** 1.2
    true_gain = np.array([1.06, 1.0, 0.9])
    LT, I = np.array([1.3, 1.25, 1.1]), np.array([0.03, 0.055, 0.10])
    lut = np.stack([KNOTS * 0.5, KNOTS * 0.5, KNOTS * 0.5], 1)
    n = 20000
    pic = rng.uniform(0.05, 0.98, (n, 3))
    scene = s2_scene(pic, true_curve, true_gain) * rng.normal(1, 0.03, (n, 3))
    alb = np.clip((scene - I) / LT, 0, 0.499)
    bm = np.repeat((alb / 0.5)[None, :, None, :], 12, 0).astype(np.float32)          # Blue Marble values whose albedo by `lut` is alb
    s2 = pic[:, None, :].astype(np.float32)
    land = np.ones((n, 1), bool)
    curve, gain, _ = fit(s2, bm, land, lut, LT, I, log=lambda *_: None)
    got = s2_scene(np.full(3, 0.5), curve, gain)
    want = s2_scene(np.full(3, 0.5), true_curve, true_gain)
    assert np.abs(got / want - 1).max() < 0.03, (got, want)
    assert np.abs(gain - true_gain).max() < 0.03, gain
    assert np.all(np.diff(curve) >= 0), curve
    # 2. albedo and scene are inverses through the air
    a = s2_albedo(np.array([0.7, 0.7, 0.7]), curve, np.ones(3), LT, I)
    s = a * LT + I
    assert np.abs(s / s[1] - 1).max() < 1e-9, s                                      # one curve, unit gains: grey stays grey
    # 3. the standard air reads the shader and is in a sane range: blue is scattered most and passed least
    LT, I = standard_air()
    assert I[2] > I[1] > I[0] > 0 and LT[0] > LT[1] > LT[2] > 0.8, (LT, I)
    print("  ok   s2_transfer selftest: curve and gains recovered within 3%; grey stays grey; the standard air reads the shader")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--fetch" in sys.argv:
        return fetch()
    src = shader_source()
    LT, I = standard_air(src)
    lut = const_table(src, "ALB_LUT", 9)
    s2, bm, land = load()
    print(f"  {int(land.sum())} cells of land; the atlas's air at a {SUN_ZENITH:.0f} degree Sun: LT {LT.round(3)}  I {I.round(3)}")
    curve, gain, ref = fit(s2, bm, land, lut, LT, I)
    for n, (med, within) in zip("RGB", residuals(s2, ref, land, curve, gain)):
        print(f"  {n}: Sentinel-2 by the table over Blue Marble by its own, in scene light: median {med:.3f}, {within * 100:.0f}% of cells within 10%")
    print("\n" + glsl(curve, gain, LT, I))


if __name__ == "__main__":
    main()
