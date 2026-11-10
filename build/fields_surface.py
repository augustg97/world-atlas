#!/usr/bin/env python3
"""Surface fields: water fraction, land reflectance x12, elevation, relief gradient, night
lights, cloud texture.   Sources in ../data (see fetch_sources.py), output in ../web/fields.

    ./venv/bin/python build/fields_surface.py                 # everything
    ./venv/bin/python build/fields_surface.py water albedo    # targeted
    ./venv/bin/python build/fields_surface.py albedo:7        # one month

Every output is canonical (frames.py): equirectangular, pixel-centre, row 0 north, -180 left.
BMNG, Black Marble and the cloud image are already in that frame; ETOPO is S->N and is flipped
by frames.reduce_aligned. Landmark assertions at the end of each step catch a flipped or
shifted product before it reaches the app.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

import frames as F

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "web", "fields")
CACHE = os.path.join(DATA, "_cache")
os.makedirs(OUT, exist_ok=True)
os.makedirs(CACHE, exist_ok=True)

W8, H8 = 8192, 4096
W4, H4 = 4096, 2048
OCEAN_FILL = np.array([2, 5, 20])          # measured: 58% of BMNG pixels are exactly this


def bmng(month: int) -> Image.Image:
    return Image.open(os.path.join(DATA, "bmng", f"world.2004{month:02d}.3x21600x10800.jpg")).convert("RGB")


def px(a, lon, lat):
    h, w = a.shape[:2]
    i, j = F.lonlat_to_px(lon, lat, w, h)
    return a[j, i]


def save_gray(a01: np.ndarray, name: str, quality: int = 90, lossless: bool = False):
    im = Image.fromarray(np.clip(a01 * 255.0 + 0.5, 0, 255).astype(np.uint8), "L")
    p = os.path.join(OUT, name)
    if name.endswith(".webp"):
        im.save(p, "WEBP", quality=quality, method=4, lossless=lossless)
    else:
        im.save(p, optimize=True)
    print(f"  wrote {name}  {os.path.getsize(p) / 1e6:.2f} MB")


# ---------------------------------------------------------------------------------------------
def step_water():
    """Water fraction at 8192: the ocean is BMNG's own constant fill colour, so the mask is
    registered to the imagery by construction. Inland water = dark water pixels."""
    print("water")
    a = np.asarray(bmng(7))
    d = np.abs(a.astype(np.int16) - OCEAN_FILL).max(axis=2)
    ocean = d <= 7
    lum = (a[..., 0] * 0.30 + a[..., 1] * 0.59 + a[..., 2] * 0.11)
    lake = (~ocean) & (lum < 13) & (a[..., 2] >= a[..., 0])     # dark and not red: open fresh water
    # polar night: July leaves Antarctica's interior valid, but guard anyway - no lakes poleward of 80
    lat = F.canon_lat(a.shape[0])[:, None]
    lake &= np.abs(lat) < 80
    del a, d, lum
    oc8 = F.reduce_aligned(ocean.astype(np.float32), W8, H8)
    lk8 = F.reduce_aligned(lake.astype(np.float32), W8, H8)
    np.save(os.path.join(CACHE, "ocean8.npy"), oc8.astype(np.float16))
    water = np.clip(oc8 + lk8, 0, 1)
    save_gray(water, "water.webp", quality=92)
    # 4096 copy for JS-side probing and for the human fields
    np.save(os.path.join(CACHE, "water4.npy"), F.reduce_aligned(water, W4, H4).astype(np.float16))
    assert px(water, -150, 0) > 0.99, "mid-Pacific must be water"
    assert px(water, 10, 23) < 0.01, "Sahara must be land"
    assert px(water, -87.5, 47.7) > 0.9, "Lake Superior must be water"
    assert px(water, 51, 42) > 0.9, "Caspian must be water"
    assert px(water, 90, -80) < 0.01, "Antarctica must be land"
    print(f"  ocean+lake fraction of the sphere: {(water * np.cos(np.radians(F.canon_lat(H8)))[:, None]).sum() / (np.cos(np.radians(F.canon_lat(H8))).sum() * W8):.4f} (Earth: ~0.71 ocean)")


def step_albedo(months):
    """Land reflectance, with land colour extended into the sea so that texture filtering at
    the coast never mixes in BMNG's ocean fill (the water field decides what is water)."""
    from scipy import ndimage
    print("albedo", months)
    idx_path = os.path.join(CACHE, "fill_idx8.npy")
    for m in months:
        a = np.asarray(bmng(m))
        land = (np.abs(a.astype(np.int16) - OCEAN_FILL).max(axis=2) > 7)
        cov = np.asarray(Image.fromarray((land * 255).astype(np.uint8), "L").resize((W8, H8), Image.LANCZOS), dtype=np.float32) / 255.0
        out = np.zeros((H8, W8, 3), np.float32)
        for c in range(3):
            pm = Image.fromarray(np.where(land, a[..., c], 0).astype(np.uint8), "L").resize((W8, H8), Image.LANCZOS)
            out[..., c] = np.asarray(pm, dtype=np.float32)
        del a, land
        valid = cov > 0.35
        out = np.where(valid[..., None], out / np.maximum(cov, 0.35)[..., None], 0.0)
        if not os.path.exists(idx_path):
            _, idx = ndimage.distance_transform_edt(~valid, return_indices=True)
            np.save(idx_path, idx.astype(np.int32))
        idx = np.load(idx_path)
        out = out[idx[0], idx[1]]                       # every sea pixel takes its nearest land colour
        im = Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")
        p = os.path.join(OUT, f"albedo_{m:02d}.webp")
        im.save(p, "WEBP", quality=86, method=4)
        p2 = os.path.join(OUT, f"albedo_{m:02d}_p.webp")
        im.resize((2048, 1024), Image.LANCZOS).save(p2, "WEBP", quality=80, method=4)
        print(f"  wrote albedo_{m:02d}.webp {os.path.getsize(p) / 1e6:.2f} MB, preview {os.path.getsize(p2) / 1e6:.2f} MB")
        o = np.asarray(im)
        s = px(o, 10, 23); assert s[0] > 150 and s[0] > s[2], f"Sahara should be bright sand, got {s}"
        g = px(o, -62, -4); assert g[1] > g[0] and g[1] < 110, f"Amazon should be dark green, got {g}"
        ice = px(o, -40, 72); assert ice.min() > 200, f"Greenland should be ice, got {ice}"


def step_elev():
    import netCDF4
    print("elevation + relief")
    z = netCDF4.Dataset(os.path.join(DATA, "etopo", "ETOPO_2022_v1_60s_surface.nc"))["z"][:]
    z = np.asarray(z, dtype=np.float32)          # (10800, 21600), row 0 = SOUTH, lon -180..180 cell-centred
    h0, w0 = z.shape
    lat = -90 + (np.arange(h0) + 0.5) * 180 / h0

    e4 = F.reduce_aligned(z, W4, H4, flip_ns=True)
    np.save(os.path.join(CACHE, "elev4.npy"), e4.astype(np.float32))
    u16 = np.clip(np.round((e4 + 11000.0) / 20000.0 * 65535.0), 0, 65535).astype(np.uint16)
    rgb = np.zeros((H4, W4, 3), np.uint8)
    rgb[..., 0] = u16 >> 8
    rgb[..., 1] = u16 & 255
    p = os.path.join(OUT, "elev.png")
    Image.fromarray(rgb, "RGB").save(p, optimize=True)
    print(f"  wrote elev.png {os.path.getsize(p) / 1e6:.2f} MB   range {e4.min():.0f} .. {e4.max():.0f} m")
    # 1-degree copy for the temperature model's sea-level reduction (fields_climate.py)
    np.save(os.path.join(CACHE, "elev_1deg.npy"), F.reduce_aligned(z, 360, 180, flip_ns=True))
    assert px(e4, 86.925, 27.988) > 5500, "Everest region must be high"
    assert px(e4, 142.4, 11.35) < -7000, "Mariana Trench must be deep"
    assert px(e4, -150, 0) < -3000 and px(e4, 90, -80) > 2500, "Pacific deep, East Antarctica high"

    # gradient at native 60 arc-seconds, in metres per metre, then area-averaged: the mean of
    # a gradient is the gradient of the smoothed surface, so nothing is invented.
    dlat_m = np.radians(180.0 / h0) * F.R_EARTH_KM * 1000.0
    coslat = np.maximum(np.cos(np.radians(lat)), 0.02)[:, None]       # TRAPS C4: do not blow up at the pole
    gx = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2 * dlat_m * coslat)     # d/d east
    gy = np.empty_like(z)
    gy[1:-1] = (z[2:] - z[:-2]) / (2 * dlat_m)                                        # d/d north (rows run south->north)
    gy[0] = gy[1]; gy[-1] = gy[-2]
    del z
    for name, g in (("relief_x", gx), ("relief_y", gy)):
        g8 = F.reduce_aligned(g, W8, H8, flip_ns=True)
        s = np.abs(g8)
        print(f"  {name}: |slope| p50 {np.percentile(s[::8, ::8], 50):.5f}  p99 {np.percentile(s[::8, ::8], 99):.4f}  max {s.max():.3f}")
        enc = 0.5 + 0.5 * np.tanh(3.0 * g8)            # companded: precision near zero slope
        used = np.unique(np.round(enc[::4, ::4] * 255)).size
        print(f"  {name}: 8-bit levels occupied {used}/256")
        save_gray(enc, f"{name}.webp", quality=92)
        np.save(os.path.join(CACHE, f"{name}.npy"), g8.astype(np.float16))
    # sign checks on the gradient (a flipped axis fails here): the Himalayan front rises to the
    # north, and the Andes' Pacific flank rises to the east.
    gyc = np.load(os.path.join(CACHE, "relief_y.npy")).astype(np.float32)
    gxc = np.load(os.path.join(CACHE, "relief_x.npy")).astype(np.float32)

    def box(a, lon0, lon1, lat0, lat1):
        i0, j1 = F.lonlat_to_px(lon0, lat0, W8, H8); i1, j0 = F.lonlat_to_px(lon1, lat1, W8, H8)
        return float(a[j0:j1, i0:i1].mean())
    hf, af = box(gyc, 80, 88, 27.3, 28.3), box(gxc, -71, -69.5, -24, -18)
    assert hf > 0.004, f"Himalayan front should slope up to the north, got {hf}"
    assert af > 0.004, f"Andes Pacific flank should slope up to the east, got {af}"


def step_night():
    print("night lights")
    a = np.asarray(Image.open(os.path.join(DATA, "night", "BlackMarble_2016_3km.jpg")).convert("RGB")).astype(np.float32)
    # The published image is lights composited on a moonlit blue base (measured: Sahara
    # 37,34,62; ocean 5,5,15; Paris 255,248,231). Lights are warm, the base is blue, so the
    # warm excess isolates emitted light.
    light = np.clip(((a[..., 0] + a[..., 1]) * 0.5 - 0.62 * a[..., 2] - 2.0) / 95.0, 0, 1)
    del a
    n8 = np.asarray(Image.fromarray(light, "F").resize((W8, H8), Image.LANCZOS), dtype=np.float32).clip(0, 1)
    np.save(os.path.join(CACHE, "night4.npy"), F.reduce_aligned(n8, W4, H4).astype(np.float16))
    save_gray(np.sqrt(n8), "night.webp", quality=88)          # sqrt-companded: most of the planet is dim
    assert px(n8, 2.35, 48.85) > 0.8, "Paris must be lit"
    assert px(n8, 10, 23) < 0.03 and px(n8, -150, 0) < 0.03, "Sahara and Pacific must be dark"
    print(f"  lit fraction (>0.05): {(n8 > 0.05).mean():.4f}")


def step_clouds():
    print("clouds")
    src = os.path.expanduser("~/Tectonic Plate Model/web/imagery/nasa-clouds-4096.jpg")
    if not os.path.exists(src):
        raise SystemExit("cloud texture not found; see Research/SOURCE-SURVEY.md for the NASA source")
    shutil.copyfile(src, os.path.join(OUT, "clouds.jpg"))
    meta = json.load(open(os.path.join(os.path.dirname(src), "nasa-clouds.json")))
    json.dump(meta, open(os.path.join(OUT, "clouds.json"), "w"), indent=1)
    print("  copied clouds.jpg (NASA Blue Marble: Clouds, 4096x2048)")


def main():
    args = sys.argv[1:] or ["water", "albedo", "elev", "night", "clouds"]
    for a in args:
        if a == "water": step_water()
        elif a.startswith("albedo"):
            step_albedo([int(a.split(":")[1])] if ":" in a else list(range(1, 13)))
        elif a == "elev": step_elev()
        elif a == "night": step_night()
        elif a == "clouds": step_clouds()
        else: raise SystemExit(f"unknown step {a}")
    from stamp import stamp
    stamp()
    print("surface: done")


if __name__ == "__main__":
    main()
