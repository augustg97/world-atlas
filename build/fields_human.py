#!/usr/bin/env python3
"""Human fields: population density, shipping density + lane orientation, fossil CO2 flux,
country identity raster.

    ./venv/bin/python build/fields_human.py              # all
    ./venv/bin/python build/fields_human.py pop ships

Frames (SCOPE section 6) - none of these three rasters starts at -180/90, so nothing here
assumes it. Each reads its own georeferencing and goes through frames.bin_sum, which is
conservative: totals are preserved exactly and reported.
  GHSL GHS-POP 30"      origin -180.0079, 89.0996 (corner), 43202 x 21384, people per cell
  ship density (ovr 0)  0.01 deg, corner -180.0153, 85.0026, 36003 x 16999, AIS positions per cell
  EDGAR v8.0            0.1 deg, cell centres -179.95.., rows SOUTH to north, tonnes per cell per year
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import frames as F

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "web", "fields")
CACHE = os.path.join(DATA, "_cache")
W4, H4 = 4096, 2048
META = os.path.join(OUT, "human.json")


def meta_update(key, val):
    m = json.load(open(META)) if os.path.exists(META) else {}
    m[key] = val
    json.dump(m, open(META, "w"), indent=1)


def log_enc(x, x0, xmax):
    return np.clip(np.log1p(np.maximum(x, 0) / x0) / np.log1p(xmax / x0), 0, 1)


def save_gray_png(a01, name):
    p = os.path.join(OUT, name)
    Image.fromarray(np.clip(np.round(a01 * 255), 0, 255).astype(np.uint8)).save(p, optimize=True)
    print(f"  wrote {name} {os.path.getsize(p) / 1e6:.2f} MB")


def at(a, lon, lat):
    h, w = a.shape[-2:]
    i, j = F.lonlat_to_px(lon, lat, w, h)
    return a[..., j, i]


def read_big(path, page=0):
    """Decode a large tiled TIFF page into a temporary memory map (never all in RAM)."""
    import tifffile
    return tifffile.TiffFile(path).pages[page].asarray(out="memmap")


def step_pop():
    import tifffile
    print("population (GHSL 2025)")
    path = os.path.join(DATA, "pop", "GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif")
    pg = tifffile.TiffFile(path).pages[0]
    sx, sy, _ = pg.tags["ModelPixelScaleTag"].value
    tp = pg.tags["ModelTiepointTag"].value          # (i, j, k, x, y, z): raster corner (0,0) -> lon, lat
    lon_left, lat_top = tp[3], tp[4]
    h0, w0 = pg.shape
    print(f"  georef: corner {lon_left:.6f}, {lat_top:.6f}  step {sx:.8f}  size {w0}x{h0}")
    a = read_big(path)
    lon_c = lon_left + (np.arange(w0) + 0.5) * sx
    acc = np.zeros((H4, W4))
    acc1 = np.zeros((180, 360))
    total = 0.0
    for r0 in range(0, h0, 1024):
        blk = np.asarray(a[r0:r0 + 1024], dtype=np.float64)
        blk[~np.isfinite(blk) | (blk < 0)] = 0.0             # nodata is negative
        lat_c = lat_top - (np.arange(r0, r0 + blk.shape[0]) + 0.5) * sy
        F.bin_sum(blk, lon_c, lat_c, acc)
        F.bin_sum(blk, lon_c, lat_c, acc1)
        total += blk.sum()
    print(f"  total population: source {total / 1e9:.4f} bn, binned {acc.sum() / 1e9:.4f} bn (UN 2025: ~8.2 bn)")
    assert abs(acc.sum() - total) / total < 1e-9, "binning must conserve people"
    dens = acc / F.cell_area_km2(W4, H4)
    np.save(os.path.join(CACHE, "pop_count4.npy"), acc.astype(np.float32))
    acc1.astype(np.float32).tofile(os.path.join(OUT, "pop_1deg.bin"))      # 360x180 float32 counts, for integrals in the app
    X0, XMAX = 1.0, 40000.0
    save_gray_png(log_enc(dens, X0, XMAX), "pop.png")
    meta_update("pop", {"file": "pop.png", "w": W4, "h": H4, "curve": "log1p", "x0": X0, "xmax": XMAX,
                        "units": "people per km2", "source": "JRC GHSL GHS-POP R2023A, epoch 2025", "total": float(total),
                        "counts_1deg": "pop_1deg.bin"})
    print(f"  density: max {dens.max():.0f} /km2, cells over 1000/km2: {(dens > 1000).sum()}")
    assert at(dens, 90.4, 23.8) > 2000, f"Dhaka must be dense, got {at(dens, 90.4, 23.8)}"
    assert at(dens, 139.7, 35.7) > 2000, "Tokyo must be dense"
    assert at(dens, 10, 23) < 1 and at(dens, -150, 0) == 0, "Sahara and Pacific must be empty"
    assert at(dens, 31.2, 30.0) > 1000 and at(dens, 25.0, 24.0) < 2, "the Nile is a line of people in an empty desert"


def step_ships():
    print("shipping density (World Bank / IMF AIS 2015-2021)")
    path = os.path.join(DATA, "ships", "shipdensity_global.tif.ovr")
    tfw = [float(x) for x in open(os.path.join(DATA, "ships", "shipdensity_global.tfw")).read().split()]
    d_full, lon_c0, lat_c0 = tfw[0], tfw[4], tfw[5]            # world file: CENTRE of the top-left full-res pixel
    lon_left, lat_top = lon_c0 - d_full / 2, lat_c0 + d_full / 2
    a = read_big(path, 0)                                       # first overview: half resolution
    h0, w0 = a.shape
    d = d_full * 2.0
    print(f"  georef: corner {lon_left:.6f}, {lat_top:.6f}  step {d}  size {w0}x{h0} (spans {w0 * d:.2f} deg lon, to lat {lat_top - h0 * d:.2f})")
    lon_c = lon_left + (np.arange(w0) + 0.5) * d
    acc = np.zeros((H4, W4)); n = np.zeros((H4, W4))
    for r0 in range(0, h0, 1024):
        blk = np.asarray(a[r0:r0 + 1024]).astype(np.float64)
        ok = (blk < 2e9) & (blk >= 0)
        blk[~ok] = 0
        lat_c = lat_top - (np.arange(r0, r0 + blk.shape[0]) + 0.5) * d
        F.bin_sum(blk, lon_c, lat_c, acc)
        F.bin_sum(ok.astype(np.float64), lon_c, lat_c, n)
    mean = np.where(n > 0, acc / np.maximum(n, 1), 0.0)         # mean AIS positions per 0.01-deg cell
    water = np.load(os.path.join(CACHE, "water4.npy")).astype(np.float32)
    mean *= (water > 0.3)                                       # river and port spill onto land cells is dropped
    p = np.percentile(mean[mean > 0], [50, 90, 99, 99.9])
    print(f"  mean positions per cell: p50 {p[0]:.1f}  p90 {p[1]:.1f}  p99 {p[2]:.0f}  p99.9 {p[3]:.0f}  max {mean.max():.0f}")
    X0, XMAX = 5.0e4, 3.0e7                     # measured: p50 1.8e4, p99 1.3e7, max 4.8e7
    enc = log_enc(mean, X0, XMAX)
    save_gray_png(enc, "ships.png")
    np.save(os.path.join(CACHE, "ships4.npy"), enc.astype(np.float32))
    meta_update("ships", {"file": "ships.png", "w": W4, "h": H4, "curve": "log1p", "x0": X0, "xmax": XMAX,
                          "units": "AIS positions per 0.01-degree cell, 2015-2021", "source": "World Bank / IMF Global Shipping Traffic Density"})
    for nm, lo, la in (("Dover Strait", 1.5, 51.0), ("Malacca Strait", 100.5, 3.2), ("Singapore Strait", 104.2, 1.25), ("Suez approaches", 32.6, 29.7),
                       ("mid North Atlantic lane", -40, 45), ("far South Pacific", -120, -45), ("Sahara", 10, 23)):
        print(f"    {nm:26s} {at(enc, lo, la):.2f}")
    assert at(enc, 1.5, 51.0) > 0.6 and at(enc, 100.5, 3.2) > 0.6, "Dover and Malacca Straits must be busy"
    assert at(enc, -120, -45) < 0.15 and at(enc, 10, 23) == 0, "the far South Pacific is nearly empty; the Sahara has no ships"

    step_lanes()


def step_lanes():
    """Lane geometry for the ship tracers, from the density field alone.

    A sea lane is a RIDGE in the density field: a line a pixel or two wide that stands above its
    surroundings. Two things are derived and shipped in lanes.png (2048 x 1024):
      R, G   cos and sin of twice the lane bearing, scaled by how coherent the direction is
             (double-angle form: a lane has no sign, and this form can be averaged)
      B      ridge strength - how far the density stands above its ~80 km neighbourhood
    Tracers spawn in proportion to ridge strength and die when they leave a ridge, so they can
    only ever be drawn where ships were actually recorded. (The first version used the smoothed
    density itself: tracers filled the whole North Atlantic in aimless swirls - measured, wrong.)
    """
    print("ship lanes (ridges of the density field)")
    enc = np.load(os.path.join(CACHE, "ships4.npy")).astype(np.float32)
    wrap = ("nearest", "wrap")
    # Open-ocean AIS density is speckle (single voyages); a LANE is where many voyages agree.
    # So: band-pass the density (lane width against an ~100 km neighbourhood), then keep only
    # where the direction of the structure is coherent over ~40 km. Speckle fails the second test.
    g = ndimage.gaussian_filter(enc, 1.5, mode=wrap)
    band = g - ndimage.gaussian_filter(enc, 10, mode=wrap)
    gy, gx = np.gradient(g)
    cl = np.maximum(np.cos(np.radians(F.canon_lat(H4))), 0.05)[:, None]
    gx = gx / cl                                                # equal angular steps are shorter in metres near the poles
    jxx = ndimage.gaussian_filter(gx * gx, 4.0, mode=wrap)
    jyy = ndimage.gaussian_filter(gy * gy, 4.0, mode=wrap)
    jxy = ndimage.gaussian_filter(gx * gy, 4.0, mode=wrap)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2    # perpendicular to the dominant gradient; image coords, y SOUTH
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-9)
    print(f"  band-pass: p50 {np.percentile(band[enc > 0.05], 50):.3f} p90 {np.percentile(band[enc > 0.05], 90):.3f} p99 {np.percentile(band[enc > 0.05], 99):.3f};  coherence p50 {np.percentile(coh[enc > 0.05], 50):.2f} p90 {np.percentile(coh[enc > 0.05], 90):.2f}")
    ridge = np.clip(band / 0.10, 0, 1) * np.clip((coh - 0.45) / 0.35, 0, 1) * (enc > 0.12)
    # a strait packed wall to wall has no ridge to find; the busiest water is a lane by definition
    ridge = np.maximum(ridge, np.clip((g - 0.72) / 0.18, 0, 1))
    c2, s2 = np.cos(2 * theta) * coh, np.sin(2 * theta) * coh
    Wl, Hl = 2048, 1024
    lane = np.zeros((Hl, Wl, 3), np.uint8)
    lane[..., 0] = np.clip(F.reduce_aligned(c2, Wl, Hl) * 127.5 + 127.5, 0, 255)
    lane[..., 1] = np.clip(F.reduce_aligned(s2, Wl, Hl) * 127.5 + 127.5, 0, 255)
    # max-pool the ridge so a one-pixel lane survives the 2x reduction
    lane[..., 2] = np.clip(ridge.reshape(Hl, 2, Wl, 2).max(axis=(1, 3)) * 255, 0, 255)
    Image.fromarray(lane).save(os.path.join(OUT, "lanes.png"), optimize=True)
    Image.fromarray(lane[..., 2]).save(os.path.join(CACHE, "lanes_ridge_preview.png"))
    print(f"  wrote lanes.png {os.path.getsize(os.path.join(OUT, 'lanes.png')) / 1e6:.2f} MB; ridge cells (>0.3): {(lane[..., 2] > 76).mean():.3%} of the grid")

    def bearing(lon, lat):
        i, j = F.lonlat_to_px(lon, lat, Wl, Hl)
        cc, ss = lane[j, i, 0] / 127.5 - 1, lane[j, i, 1] / 127.5 - 1
        return (90 + 0.5 * np.degrees(np.arctan2(ss, cc))) % 180, lane[j, i, 2] / 255
    for nm, lo, la, exp in (("Dover Strait", 1.4, 51.0, "~45"), ("Malacca Strait", 100.5, 3.2, "~140"), ("Red Sea axis", 38.5, 20.0, "~155"),
                            ("Gibraltar approach", -7.5, 36.0, "~90"), ("off Cape Finisterre", -9.9, 43.2, "~0/180"), ("mid South Pacific", -120, -45, "none")):
        bg, rd = bearing(lo, la)
        print(f"    {nm:22s} bearing {bg:5.0f} (expect {exp})  ridge {rd:.2f}")


def step_co2():
    import netCDF4
    print("fossil CO2 (EDGAR v8.0, 2022)")
    d = netCDF4.Dataset(os.path.join(DATA, "co2", "v8.0_FT2022_GHG_CO2_2022_TOTALS_emi.nc"))
    e = np.ma.filled(d["emissions"][:].astype(np.float64), 0.0)
    lat, lon = d["lat"][:], d["lon"][:]
    assert lat[0] < lat[-1] and abs(lon[0] + 179.95) < 1e-6, "EDGAR frame is not what this step assumes"
    e = e[::-1]                                                  # to north-first; already -180..180 cell-centred
    H, W = e.shape
    flux = e / F.cell_area_km2(W, H)                             # tonnes CO2 per km2 per year
    print(f"  global total {e.sum() / 1e9:.2f} Gt CO2 (EDGAR 2022 reports ~38.5 incl. international transport)")
    X0, XMAX = 5.0, 5.0e5
    save_gray_png(log_enc(flux, X0, XMAX), "co2.png")
    (F.reduce_aligned(e, 360, 180) * 100.0).astype(np.float32).tofile(os.path.join(OUT, "co2_1deg.bin"))   # tonnes per 1-degree cell
    meta_update("co2", {"file": "co2.png", "w": W, "h": H, "curve": "log1p", "x0": X0, "xmax": XMAX,
                        "units": "tonnes CO2 per km2 per year", "source": "EDGAR v8.0 (JRC), year 2022", "total_t": float(e.sum())})
    assert at(flux, 116.4, 39.9) > 5000 and at(flux, 10, 23) < 20, "Beijing emits; the Sahara does not"


def step_countries():
    print("country identity raster (Natural Earth 5.1.2, de facto)")
    W, H = 8192, 4096
    fc = json.load(open(os.path.join(DATA, "ne", "ne_50m_admin_0_countries.geojson")))["features"]
    fc.sort(key=lambda f: f["properties"]["ADM0_A3"])            # id = 1 + index in ADM0_A3 order; vectors.py uses the same order
    ids = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(ids)

    def to_px(ring):
        return [((x + 180.0) / 360.0 * W, (90.0 - y) / 180.0 * H) for x, y in ring]

    def area(f):
        g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        return sum(abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p[0], p[0][1:]))) for p in polys)
    order = sorted(range(len(fc)), key=lambda i: -area(fc[i]))   # big first, so enclaves draw on top
    for i in order:
        g = fc[i]["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            dr.polygon(to_px(poly[0]), fill=i + 1)
            for hole in poly[1:]:
                dr.polygon(to_px(hole), fill=0)
    # a second pass restores enclaves that a later hole-punch erased
    for i in reversed(order[len(order) // 2:]):
        g = fc[i]["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            dr.polygon(to_px(poly[0]), fill=i + 1)
    idarr = np.asarray(ids).copy()
    # the 50m coast is generalised; extend ids up to ~16 px seaward so real coast pixels are never unowned
    dist, idx = ndimage.distance_transform_edt(idarr == 0, return_indices=True)
    grown = idarr[idx[0], idx[1]]
    idarr = np.where((idarr == 0) & (dist <= 16), grown, idarr)

    dis = Image.new("L", (W, H), 0)
    dd = ImageDraw.Draw(dis)
    for f in json.load(open(os.path.join(DATA, "ne", "ne_50m_admin_0_breakaway_disputed_areas.geojson")))["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            dd.polygon(to_px(poly[0]), fill=255)
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[..., 0] = idarr
    rgb[..., 1] = np.asarray(dis)
    # B: Natural Earth's 7-colour map index, so the Atlas style can tint without a lookup
    mc = np.zeros(256, np.uint8)
    for i, f in enumerate(fc):
        mc[i + 1] = int(f["properties"].get("MAPCOLOR7") or 1) * 32
    rgb[..., 2] = mc[idarr]
    p = os.path.join(OUT, "countries.png")
    Image.fromarray(rgb).save(p, optimize=True)
    print(f"  wrote countries.png {os.path.getsize(p) / 1e6:.2f} MB, {len(fc)} units")
    a3 = [f["properties"]["ADM0_A3"] for f in fc]
    def who(lon, lat): return a3[at(idarr, lon, lat) - 1] if at(idarr, lon, lat) else None
    assert who(2.35, 48.85) == "FRA" and who(-100, 40) == "USA" and who(28.2, -29.5) == "LSO" and who(12.45, 43.94) in ("SMR", "ITA")
    assert who(-150, 0) is None and who(139.7, 35.7) == "JPN" and who(34.0, 45.2) is not None
    assert at(np.asarray(dis), 34.0, 45.2) == 255, "Crimea must carry the disputed flag"

    # population per unit, from the same population field the app shows (the witness audit reads this)
    pc = os.path.join(CACHE, "pop_count4.npy")
    if os.path.exists(pc):
        pop = np.load(pc)
        id4 = idarr[::2, ::2]
        sums = np.bincount(id4.ravel(), weights=pop.ravel(), minlength=len(fc) + 1)
        json.dump({a3[i]: float(sums[i + 1]) for i in range(len(fc))} | {"_unassigned": float(sums[0])},
                  open(os.path.join(CACHE, "pop_by_country.json"), "w"), indent=0)
        print(f"  population assigned to a unit: {sums[1:].sum() / 1e9:.3f} bn; unassigned {sums[0] / 1e6:.1f} M")


def main():
    args = sys.argv[1:] or ["pop", "ships", "co2", "countries"]
    for a in args:
        {"pop": step_pop, "ships": step_ships, "lanes": step_lanes, "co2": step_co2, "countries": step_countries}[a]()
    from stamp import stamp
    stamp()
    print("human: done")


if __name__ == "__main__":
    main()
