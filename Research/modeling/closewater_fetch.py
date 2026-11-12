"""Fetch the reference set for audit_closewater.py: 23 places, each a box of 14-24 km, with

    s2      the picture the app streams there: Sentinel-2 cloudless 2016 (EOX), level 12, 19 m a texel
    elev    the terrain tiles the app streams (AWS terrarium), zoom 12, sampled onto that grid
    mask    NASA's MODIS land/water mask as GIBS serves it (250 m), sampled onto that grid
    truth   the WITNESS: JRC Global Surface Water v1.4 (Pekel et al. 2016, Nature 540), water occurrence
            1984-2021 from Landsat at 30 m; water where it was water at least half the time.

The witness is measure-against only: it is not shipped and the page never asks its host. It is free to use
with attribution (Source: EC JRC/Google). Its 10-degree tiles are 30-85 MB each; eight are needed.
Everything lands in reference/closewater/ (ignored by git).

    ./venv/bin/python Research/modeling/closewater_fetch.py            # all 23; a place already there is skipped
"""
from __future__ import annotations

import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "reference", "closewater")
TILES = os.path.join(OUT, "tiles")
GSW = os.path.join(ROOT, "reference", "gsw")
Z = 12                                   # Sentinel-2 level and terrain zoom
# name: lon, lat, half-size km. Chosen before any rule was scored: sea coasts and harbours, wide and narrow
# rivers of every colour, lakes, a lagoon, polders and a salt lake below sea level, a desert reservoir,
# high mountains with no water at all. Each box lies inside one 10-degree tile of the witness.
SITES = dict(manhattan=(-73.99, 40.75, 9), laport=(-118.24, 33.75, 9), paris=(2.33, 48.86, 7), cairo=(31.23, 30.13, 9), amsterdam=(4.95, 52.40, 12),
             montreux=(6.88, 46.42, 9), venice=(12.33, 45.44, 9), deadsea=(35.50, 31.45, 12), manaus=(-59.85, -3.14, 12), dhaka=(90.40, 23.72, 12),
             rotterdam=(4.40, 51.90, 10), lyon=(4.83, 45.75, 8), zermatt=(7.75, 46.00, 9), portsaid=(32.30, 31.25, 10), ismailia=(32.30, 30.58, 10),
             albany=(-73.75, 42.65, 9), boston=(-71.05, 42.36, 9), santarem=(-54.72, -2.42, 12), chittagong=(91.82, 22.30, 10), garda=(10.70, 45.60, 10),
             cremona=(10.13, 45.10, 8), sandiego=(-117.18, 32.70, 9), mead=(-114.75, 36.10, 12))

S = requests.Session(); S.headers["User-Agent"] = "python-requests"


def get(url, key):
    p = os.path.join(TILES, key)
    if not os.path.exists(p):
        r = S.get(url, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"{url}: HTTP {r.status_code}")
        with open(p, "wb") as fh:
            fh.write(r.content)
    return Image.open(p)


def mosaic(url, key, P, r0, r1, c0, c1, mode):
    out = Image.new(mode, ((c1 - c0 + 1) * P, (r1 - r0 + 1) * P))
    jobs = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    with ThreadPoolExecutor(8) as ex:
        for (r, c), im in zip(jobs, ex.map(lambda rc: get(url(*rc), key(*rc)).convert(mode), jobs)):
            out.paste(im, ((c - c0) * P, (r - r0) * P))
    return np.asarray(out)


def gsw_tile(lon, lat):
    w = math.floor(lon / 10) * 10; n = math.ceil(lat / 10) * 10
    return f"{abs(w)}{'W' if w < 0 else 'E'}_{abs(n)}{'S' if n < 0 else 'N'}", w, n


def site(lon, lat, km):
    t = 180 / 256 / 2 ** Z
    dlat = km / 111.195; dlon = dlat / math.cos(math.radians(lat))
    x0 = int((lon - dlon + 180) / t); x1 = int((lon + dlon + 180) / t); y0 = int((90 - lat - dlat) / t); y1 = int((90 - lat + dlat) / t)
    w, h = x1 - x0, y1 - y0
    m = mosaic(lambda r, c: f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless/default/WGS84/{Z}/{r}/{c}.jpg", lambda r, c: f"s2_{Z}_{r}_{c}.jpg", 256, y0 // 256, (y1 - 1) // 256, x0 // 256, (x1 - 1) // 256, "RGB")
    s2 = m[y0 - (y0 // 256) * 256:, x0 - (x0 // 256) * 256:][:h, :w]
    lons = (x0 + np.arange(w) + 0.5) * t - 180; lats = 90 - (y0 + np.arange(h) + 0.5) * t
    n = 256 * 2 ** Z
    gx = (lons / 360 + 0.5) * n; gy = (0.5 - np.log(np.tan(np.pi / 4 + np.radians(lats) / 2)) / (2 * np.pi)) * n
    tx0, tx1, ty0, ty1 = int(gx.min() // 256), int(gx.max() // 256), int(gy.min() // 256), int(gy.max() // 256)
    tm = mosaic(lambda r, c: f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{c}/{r}.png", lambda r, c: f"terr_{Z}_{c}_{r}.png", 256, ty0, ty1, tx0, tx1, "RGB").astype(np.float64)
    el = tm[..., 0] * 256 + tm[..., 1] + tm[..., 2] / 256 - 32768
    elev = el[np.clip((gy - ty0 * 256).astype(int), 0, el.shape[0] - 1)][:, np.clip((gx - tx0 * 256).astype(int), 0, el.shape[1] - 1)]
    L = 8; g = 288 / 512 / 2 ** L
    px = (lons + 180) / g; py = (90 - lats) / g
    c0, c1, r0, r1 = int(px.min() // 512), int(px.max() // 512), int(py.min() // 512), int(py.max() // 512)
    mm = mosaic(lambda r, c: f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Water_Mask/default/250m/{L}/{r}/{c}.png", lambda r, c: f"MODIS_Water_Mask_{L}_{r}_{c}.png", 512, r0, r1, c0, c1, "RGBA")
    mask = mm[np.clip((py - r0 * 512).astype(int), 0, mm.shape[0] - 1)][:, np.clip((px - c0 * 512).astype(int), 0, mm.shape[1] - 1)][..., 3] > 0
    return dict(s2=s2, elev=elev.astype(np.float32), mask=mask, lons=lons, lats=lats)


def jrc_tiles(lons, lats):
    """JRC Global Surface Water occurrence as the PAGE gets it: the map tiles (Web Mercator, zoom 12, PNG; alpha is
    the share of the record in which the place was water, and open sea beyond the record is drawn as all water),
    taken bilinearly onto the grid. Returns float32 0..1."""
    from scipy import ndimage as nd
    n = 256 * 2 ** Z
    gx = (lons / 360 + 0.5) * n; gy = (0.5 - np.log(np.tan(np.pi / 4 + np.radians(lats) / 2)) / (2 * np.pi)) * n
    tx0, tx1, ty0, ty1 = int((gx.min() - 1) // 256), int((gx.max() + 1) // 256), int((gy.min() - 1) // 256), int((gy.max() + 1) // 256)
    a = mosaic(lambda r, c: f"https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{Z}/{c}/{r}.png", lambda r, c: f"jrc_{Z}_{c}_{r}.png", 256, ty0, ty1, tx0, tx1, "RGBA")[..., 3].astype(np.float32) / 255
    X, Y = np.meshgrid(gx - tx0 * 256 - 0.5, gy - ty0 * 256 - 0.5)
    return nd.map_coordinates(a, [Y, X], order=1, mode="nearest").astype(np.float32)


def main_jrc():
    """The page's source, on every place's grid: reference/closewater/<name>.jrc.npz {occ}."""
    os.makedirs(TILES, exist_ok=True)
    for n in SITES:
        out = os.path.join(OUT, f"{n}.jrc.npz")
        if os.path.exists(out):
            continue
        d = np.load(os.path.join(OUT, f"{n}.npz"))
        occ = jrc_tiles(d["lons"], d["lats"])
        np.savez_compressed(out, occ=occ)
        print(f"  {n:11s} water {100 * (occ >= 0.5).mean():.1f}% by the tiles, {100 * d['truth'].mean():.1f}% by the record's own file; they differ on {100 * ((occ >= 0.5) != d['truth']).mean():.2f}% of texels")


def main():
    if "--jrc" in sys.argv:
        return main_jrc()
    import tifffile
    os.makedirs(TILES, exist_ok=True); os.makedirs(GSW, exist_ok=True)
    todo = [n for n in (sys.argv[1:] or SITES) if not os.path.exists(os.path.join(OUT, f"{n}.npz"))]
    by = {}
    for n in todo:
        by.setdefault(gsw_tile(*SITES[n][:2]), []).append(n)
    for (t, w, north), names in by.items():
        p = os.path.join(GSW, f"occurrence_{t}.tif")
        if not os.path.exists(p):
            print(f"  fetching the witness tile {t} ...", flush=True)
            r = S.get(f"https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{t}v1_4_2021.tif", timeout=900)
            r.raise_for_status()
            with open(p, "wb") as fh:
                fh.write(r.content)
        a = tifffile.imread(p)
        assert a.shape == (40000, 40000), a.shape
        for n in names:
            d = site(*SITES[n])
            ix = ((d["lons"] - w) / 0.00025).astype(int); iy = ((north - d["lats"]) / 0.00025).astype(int)
            assert ix.min() >= 0 and ix.max() < 40000 and iy.min() >= 0 and iy.max() < 40000, f"{n} leaves its witness tile"
            occ = a[iy][:, ix]
            assert (occ > 100).mean() < 0.01, f"{n}: the witness has no data over {100 * (occ > 100).mean():.0f}% of the box"
            lat = float(d["lats"].mean()); my = 180 / 256 / 2 ** Z * 111195.0
            np.savez_compressed(os.path.join(OUT, f"{n}.npz"), s2=d["s2"], elev=d["elev"], mask=d["mask"], truth=(occ >= 50) & (occ <= 100),
                                lons=d["lons"], lats=d["lats"], mx=my * math.cos(math.radians(lat)), my=my)
            print(f"  {n:11s} {d['s2'].shape[1]} x {d['s2'].shape[0]}  water {100 * ((occ >= 50) & (occ <= 100)).mean():.1f}% by the witness, {100 * d['mask'].mean():.1f}% by MODIS")
        del a
    print(f"closewater reference: {len(SITES) - len(todo)} already there, {len(todo)} fetched")


if __name__ == "__main__":
    main()
