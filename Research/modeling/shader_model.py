"""The Space style's light model in numpy: the same arithmetic as web/shaders/earth.frag.glsl for a
cloud-free pixel of land or deep water. Audits invert it (what albedo does EPIC imply here?) and fit
it (what exposure puts a deep convective cloud where EPIC puts it?).

It is a second copy of the shader, which is exactly what an audit should not trust. So every user of
this file first runs `check_against_render`: rebuild the atlas's own clouds-off render from the
shipped fields and compare. If the copy has drifted from the shader, that check says so in display
levels before any conclusion is drawn.

Constants are read out of the shader source by name; a constant renamed there fails loudly here.
"""
from __future__ import annotations

import os
import re

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SHADER = os.path.join(ROOT, "web", "shaders", "earth.frag.glsl")


def consts(path=SHADER):
    src = open(path).read()

    def f(name):
        m = re.search(rf"const float [^;]*\b{name} = ([-\d.e]+)", src)
        if not m:
            raise SystemExit(f"shader_model: constant {name} not found in {path}")
        return float(m.group(1))

    def v(name):
        m = re.search(rf"const vec3 {name} = vec3\(([^)]+)\)", src)
        if not m:
            raise SystemExit(f"shader_model: constant {name} not found in {path}")
        return np.array([float(x) for x in m.group(1).split(",")])

    m = re.search(r"const vec3 ALB_LUT\[(\d+)\] = vec3\[\]\(([^;]+)\);", src, re.S)
    lut = np.array([[float(x) for x in t.split(",")] for t in re.findall(r"vec3\(([^)]+)\)", m.group(2))]) if m else None
    return dict(TAU_R=v("TAU_R"), TAU_A=v("TAU_A"), AIR_ABOVE_HAZE=f("AIR_ABOVE_HAZE"), SUN_E=f("SUN_E"), AIR_MS=f("AIR_MS"), AER_W=f("AER_W"),
                SKY=v("SKY_L"), TRANS_K=v("TRANS_K"), SEA_DEEP=v("SEA_DEEP"), SKY_REF=v("SKY_REF"),
                EXPO=f("EXPO"), GAMMA=f("GAMMA"), KNEE=f("KNEE"), SNOW_ALB=f("SNOW_ALB"), LAND_LS=f("LAND_LS"), ALB_LUT=lut)


def airmass(mu):
    h = np.degrees(np.arcsin(np.clip(mu, 0, 1)))
    return 1.0 / (np.maximum(mu, 0) + 0.50572 * (6.07995 + h) ** -1.6364)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def hg(g, c):
    return (1 - g * g) / (1 + g * g - 2 * g * c) ** 1.5


def aerosol_phase(c):
    """Per unit of scattering, same convention as the Rayleigh (3/16)(1+cos^2): P / 4."""
    return 0.25 * (0.9 * hg(0.75, c) + 0.1 * hg(-0.3, c))


def display(c, K):
    s = np.maximum(c, 0) * K["EXPO"]
    k = K["KNEE"]
    s = np.where(s > k, k + (1 - k) * np.tanh((s - k) / (1 - k)), s)
    return 255 * s ** (1 / K["GAMMA"])


def from_display(d, K):
    s = (np.clip(d, 0, 254.5) / 255) ** K["GAMMA"]
    k = K["KNEE"]
    s = np.where(s > k, k + (1 - k) * np.arctanh(np.clip((s - k) / (1 - k), 0, 0.9999)), s)
    return s / K["EXPO"]


def decode_albedo(v, K):
    """8-bit Blue Marble value -> albedo, as albedoOf() in the shader: a per-channel table, linear between knots."""
    lut = K["ALB_LUT"]
    if lut is None or not lut.any():
        return (v / 255.0) ** 2.2
    n = len(lut) - 1
    x = np.clip(v / 255.0, 0, 1) * n
    i = np.clip(np.floor(x).astype(int), 0, n - 1); f = x - i
    out = np.empty_like(v, dtype=np.float64)
    for c in range(3):
        out[..., c] = lut[i[..., c], c] * (1 - f[..., c]) + lut[i[..., c] + 1, c] * f[..., c]
    snow = smoothstep(0.80, 0.96, v.min(-1) / 255.0)[..., None]
    return out * (1 - snow) + K["SNOW_ALB"] * snow


def light(mu0, muv, cos_sv, K, z=0.0):
    """Sun and sky on the ground, the two-way loss through the air, and the air's own light.
    A cloud-free pixel is  surface * through + inscat  where surface is in the Sun's units.
    cos_sv is dot(Sun, view) with view pointing from the ground to the camera, as in the shader:
    +1 when the camera sits in the Sun's direction, which is a scattering angle of 180 degrees."""
    mu0 = np.asarray(mu0)[..., None]; muv = np.asarray(muv)[..., None]; c = np.asarray(cos_sv)[..., None]
    trans = np.exp(-K["TRANS_K"] * (1 / (np.maximum(mu0, 0) + 0.055) - 0.948))
    sunL = K["SUN_E"] * trans * np.maximum(mu0, 0)
    skyL = K["SKY"] * smoothstep(-0.20, 0.30, mu0)
    zz = np.maximum(np.asarray(z, dtype=float), 0)[..., None] if np.ndim(z) else max(z, 0.0)
    tau = K["TAU_R"] * np.exp(-zz / 8000.0)
    tauA = K["TAU_A"] * np.exp(-zz / 2000.0)
    amV, amS = airmass(muv), airmass(mu0)
    geo = amV / (amV + amS)
    ins = K["SUN_E"] * geo * (K["AIR_MS"] * 0.1875 * (1 + c * c) * (1 - np.exp(-tau * (amV + amS)))
                              + K["AER_W"] * aerosol_phase(-c) * (1 - np.exp(-tauA * (amV + amS))) * np.exp(-tau * K["AIR_ABOVE_HAZE"] * (amV + amS)))
    through = np.exp(-(tau * 0.6 + tauA * 0.3) * (amV + 1.0))
    rough = np.minimum((1 - K["LAND_LS"]) + K["LAND_LS"] * 2.0 / (np.maximum(mu0, 0) + np.maximum(muv, 0) + 1e-3), 1.8)
    return dict(sunL=sunL, skyL=skyL, through=through, rough=rough, inscat=ins * smoothstep(-0.10, 0.02, mu0))


def land_gain(L):
    """What multiplies the albedo in a land pixel: Sun (with the rough-ground factor) and sky, through the air."""
    return (L["sunL"] * L["rough"] + L["skyL"]) * L["through"]


def land_scene(alb, L):
    return alb * land_gain(L) + L["inscat"]


def sea_scene(muv, L, K):
    """Deep open water away from the glint: water-leaving light and the reflected sky."""
    fres = 0.02 + 0.98 * (1 - np.clip(np.asarray(muv), 0, 1)[..., None]) ** 5
    sea = K["SEA_DEEP"] * (L["sunL"] * 0.9 + L["skyL"] * 1.6) + fres * K["SKY_REF"] * 0.55
    return sea * L["through"] + L["inscat"]
