"""The canonical frame, and every conversion into it.  SCOPE §6.

CANONICAL RASTER
    equirectangular WGS84, pixel-CENTRE registered
    column i centre:  lon = -180 + (i + 0.5) * 360 / W
    row    j centre:  lat =  +90 - (j + 0.5) * 180 / H     (row 0 is the north)

Every source grid is described by what it actually is (where its first sample sits, which
way its rows run, whether its longitudes start at 0 or -180, whether it is node- or
cell-registered) and converted here. Nothing else in build/ may index a source grid directly.

Tested by build/test_frames.py - run it after touching anything in this file.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

R_EARTH_KM = 6371.0088


def canon_lon(w: int) -> np.ndarray:
    return -180.0 + (np.arange(w) + 0.5) * 360.0 / w


def canon_lat(h: int) -> np.ndarray:
    return 90.0 - (np.arange(h) + 0.5) * 180.0 / h


def cell_area_km2(w: int, h: int) -> np.ndarray:
    """Area of each canonical cell, shape (h, 1). Exact on the sphere (sine difference)."""
    top = np.radians(90.0 - np.arange(h) * 180.0 / h)
    bot = np.radians(90.0 - (np.arange(h) + 1) * 180.0 / h)
    band = (np.sin(top) - np.sin(bot)) * R_EARTH_KM ** 2 * (2 * np.pi / w)
    return band[:, None]


def resample_grid(src: np.ndarray, src_lons: np.ndarray, src_lats: np.ndarray,
                  w: int, h: int) -> np.ndarray:
    """Bilinear resample of a COARSE global grid onto the canonical raster.

    src        (..., nlat, nlon)
    src_lons   the longitude of each source column's SAMPLE POINT, degrees, ascending,
               any origin (0..360 or -180..180). Treated as periodic.
    src_lats   the latitude of each source row's sample point; ascending or descending,
               regular or irregular (Gaussian). Clamped beyond its ends (no extrapolation).
    NaNs are honoured: a target point takes the weighted mean of its non-NaN corners and is
    NaN only if all four are.
    """
    src = np.asarray(src, dtype=np.float64)
    lons = np.asarray(src_lons, dtype=np.float64)
    lats = np.asarray(src_lats, dtype=np.float64)
    if lats[0] > lats[-1]:                       # make latitude ascending
        lats = lats[::-1]
        src = src[..., ::-1, :]
    nlon = lons.size
    dlon = (lons[-1] - lons[0]) / (nlon - 1)
    if abs(dlon * nlon - 360.0) > 1e-3 * 360:
        raise ValueError(f"source longitudes are not a full periodic circle: {dlon * nlon}")

    tl = canon_lon(w)
    fx = ((tl - lons[0]) % 360.0) / dlon          # fractional column, periodic
    x0 = np.floor(fx).astype(int) % nlon
    x1 = (x0 + 1) % nlon
    ax = fx - np.floor(fx)

    tlat = canon_lat(h)
    fy = np.interp(tlat, lats, np.arange(lats.size))   # clamps at the ends
    y0 = np.clip(np.floor(fy).astype(int), 0, lats.size - 1)
    y1 = np.clip(y0 + 1, 0, lats.size - 1)
    ay = fy - y0

    def take(yy, xx):
        return src[..., yy[:, None], xx[None, :]]

    c = [take(y0, x0), take(y0, x1), take(y1, x0), take(y1, x1)]
    wts = [(1 - ay)[:, None] * (1 - ax)[None, :], (1 - ay)[:, None] * ax[None, :],
           ay[:, None] * (1 - ax)[None, :], ay[:, None] * ax[None, :]]
    num = np.zeros(c[0].shape)
    den = np.zeros(c[0].shape)
    for ci, wi in zip(c, wts):
        ok = ~np.isnan(ci)
        num += np.where(ok, ci, 0.0) * wi
        den += ok * wi
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den < 1e-9] = np.nan
    return out


def reduce_aligned(src: np.ndarray, w: int, h: int, flip_ns: bool = False) -> np.ndarray:
    """Area-average a FINE global raster that is already aligned to exactly -180..180 / 90..-90
    (cell-registered) down to the canonical (h, w). Non-integer ratios are handled (PIL BOX).

    flip_ns=True if the source's row 0 is the SOUTH.
    """
    a = np.asarray(src, dtype=np.float32)
    if flip_ns:
        a = a[::-1]
    im = Image.fromarray(np.ascontiguousarray(a), mode="F")
    # BOX is exact for integer ratios but dislocates samples by up to ~0.1 px at non-integer
    # ones (measured in test_frames.py); HAMMING has the same footprint without that.
    exact = a.shape[1] % w == 0 and a.shape[0] % h == 0
    return np.asarray(im.resize((w, h), Image.BOX if exact else Image.HAMMING), dtype=np.float32)


def bin_sum(values: np.ndarray, lon_centres: np.ndarray, lat_centres: np.ndarray,
            acc: np.ndarray) -> None:
    """Conservatively add a source block into canonical bins: each source cell's whole value
    goes to the canonical cell containing its centre. Sums are preserved exactly.

    values (n_lat, n_lon); lon_centres (n_lon,), lat_centres (n_lat,) in degrees.
    Longitudes outside -180..180 wrap; latitudes outside the raster are dropped.
    """
    h, w = acc.shape
    ix = np.floor(((lon_centres + 180.0) % 360.0) / 360.0 * w).astype(int) % w
    iy = np.floor((90.0 - lat_centres) / 180.0 * h).astype(int)
    ok = (iy >= 0) & (iy < h)
    v = np.asarray(values, dtype=np.float64)[ok]
    iy = iy[ok]
    # sum along longitude first (bincount per row is far faster than np.add.at)
    for r in np.unique(iy):
        rows = v[iy == r].sum(axis=0)
        acc[r] += np.bincount(ix, weights=rows, minlength=w)


def lonlat_to_px(lon: float, lat: float, w: int, h: int) -> tuple[int, int]:
    """Canonical pixel (col, row) containing a point."""
    i = int(np.floor(((lon + 180.0) % 360.0) / 360.0 * w)) % w
    j = min(h - 1, max(0, int(np.floor((90.0 - lat) / 180.0 * h))))
    return i, j


# --- NSIDC sea-ice polar stereographic grids -------------------------------------------------
# EPSG:3411 (north) and EPSG:3412 (south): polar stereographic on the Hughes 1980 ellipsoid, true
# scale at 70 degrees, 25 km cells. x0/y0 is the OUTER corner of the top-left pixel in metres;
# x runs right with the column, y runs UP while the row runs down. lon0 is the meridian that
# points straight down the grid (north) or straight up it (south). Constants as published in
# NSIDC's "Guide to NSIDC's Polar Stereographic Projection" and as read back from the GeoTIFF
# tags by read_nsidc_concentration, which refuses a file that disagrees.
# The latitudes are geodetic on Hughes 1980, not WGS84; NSIDC puts the difference at about 1 m
# across a 25 km cell, four orders of magnitude below a canonical cell.
HUGHES_A = 6378273.0
HUGHES_B = 6356889.449
HUGHES_E = float(np.sqrt(1.0 - (HUGHES_B / HUGHES_A) ** 2))
NSIDC_NORTH = {"name": "north", "sign": 1, "lon0": -45.0, "lat_ts": 70.0, "x0": -3850000.0, "y0": 5850000.0,
               "nx": 304, "ny": 448, "cell": 25000.0, "epsg": 3411}
NSIDC_SOUTH = {"name": "south", "sign": -1, "lon0": 0.0, "lat_ts": 70.0, "x0": -3950000.0, "y0": 4350000.0,
               "nx": 316, "ny": 332, "cell": 25000.0, "epsg": 3412}
# values in the Sea Ice Index concentration GeoTIFFs (user guide, table 5): 0..1000 = percent x 10
NSIDC_POLE, NSIDC_COAST, NSIDC_LAND, NSIDC_MISSING = 2510, 2530, 2540, 2550


def _ps_t(lat_abs_rad: np.ndarray) -> np.ndarray:
    """Snyder (1987) eq. 15-9: the conformal colatitude term, for |latitude| in radians."""
    es = HUGHES_E * np.sin(lat_abs_rad)
    return np.tan(np.pi / 4 - lat_abs_rad / 2) / ((1 - es) / (1 + es)) ** (HUGHES_E / 2)


def _ps_m(lat_abs_rad: np.ndarray) -> np.ndarray:
    return np.cos(lat_abs_rad) / np.sqrt(1 - (HUGHES_E * np.sin(lat_abs_rad)) ** 2)


def polar_stereo_xy(lon, lat, grid: dict):
    """Geodetic lon/lat (degrees) -> projected x, y in metres (Snyder eq. 21-33, 21-34).
    Points of the other hemisphere project far outside the grid; they are not clipped here."""
    sgn = grid["sign"]
    la = np.radians(np.asarray(lat, dtype=np.float64) * sgn)
    dl = np.radians(np.asarray(lon, dtype=np.float64) - grid["lon0"])
    lc = np.radians(grid["lat_ts"])
    rho = HUGHES_A * _ps_m(lc) * _ps_t(la) / _ps_t(lc)
    return rho * np.sin(dl), -sgn * rho * np.cos(dl)


def polar_stereo_lonlat(x, y, grid: dict):
    """Inverse of polar_stereo_xy: projected metres -> lon (-180..180), lat in degrees."""
    sgn = grid["sign"]
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y, dtype=np.float64)
    lc = np.radians(grid["lat_ts"])
    t = np.hypot(x, y) * _ps_t(lc) / (HUGHES_A * _ps_m(lc))
    la = np.pi / 2 - 2 * np.arctan(t)
    for _ in range(8):                                   # Snyder eq. 7-9, converges in 4
        es = HUGHES_E * np.sin(la)
        la = np.pi / 2 - 2 * np.arctan(t * ((1 - es) / (1 + es)) ** (HUGHES_E / 2))
    lon = grid["lon0"] + np.degrees(np.arctan2(x, -sgn * y))
    return (lon + 180.0) % 360.0 - 180.0, sgn * np.degrees(la)


def polar_cell_area_km2(grid: dict) -> np.ndarray:
    """True area of every cell of an NSIDC grid, (ny, nx): the nominal 625 km2 over the square of
    the projection's scale factor at the cell centre (382..664 km2 north, 443..664 km2 south)."""
    xs = grid["x0"] + (np.arange(grid["nx"]) + 0.5) * grid["cell"]
    ys = grid["y0"] - (np.arange(grid["ny"]) + 0.5) * grid["cell"]
    rho = np.hypot(xs[None, :], ys[:, None])
    _, lat = polar_stereo_lonlat(xs[None, :], ys[:, None], grid)
    k = rho / (HUGHES_A * _ps_m(np.radians(np.abs(lat))))
    return (grid["cell"] / 1000.0) ** 2 / k ** 2


def polar_px(lon, lat, grid: dict):
    """Fractional (col, row) of a point in an NSIDC grid, in PIXEL-EDGE units: the top-left pixel
    covers 0 <= col < 1, 0 <= row < 1 and its centre is (0.5, 0.5)."""
    x, y = polar_stereo_xy(lon, lat, grid)
    return (x - grid["x0"]) / grid["cell"], (grid["y0"] - y) / grid["cell"]


def polar_map(grid: dict, w: int, h: int) -> dict:
    """Where every canonical cell centre of this grid's hemisphere falls in the NSIDC grid.
    Built once and reused for every month (resample_polar)."""
    rows = np.where(canon_lat(h) * grid["sign"] > 0)[0]
    fc, fr = polar_px(canon_lon(w)[None, :], canon_lat(h)[rows][:, None], grid)
    inside = (fc >= 0) & (fc < grid["nx"]) & (fr >= 0) & (fr < grid["ny"])
    return {"grid": grid, "w": w, "h": h, "rows": rows, "fc": fc, "fr": fr, "inside": inside}


def resample_polar(src: np.ndarray, pm: dict, method: str = "nearest") -> np.ndarray:
    """An NSIDC polar grid (..., ny, nx) onto the canonical raster (..., h, w). NaN outside the
    grid's footprint and in the other hemisphere.

    nearest   each canonical cell takes the source cell that CONTAINS its centre. A thresholded
              quantity (is this cell iced?) keeps the source's own cell-by-cell answer, so an area
              counted here equals the source's count up to the canonical cells' own granularity.
    bilinear  between the four surrounding source cell centres, NaN-aware like resample_grid, and
              clamped at the grid's outer half cell. For smooth fields only: the 15% contour of a
              bilinearly interpolated concentration sits outside the 15% cells (measured in
              fields_climate.py), so extent must never be counted on one.
    """
    g = pm["grid"]
    src = np.asarray(src, dtype=np.float64)
    if src.shape[-2:] != (g["ny"], g["nx"]):
        raise ValueError(f"expected (..., {g['ny']}, {g['nx']}) for the {g['name']} grid, got {src.shape}")
    out = np.full(src.shape[:-2] + (pm["h"], pm["w"]), np.nan)
    ok = pm["inside"]
    if method == "nearest":
        i = np.clip(np.floor(pm["fc"]).astype(int), 0, g["nx"] - 1)
        j = np.clip(np.floor(pm["fr"]).astype(int), 0, g["ny"] - 1)
        part = np.where(ok, src[..., j, i], np.nan)
    elif method == "bilinear":
        fx = np.clip(pm["fc"] - 0.5, 0, g["nx"] - 1); fy = np.clip(pm["fr"] - 0.5, 0, g["ny"] - 1)
        i0 = np.minimum(np.floor(fx).astype(int), g["nx"] - 2); j0 = np.minimum(np.floor(fy).astype(int), g["ny"] - 2)
        ax = fx - i0; ay = fy - j0
        num = np.zeros(src.shape[:-2] + fx.shape); den = np.zeros(src.shape[:-2] + fx.shape)
        for dj, di, wt in ((0, 0, (1 - ay) * (1 - ax)), (0, 1, (1 - ay) * ax), (1, 0, ay * (1 - ax)), (1, 1, ay * ax)):
            c = src[..., j0 + dj, i0 + di]
            good = ~np.isnan(c)
            num += np.where(good, c, 0.0) * wt
            den += good * wt
        with np.errstate(invalid="ignore", divide="ignore"):
            part = num / den
        part = np.where(ok & (den > 1e-9), part, np.nan)
    else:
        raise ValueError(method)
    out[..., pm["rows"], :] = part
    return out


def read_nsidc_concentration(path: str, grid: dict):
    """One Sea Ice Index monthly concentration GeoTIFF -> (conc, raw).

    conc  float (ny, nx), fraction 0..1; the pole hole is ice (1.0, as NSIDC counts it for
          extent); coast, land and missing are NaN.
    raw   the file's own uint16 codes, for the masks.
    The georeferencing is READ from the file and must match `grid`: pixel size, the outer corner
    of the top-left pixel, the EPSG code and the raster shape."""
    import tifffile
    with tifffile.TiffFile(path) as t:
        pg = t.pages[0]
        raw = pg.asarray()
        scale = pg.tags["ModelPixelScaleTag"].value
        tie = pg.tags["ModelTiepointTag"].value
        keys = pg.tags["GeoKeyDirectoryTag"].value
    geo = {keys[k]: keys[k + 3] for k in range(4, len(keys), 4)}
    if raw.shape != (grid["ny"], grid["nx"]):
        raise ValueError(f"{path}: shape {raw.shape}, expected {(grid['ny'], grid['nx'])}")
    if tuple(scale[:2]) != (grid["cell"], grid["cell"]) or tuple(tie[:2]) != (0.0, 0.0) or tuple(tie[3:5]) != (grid["x0"], grid["y0"]):
        raise ValueError(f"{path}: georeferencing {scale} {tie} is not the {grid['name']} grid")
    if geo.get(3072) != grid["epsg"] or geo.get(1025) != 1:      # ProjectedCSType; RasterPixelIsArea
        raise ValueError(f"{path}: EPSG {geo.get(3072)}, raster type {geo.get(1025)}; expected {grid['epsg']}, 1 (pixel is area)")
    known = (raw <= 1000) | np.isin(raw, (NSIDC_POLE, NSIDC_COAST, NSIDC_LAND, NSIDC_MISSING))
    if not known.all():
        raise ValueError(f"{path}: unknown codes {np.unique(raw[~known])[:8]}")
    conc = np.where(raw <= 1000, raw / 1000.0, np.nan)
    conc[raw == NSIDC_POLE] = 1.0
    return conc, raw


# --- administrative codes ------------------------------------------------------------------
# Natural Earth ADM0_A3 -> World Bank country code. Only the ones that differ.
_WB = {"KOS": "XKX", "SDS": "SSD", "PSX": "PSE", "SAH": None, "CYN": None, "SOL": None,
       "KAS": None, "ATA": None, "ATF": None, "FLK": None, "TWN": None, "ESH": None,
       "ALD": None, "IOA": None, "HMD": None, "SGS": None, "IOT": None, "PCN": None,
       "NFK": None, "COK": None, "NIU": None, "WLF": None, "SPM": None, "BLM": None,
       "SHN": None, "MSR": None, "AIA": None, "VAT": None, "GGY": None, "JEY": None}


def wb_code(adm0_a3: str):
    """World Bank code for a Natural Earth unit, or None if the Bank publishes no series for
    it. None means NO STATISTICS - never a neighbour's or a parent's."""
    return _WB.get(adm0_a3, adm0_a3)
