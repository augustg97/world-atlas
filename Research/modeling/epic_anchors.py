"""Fit the display transform to targets whose reflectance is known WITHOUT this atlas (register A1/A7).

Last round the exposure and gamma were fitted so that desert, ocean and bright cloud landed on EPIC's
display values. Two of those three were the atlas's own guesses: desert albedo was Blue Marble read as
sRGB, and "bright cloud" was a Lambert surface of albedo 1. The fit absorbed both errors. This one uses:

  deep convective cloud   the brightest 0.3% of the tropics near the disc centre. Reflectance 0.90
                          (the value satellite calibration assigns these targets; +-0.05).
  clear deep ocean        from the clear-sky composite (epic_clearsky.py), away from the glint. Its
                          brightness is Rayleigh scattering, computed, plus 1-2% from water and haze.
  Libya-4 (28.55N 23.39E) NOT fitted: the check. Top-of-atmosphere reflectance about 0.47 / 0.34 / 0.22
                          in red / green / blue (calibration-site literature, from memory: +-0.03).

    ./venv/bin/python Research/modeling/epic_anchors.py            # fit, report, and the check
"""
import json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epic_compare as E, epic_clearsky as C, shader_model as S  # noqa: E402

DCC_REFLECTANCE = 0.90
LIBYA4 = np.array([0.47, 0.34, 0.22])


def cloud_tops():
    """(display rgb, mu0) of the brightest 0.3% of tropical pixels near the disc centre, per frame."""
    out = []
    for fr in E.load_frames():
        g = E.disc_geometry(fr["lon"], fr["lat"], fr["dist"])
        A = E.to_common(Image.open(os.path.join(E.REF, fr["image"] + ".png")).convert("RGB"), fr["cx"], fr["cy"], fr["r"])
        mu0 = g["P"] @ E.unit(*E.sub_solar(fr))
        m = g["hit"] & (g["mu"] > 0.85) & (mu0 > 0.85) & (np.abs(g["lat"]) < 30)
        lum = A @ E.LUMA
        k = m & (lum >= np.percentile(lum[m], 99.7))
        out.append((A[k].mean(0), float(mu0[k].mean())))
    return out


def ocean(K):
    """Per composite frame: EPIC's clear-ocean display value (30th percentile: the composite still holds
    thin cloud) and the model's scene value for the same pixels."""
    index = json.load(open(os.path.join(C.CS, "index.json")))
    fd = {f["image"][8:]: f for f in E.load_frames()}
    out = []
    for n in index:
        ref = fd[n]; z = np.load(os.path.join(C.CS, f"composite_{n}.npz")); comp = z["comp"]
        g = E.disc_geometry(ref["lon"], ref["lat"], ref["dist"]); sun = E.unit(*E.sub_solar(ref)); mu0 = g["P"] @ sun
        water = np.where(g["hit"], E.sample_field("water.webp", g["lon"], g["lat"]), 0)
        deep = np.where(g["hit"], E.sample_field("elev.png", g["lon"], g["lat"]), 1) < 0.45      # high byte of elevation: deeper than about 2000 m
        H = sun - g["d"]; H /= np.linalg.norm(H, axis=-1, keepdims=True)
        m = g["hit"] & (water > 0.98) & deep & (g["mu"] > 0.8) & (mu0 > 0.8) & ~np.isnan(comp[..., 0]) & ((g["P"] * H).sum(-1) < 0.985) & (z["agree"] >= 6)
        L = S.light(mu0[m], g["mu"][m], -(g["d"][m] @ sun), K)
        out.append((np.percentile(comp[m], 30, 0), np.median(S.sea_scene(g["mu"][m], L, K), 0), n))
    return out


def libya(K):
    index = json.load(open(os.path.join(C.CS, "index.json")))
    fd = {f["image"][8:]: f for f in E.load_frames()}
    out = []
    for n in index:
        ref = fd[n]; comp = np.load(os.path.join(C.CS, f"composite_{n}.npz"))["comp"]
        g = E.disc_geometry(ref["lon"], ref["lat"], ref["dist"]); mu0 = g["P"] @ E.unit(*E.sub_solar(ref))
        m = g["hit"] & (np.abs(g["lon"] - 23.39) < 0.6) & (np.abs(g["lat"] - 28.55) < 0.6) & ~np.isnan(comp[..., 0])
        if m.sum() > 20 and mu0[m].mean() > 0.5:
            out.append((comp[m].mean(0), float(mu0[m].mean()), n))
    return out


def main():
    K = S.consts()
    tops, sea = cloud_tops(), ocean(K)
    d_top = np.array([t[0] @ E.LUMA for t in tops]); s_top = np.array([K["SUN_E"] * DCC_REFLECTANCE * t[1] for t in tops])
    d_sea = np.array([o[0] for o in sea]).ravel(); s_sea = np.array([o[1] for o in sea]).ravel()
    best = None
    for gamma in np.arange(1.30, 2.21, 0.01):
        for expo in np.arange(0.40, 1.001, 0.005):
            k = dict(K, EXPO=expo, GAMMA=gamma, KNEE=2.0)                    # no knee while fitting
            e1 = S.display(s_top, k) - d_top; e2 = S.display(s_sea, k) - d_sea
            err = np.sqrt((e1 ** 2).mean() + (e2 ** 2).mean())
            if best is None or err < best[0]:
                best = (err, expo, gamma, e1, e2)
    err, expo, gamma, e1, e2 = best
    print(f"fit: EXPO {expo:.3f}  GAMMA {gamma:.2f}   (shader has {K['EXPO']}, {K['GAMMA']})")
    print(f"  cloud tops: EPIC {d_top.mean():.0f}, model {(d_top + e1).mean():.0f}  (per-frame error {e1.round(0)})")
    kk = dict(K, EXPO=expo, GAMMA=gamma)
    print("  clear ocean, EPIC p30 against model, R G B per frame:")
    for o in sea:
        print(f"    {o[2]}  EPIC {o[0].round(0)}  model {S.display(o[1], kk).round(0)}")
    print(f"  rms {err:.1f} display levels")
    print("check, Libya-4 (not fitted): EPIC against a Lambert surface of the published reflectance")
    for d, mu0, n in libya(kk):
        print(f"    {n}  EPIC {d.round(0)}  model {S.display(K['SUN_E'] * LIBYA4 * mu0, kk).round(0)}   mu0 {mu0:.2f}")
    print("with the shader's present constants:")
    for d, mu0, n in libya(K):
        print(f"    {n}  Libya-4 EPIC {d.round(0)}  model {S.display(K['SUN_E'] * LIBYA4 * mu0, K).round(0)}")
    print(f"    cloud tops EPIC {d_top.mean():.0f} model {S.display(s_top, K).mean():.0f};  ocean EPIC {np.array([o[0] for o in sea]).mean(0).round(0)} model {np.array([S.display(o[1], K) for o in sea]).mean(0).round(0)}")


if __name__ == "__main__":
    main()
