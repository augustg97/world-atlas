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
def ocean_connected(water_bool):
    """The part of a water mask that connects to the world ocean: its largest connected piece, with the
    antimeridian joined (the raster's left and right edges are neighbours)."""
    from scipy import ndimage
    lab, n = ndimage.label(water_bool)
    left, right = lab[:, 0], lab[:, -1]
    parent = np.arange(n + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    both = (left > 0) & (right > 0)
    for a, b in set(zip(left[both].tolist(), right[both].tolist())):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    root = np.array([find(i) for i in range(n + 1)])
    lab = root[lab]
    sizes = np.bincount(lab.ravel()); sizes[0] = 0
    return lab == sizes.argmax()


def etopo_sea8():
    """Share of each 8192 cell that is sea by ETOPO 2022: below sea level and connected to the world ocean.
    No coastline from anyone goes into it. THE WATER MASK DOES NOT USE THIS: it is the witness the mask is
    scored against (Research/modeling/audit_water.py), kept here so there is one definition of it.
    Cached: labelling 233 million cells takes a minute."""
    p = os.path.join(CACHE, "etopo_sea8.npy")
    if os.path.exists(p):
        return np.load(p).astype(np.float32)
    import netCDF4
    z = np.asarray(netCDF4.Dataset(os.path.join(DATA, "etopo", "ETOPO_2022_v1_60s_surface.nc"))["z"][:], dtype=np.float32)[::-1]   # north first
    out = F.reduce_aligned(ocean_connected(z < 0).astype(np.float32), W8, H8)
    np.save(p, out.astype(np.float16))
    return out


def _polys(name, keep=None):
    """The polygons of a Natural Earth layer, each a list of rings (the outline first, then its holes)."""
    for f in json.load(open(os.path.join(DATA, "ne", name + ".geojson")))["features"]:
        if keep is not None and not keep(f["properties"]):
            continue
        g = f["geometry"]
        if g is None:
            continue
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            yield poly


def _ring_area(ring):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))) * 0.5


def cover(polys, w=W8, h=H8, ss=3):
    """Share of each canonical cell that lies inside the polygons: drawn `ss` times finer and averaged.
    Rings go down largest first, outlines filled and holes cleared, so an island in a lake in a continent
    comes out as land: nothing drawn later can be bigger than the hole it sits in."""
    from PIL import ImageDraw
    ws, hs = w * ss, h * ss
    im = Image.new("L", (ws, hs), 0)
    dr = ImageDraw.Draw(im)
    rings = sorted(((_ring_area(r), 255 if k == 0 else 0, r) for poly in polys for k, r in enumerate(poly)), key=lambda t: -t[0])
    for _, fill, ring in rings:
        if len(ring) >= 3:
            # PIL puts a pixel's centre at whole numbers; the canonical frame puts its edge there
            dr.polygon([((x + 180.0) / 360.0 * ws - 0.5, (90.0 - y) / 180.0 * hs - 0.5) for x, y in ring], fill=fill)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=np.float32) / 255.0


DRY_LUM = 110        # a salt lake brighter than this in the July picture is a salt pan, not water


def step_water():
    """Water fraction at 8192, from a coastline and not from the picture.

    Until 2026-11-10 the sea was "wherever Blue Marble is its ocean fill colour". But Blue Marble paints
    every shelf sea, bank and river plume in a colour of its own, not the fill, so 5.6 million km2 of sea
    was classed as land: the East Siberian, Kara and Chukchi shelves, the mouth of the Amazon, the Yellow
    Sea, south-west Hudson Bay, the Bahama banks (Research/modeling/audit_water.py, against ETOPO 2022). It
    was drawn in the picture's water colour, which is why it went unseen for three rounds; it never iced,
    never glinted, and answered a click as land.

    Now: land is Natural Earth's 1:10m land, its minor islands and the Antarctic ice shelves (ice a
    viewer sees as ice); everything else is sea. Inland water is Natural Earth's 1:10m lakes, plus the
    open fresh water Blue Marble itself shows inside the land (lakes too small for the 1:10m sheet).
    Natural Earth draws dry salt pans as lakes; one that is bright in the picture is left dry."""
    print("water")
    land = cover(list(_polys("ne_10m_land")) + list(_polys("ne_10m_minor_islands")) + list(_polys("ne_10m_antarctic_ice_shelves_polys")))
    a = np.asarray(bmng(7))
    d = np.abs(a.astype(np.int16) - OCEAN_FILL).max(axis=2)
    lum = (a[..., 0] * 0.30 + a[..., 1] * 0.59 + a[..., 2] * 0.11)
    dark = (d > 7) & (lum < 13) & (a[..., 2] >= a[..., 0])       # dark and not red: open fresh water
    dark &= np.abs(F.canon_lat(a.shape[0])[:, None]) < 80        # no lakes poleward of 80; the polar night is dark too
    lum8 = F.reduce_aligned(lum, W8, H8)
    dark8 = F.reduce_aligned(dark.astype(np.float32), W8, H8)
    oc8 = F.reduce_aligned((d <= 7).astype(np.float32), W8, H8)
    # The picture's sea is two things, the same in all twelve months: one flat fill over deep water, and a
    # painted colour over every shelf, bank and plume (dark teal over the Siberian shelf, turquoise over the
    # Bahama banks, brown off the Amazon). `seen8` is that painted water; `white8` is what is not fill and is
    # near white in every channel, which south of 60 S is the ice of the shelves.
    seen8 = F.reduce_aligned(((d > 7) & (a.min(axis=2) < 110)).astype(np.float32), W8, H8)
    white8 = F.reduce_aligned(((d > 7) & (a.min(axis=2) >= 110)).astype(np.float32), W8, H8)
    del a, d, lum, dark
    np.save(os.path.join(CACHE, "ocean8.npy"), oc8.astype(np.float16))          # the picture's own fill: albedo and the audit read it
    # Antarctica's coast is the ice front. South of 60 S the land is Natural Earth's joined to whatever the
    # picture shows as ice. Three fronts were tried against the per-year check of the sea-ice conversion
    # (fields_climate.step_ocean), which fails when the atlas draws sea in cells NSIDC's grids hold as land
    # and the coast fill gives them ice:
    #     Natural Earth's shelves alone   worst year 6.8%   (its West, Ronne and Larsen C fronts stand back)
    #     ETOPO 2022's ice front          worst year 5.9%
    #     the picture's ice               worst year 3.4%   <- used
    # The picture's ice includes 0.37 million km2 that ETOPO calls sea (fast ice, and fronts that have moved).
    south = (F.canon_lat(H8) < -60.0)[:, None]
    land = np.where(south, np.maximum(land, white8), land)

    # salt lakes: wet or dry by the picture
    lakes, dry = [], []
    for f in json.load(open(os.path.join(DATA, "ne", "ne_10m_lakes.geojson")))["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        if f["properties"].get("featurecla") == "Alkaline Lake":
            xs = [x for p in polys for x, _ in p[0]]; ys = [y for p in polys for _, y in p[0]]
            i0, j0 = F.lonlat_to_px(min(xs), max(ys), W8, H8); i1, j1 = F.lonlat_to_px(max(xs), min(ys), W8, H8)
            win = lum8[j0:j1 + 1, i0:i1 + 1]
            # the middle of the basin's box is inside the basin for every salt lake large enough to matter
            core = win[win.shape[0] // 4: max(win.shape[0] // 4 + 1, 3 * win.shape[0] // 4), win.shape[1] // 4: max(win.shape[1] // 4 + 1, 3 * win.shape[1] // 4)]
            if core.size and float(np.median(core)) > DRY_LUM:
                dry.append((f["properties"].get("name"), round(float(np.median(core)))))
                continue
        lakes += polys
    print(f"  salt lakes left dry (bright in the July picture): {len(dry)}: " + ", ".join(f"{n} {v}" for n, v in sorted(dry, key=lambda t: -t[1])[:12]))
    lake = cover(lakes)
    inland = np.minimum(land, np.maximum(lake, dark8))            # inland water lies inside the land
    water = np.clip((1.0 - land) + inland, 0, 1)
    save_gray(water, "water.webp", quality=92)
    # Water whose colour the picture has. Over deep sea Blue Marble is one flat fill and the atlas paints its
    # own sea. Over shallow banks, river plumes, silty shelves and lakes it carries a colour: the turquoise
    # of the Bahama banks, the Amazon's brown, the Yellow Sea's silt. When the sea was "wherever the picture
    # is fill", those places were classed as LAND, which is how their colour reached the screen; with a real
    # coastline they are water, and this field says where the water's own colour should be the picture's.
    # Smoothed over three cells so that it fades in.
    from scipy import ndimage
    shoal = ndimage.uniform_filter(np.clip(np.minimum(water, seen8), 0, 1), size=3, mode=("nearest", "wrap"))
    save_gray(shoal, "shoal.webp", quality=88)
    area_w = F.cell_area_km2(W8, H8) * np.ones((1, W8), dtype=np.float32) / 1e6
    print(f"  water drawn in the picture's own colour: {float((shoal * area_w).sum()):.2f} M km2")
    assert px(shoal, -78.6, 25.2) > 0.8, "the Great Bahama Bank's colour is the picture's"
    assert px(shoal, -150, 0) < 0.01 and px(shoal, -30, 35) < 0.01, "the open Pacific and Atlantic are the atlas's own sea"
    assert px(shoal, -49.5, 1.2) > 0.8 and px(shoal, -40, -70) < 0.01, "the Amazon's mouth is the picture's brown; the open Weddell Sea is the atlas's own sea"
    # 4096 copy for JS-side probing and for the human fields
    np.save(os.path.join(CACHE, "water4.npy"), F.reduce_aligned(water, W4, H4).astype(np.float16))
    area = F.cell_area_km2(W8, H8) * np.ones((1, W8), dtype=np.float32) / 1e6
    print(f"  land {float((land * area).sum()):.2f} M km2 (Earth: 148.9 with the ice shelves' 1.6);  inland water {float((inland * area).sum()):.3f} M km2, "
          f"of it {float((np.minimum(land, lake) * area).sum()):.3f} Natural Earth lakes and {float((np.clip(np.minimum(land, dark8) - lake, 0, 1) * area).sum()):.3f} from the picture alone")
    assert px(water, -150, 0) > 0.99, "mid-Pacific must be water"
    assert px(water, 10, 23) < 0.01, "Sahara must be land"
    assert px(water, -87.5, 47.7) > 0.9, "Lake Superior must be water"
    assert px(water, 51, 42) > 0.9, "Caspian must be water"
    assert px(water, 90, -80) < 0.01, "Antarctica must be land"
    # the places the old mask had wrong, and the things a coastline-only mask would break
    assert px(water, 154.5, 73.0) > 0.99, "the East Siberian Sea is sea (the July picture shows it under ice)"
    assert px(water, -84.9, 55.6) > 0.99, "south-west Hudson Bay is sea"
    assert px(water, -78.0, 24.5) < 0.2 and px(water, -78.6, 25.2) > 0.99, "Andros is land and the Great Bahama Bank beside it is sea"
    assert px(water, -49.5, 1.2) > 0.99, "the mouth of the Amazon is sea"
    assert px(water, 108.0, 53.5) > 0.9 and px(water, 33.0, -1.0) > 0.99, "Baikal and Victoria are water"
    assert px(water, 137.3, -28.6) < 0.2, "Lake Eyre is a salt pan in the picture and stays dry"
    assert px(water, -112.5, 41.1) > 0.5, "the Great Salt Lake holds water"
    assert px(water, 5.45, 52.8) > 0.8, "the IJsselmeer is water"
    assert px(water, 175.0, -81.0) < 0.01, "the Ross Ice Shelf is ice, not sea"
    # (No assertion on the Amazon's main stem: it is brown, not dark, in the picture and a line in Natural Earth,
    # so neither source has ever made it water here. Rivers are drawn as lines. Register A5.)
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
