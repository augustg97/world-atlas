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
