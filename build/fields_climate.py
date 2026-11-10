#!/usr/bin/env python3
"""Climatology atlases: atmosphere (360x180 x 12 months) and ocean (1440x720 and 720x360 x 12).

    ./venv/bin/python build/fields_climate.py            # atmo + ocean + currents
    ./venv/bin/python build/fields_climate.py atmo

Each atlas is one lossless PNG: twelve canonical months stacked top to bottom (January first).
All decoding constants are written to web/fields/climate.json - the app reads them from there,
so the encoding is stated exactly once.

Frames (SCOPE section 6), all converted by frames.resample_grid:
  NCEP R1 surface/pressure   2.5 deg NODE grid, 0..357.5 E, 90..-90
  NCEP R1 Gaussian (T62)     192 x 94, irregular latitudes, 0..358.125 E
  GPCP v2.3                  2.5 deg CELL grid, 1.25..358.75 E, -88.75..88.75
  OISST v2.1                 0.25 deg CELL grid, 0.125..359.875 E, -89.875..89.875
  NSIDC Sea Ice Index v4     25 km polar stereographic (EPSG:3411 / 3412), 304x448 north and
                             316x332 south, one grid per month and year; frames.resample_polar
  GODAS                      1 x 1/3 deg velocity points, 1..360 E, -74..65 (no Arctic)
"""
from __future__ import annotations

import json
import os
import sys

import netCDF4
import numpy as np
from PIL import Image
from scipy import ndimage

import frames as F

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "web", "fields")
CACHE = os.path.join(DATA, "_cache")
DODS = "https://psl.noaa.gov/thredds/dodsC/Datasets"
LAPSE = 6.5          # K per km, the standard-atmosphere value; stated in the app's About panel

ENC = {}             # name -> {"lo":, "hi":, "curve": "linear"|"sqrt"|"ssqrt", "units":}


def enc(name, a, lo, hi, curve="linear", units=""):
    ENC[name] = {"lo": lo, "hi": hi, "curve": curve, "units": units}
    x = (np.asarray(a, dtype=np.float64) - lo) / (hi - lo)
    if curve == "sqrt":
        x = np.sqrt(np.clip(x, 0, 1))
    elif curve == "ssqrt":                      # signed sqrt about the midpoint
        s = x * 2 - 1
        x = 0.5 + 0.5 * np.sign(s) * np.sqrt(np.clip(np.abs(s), 0, 1))
    clipped = float(((x < 0) | (x > 1)).mean())
    if clipped > 0.002:
        print(f"  WARNING {name}: {clipped:.2%} of samples outside [{lo}, {hi}]")
    return np.clip(np.round(np.nan_to_num(x, nan=0.0) * 255), 0, 255).astype(np.uint8)


def atlas(name, r, g, b):
    """r, g, b: (12, h, w) uint8 -> one PNG, months stacked vertically."""
    m, h, w = r.shape
    img = np.zeros((m * h, w, 3), np.uint8)
    for i, c in enumerate((r, g, b)):
        img[..., i] = c.reshape(m * h, w)
    p = os.path.join(OUT, name)
    Image.fromarray(img).save(p, optimize=True)
    print(f"  wrote {name} {w}x{h}x{m}  {os.path.getsize(p) / 1e6:.2f} MB")


def local(name):
    return netCDF4.Dataset(os.path.join(DATA, "psl", name))


def at(a, lon, lat):
    h, w = a.shape[-2:]
    i, j = F.lonlat_to_px(lon, lat, w, h)
    return a[..., j, i]


def isccp_monthly(W, H):
    """Cloud amount by kind for each month, from ISCCP H-series monthly means of 2007-2016 (1 degree).

    Returns, each (12, H, W) on the canonical frame, 0..1: total cloud amount; `deck`, the share of sky under
    stratocumulus and stratus sheets; `cu`, the share under thin broken low and middle cloud (cumulus,
    altocumulus); and `light`, the mean reflectance of ALL THE REST (fronts, storms, high cloud): each kind's
    amount times the reflectance its own mean optical thickness gives, summed. Amount alone is the wrong
    driver for a picture: over the Congo in April ISCCP finds 74% cloud, most of it thin cirrus and anvil
    with an optical thickness under 3.6, and three VIIRS scenes there average a reflectance of 0.22.

    ISCCP sorts cloud by retrieved top pressure and optical thickness, and two of its habits matter here.
    Under a strong inversion it puts the top of a stratocumulus deck too high: off Peru in September it
    reports 19% stratocumulus and 28% "liquid altostratus" where the sky is one deck. So liquid altostratus
    counts as deck wherever there is little high cloud above it, and as frontal cloud otherwise. And over
    bright desert it reports thin low cloud that is not there; the shader ignores `cu` where it never rains.
    """
    import glob
    cache = os.path.join(CACHE, "isccp_2007_2016.npz")
    if os.path.exists(cache):
        return dict(np.load(cache))
    files = sorted(glob.glob(os.path.join(DATA, "isccp", "ISCCP-Basic.HGM.*.nc")))
    if len(files) < 120:
        raise SystemExit(f"ISCCP: {len(files)} of 120 monthly files in data/isccp; run build/fetch_sources.py isccp")
    acc = {k: np.zeros((12, 180, 360)) for k in ("total", "deck", "cu", "light", "deck_light", "cu_light")}
    cnt = {k: np.zeros((12, 180, 360)) for k in acc}
    lon = lat = None
    for f in files:
        d = netCDF4.Dataset(f)
        m = int(os.path.basename(f).split(".")[5]) - 1
        lon, lat = np.asarray(d["lon"][:]), np.asarray(d["lat"][:])
        t = np.ma.filled(d["cldamt_types"][0].astype(np.float64), np.nan) / 100.0        # (18, lat, lon)
        tot = np.ma.filled(d["cldamt"][0].astype(np.float64), np.nan) / 100.0
        high = t[[12, 13, 14, 15, 16, 17]].sum(0)
        under_clear_sky = np.clip(1.0 - high / 0.20, 0.0, 1.0)                           # little cloud above 440 hPa
        tau = np.ma.filled(d["tau_types"][0].astype(np.float64), np.nan)
        # two-stream reflectance of a layer of optical thickness tau with the Sun 40 degrees from overhead
        # (the shader's CLOUD_MU); where a kind is absent its tau is missing and its amount is zero
        refl = np.nan_to_num(0.075 * tau / (0.75 + 0.075 * tau)) * np.nan_to_num(t)
        w7 = t[7] * under_clear_sky
        r7 = refl[7] * under_clear_sky
        rest = [6 + 2, 9 + 1, 9 + 2, 12, 13, 14, 15, 16, 17]          # nimbostratus, altostratus (ice), all high cloud
        v = {"total": tot,
             "deck": t[[1, 2, 4, 5]].sum(0) + w7,
             "cu": t[[0, 3, 6, 9]].sum(0),
             "light": refl[rest].sum(0) + (refl[7] - r7),
             "deck_light": refl[[1, 2, 4, 5]].sum(0) + r7,
             "cu_light": refl[[0, 3, 6, 9]].sum(0)}
        for k in acc:
            ok = np.isfinite(v[k])
            acc[k][m][ok] += v[k][ok]; cnt[k][m][ok] += 1
        d.close()
    out = {}
    for k in acc:
        a = np.where(cnt[k] > 0, acc[k] / np.maximum(cnt[k], 1), np.nan)
        a = F.resample_grid(a, lon, lat, W, H)
        out[k] = np.clip(fill_nearest(a), 0.0, 1.0)
    # Poleward of 70 degrees ISCCP cannot tell cloud from ice by kind (blocky equal-area cells, polar night):
    # the kinds fade out there and only the total is used.
    lat_c = np.abs(F.canon_lat(H))[None, :, None]
    keep = np.clip((80.0 - lat_c) / 10.0, 0.0, 1.0)
    for k in ("deck", "cu"):
        out[k] = out[k] * keep
    # poleward of 80 the light of deck and cumulus goes to `light`, so no cloud is lost when the kinds fade
    out["light"] = out["light"] + (out["deck_light"] + out["cu_light"]) * (1 - keep)
    np.savez_compressed(cache, **out)
    return out


def step_atmo():
    print("atmosphere")
    W, H = 360, 180

    def grid(fname, var, sel=None):
        d = local(fname)
        v = d[var][:] if sel is None else d[var][sel]
        v = np.ma.filled(np.ma.masked_invalid(v).astype(np.float64), np.nan)
        return F.resample_grid(v, d["lon"][:], d["lat"][:], W, H)

    u = grid("uwnd.sig995.mon.ltm.nc", "uwnd")
    v = grid("vwnd.sig995.mon.ltm.nc", "vwnd")
    slp = grid("slp.mon.ltm.nc", "slp")
    t2 = grid("air.2m.mon.ltm.nc", "air") - 273.15
    cld_r1 = grid("tcdc.eatm.mon.ltm.nc", "tcdc") / 100.0
    # Cloud is the satellite's, not the reanalysis's: NCEP R1 has almost none of the stratocumulus decks
    # (measured against VIIRS scenes off Peru: 16% bright cloud in the atlas, 45% in the photographs).
    ic = isccp_monthly(W, H)
    cld, deck, cu, light = ic["total"], ic["deck"], ic["cu"], ic["light"]
    pr = grid("precip.mon.ltm.nc", "precip")
    lev = list(local("uwnd.mon.ltm.nc")["level"][:])
    k = lev.index(250.0)
    u250 = grid("uwnd.mon.ltm.nc", "uwnd", (slice(None), k))
    v250 = grid("vwnd.mon.ltm.nc", "vwnd", (slice(None), k))

    # sea-level-reduced temperature: the app recovers T at any pixel as T0 - LAPSE * z_fine.
    # z here is the terrain as the reanalysis sees it: ETOPO smoothed to roughly T62 (~2 deg).
    z1 = np.maximum(np.load(os.path.join(CACHE, "elev_1deg.npy")), 0.0)
    zs = ndimage.gaussian_filter(z1, sigma=(1.0, 1.0), mode=("nearest", "wrap"))
    t0 = t2 + LAPSE * zs[None] / 1000.0

    # landmarks - these fail if a grid is flipped or shifted
    assert at(t2[6], 10, 25) > 28 and at(t2[0], 100, -80) > at(t2[6], 100, -80), "Sahara hot in July; Antarctic warmer in January"
    assert at(t2[6], 100, -80) < -45, "East Antarctic plateau in July"
    assert at(u[6], -140, 12) < -3 and at(u[6], 60, -50) > 5, "NE trades easterly; roaring forties westerly"
    assert at(pr[6], 88, 24) > 8 and at(pr[0], 88, 24) < 2, "Bengal monsoon: wet July, dry January"
    assert at(pr[0], -60, -5) > 5 and at(pr[6], 25, 23) < 0.3, "Amazon wet season; Sahara dry"
    assert at(slp[0], -20, 63) < 1002 and at(slp[6], -35, 35) > 1020, "Icelandic low; Azores high"
    assert at(u250[0], 140, 33) > 50, "the winter jet over Japan"
    wts = np.cos(np.radians(F.canon_lat(H)))[:, None] * np.ones((1, W))
    print(f"  global mean cloud: ISCCP {np.average(cld.mean(0), weights=wts):.2f} (observed about 0.67), reanalysis {np.average(np.nan_to_num(cld_r1).mean(0), weights=wts):.2f}")
    dl, cl = ic["deck_light"], ic["cu_light"]
    print(f"  shares of the sky: deck {np.average(deck.mean(0), weights=wts):.3f}, cu {np.average(cu.mean(0), weights=wts):.3f};  "
          f"mean reflectance of the rest {np.average(light.mean(0), weights=wts):.3f}")
    print(f"  reflectance of a deck where there is one: {np.nansum(dl * wts) / np.nansum(deck * wts):.2f};  of broken low cloud: {np.nansum(cl * wts) / np.nansum(cu * wts):.2f}")
    print(f"  all cloud, mean reflectance: {np.average((light + dl + cl).mean(0), weights=wts):.3f}  (the Earth's clouds return about 0.2 of sunlight)")
    for nm, (lo, la, mo) in {"Namibia Sep": (5, -15, 8), "Peru Sep": (-85, -20, 8), "California Jul": (-125, 30, 6), "Barbados Feb": (-52, 14, 1),
                             "Amazon Aug": (-60, -5, 7), "Congo Apr": (22, 1, 3), "warm pool Jan": (150, 5, 0), "N Atlantic Sep": (-40, 45, 8), "Sahara Jul": (10, 23, 6)}.items():
        print(f"    {nm:15s} total {at(cld[mo], lo, la):.2f} (R1 {at(cld_r1[mo], lo, la):.2f})  deck {at(deck[mo], lo, la):.2f}  cu {at(cu[mo], lo, la):.2f}  light {at(light[mo], lo, la):.3f}  all light {at((light + dl + cl)[mo], lo, la):.3f}")
    assert at(deck[8], 5, -15) > 0.5 and at(deck[8], -85, -20) > 0.35, "the Namibian and Peruvian stratocumulus decks in September"
    assert at(deck[6], -125, 30) > 0.3 and at(deck[6], 10, 23) < 0.05, "the Californian deck in July; no deck over the Sahara"
    assert at(light[0], 150, 5) > 0.10 and at(light[6], 10, 23) < 0.03, "bright cloud over the warm pool, almost none over the Sahara"
    assert at(cld[6], 10, 23) < 0.30 and at(cld[0], -40, 55) > 0.75, "clear Sahara, overcast North Atlantic winter"
    assert (deck + cu <= cld + 0.25).mean() > 0.98, "sheets and broken cloud do not add up to more than the total"
    print(f"  global mean T2m: Jan {np.average(t2[0], weights=np.cos(np.radians(F.canon_lat(H)))[:, None] * np.ones((1, W))):.2f} C, "
          f"Jul {np.average(t2[6], weights=np.cos(np.radians(F.canon_lat(H)))[:, None] * np.ones((1, W))):.2f} C  (observed ~12.5 / ~16)")

    atlas("atmoA.png", enc("u10", u, -32, 32, units="m/s"), enc("v10", v, -32, 32, units="m/s"),
          enc("t0", t0, -55, 50, units="C at sea level"))
    atlas("atmoB.png", enc("slp", slp, 960, 1060, units="hPa"), enc("cloud", cld, 0, 1, units="fraction"),
          enc("precip", pr, 0, 40, "sqrt", units="mm/day"))
    atlas("atmoC.png", enc("u250", u250, -90, 90, units="m/s"), enc("v250", v250, -90, 90, units="m/s"),
          np.zeros_like(enc("u10", u, -32, 32, units="m/s")))
    atlas("cloudT.png", enc("deck", deck, 0, 1, units="fraction"), enc("cu", cu, 0, 1, units="fraction"),
          enc("light", light, 0, 0.75, "sqrt", units="mean reflectance"))
    np.save(os.path.join(CACHE, "cloud_frac.npy"), cld.astype(np.float32))


def psl_months(fname, var, path):
    """(12, nlat, nlon) from the local file if it is intact, else month by month over OPeNDAP
    (PSL's file server truncates large downloads under load; OPeNDAP does not). Cached."""
    cache = os.path.join(CACHE, f"psl_{var}.npz")
    if os.path.exists(cache):
        z = np.load(cache)
        return z["a"], z["lon"], z["lat"]
    try:
        d = local(fname)
        a = d[var][:]
        print(f"  {var}: local file")
    except OSError:
        print(f"  {var}: local file missing or truncated, reading over OPeNDAP")
        import time
        d = netCDF4.Dataset(f"{DODS}/{path}")
        months = []
        for m in range(12):
            part = os.path.join(CACHE, f"psl_{var}_{m:02d}.npy")
            if not os.path.exists(part):
                for attempt in range(8):                 # PSL answers 429 to bursts
                    try:
                        np.save(part, np.ma.filled(np.ma.masked_invalid(d[var][m]).astype(np.float32), np.nan))
                        break
                    except RuntimeError:
                        time.sleep(45 * (attempt + 1))
                        d = netCDF4.Dataset(f"{DODS}/{path}")
                else:
                    raise SystemExit(f"could not read {var} month {m + 1} from PSL")
                time.sleep(12)
            months.append(np.load(part))
        a = np.stack(months)
    a = np.ma.filled(np.ma.masked_invalid(a).astype(np.float32), np.nan)
    np.savez(cache, a=a, lon=np.asarray(d["lon"][:]), lat=np.asarray(d["lat"][:]))
    return a, np.asarray(d["lon"][:]), np.asarray(d["lat"][:])


def fill_nearest(a):
    """Extend valid values into NaN cells (nearest neighbour) so texture filtering at a coast
    never blends in junk. The validity mask ships separately and is what says 'no data'."""
    out = np.empty_like(a)
    for m in range(a.shape[0]):
        bad = np.isnan(a[m])
        idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
        out[m] = a[m][idx[0], idx[1]]
    return out


# --- sea ice: one typical year from NSIDC's thirty --------------------------------------------
ICE_YEARS = range(1991, 2021)
ICE_THRESHOLD = 0.15         # the Sea Ice Index's cutoff, and the one web/js/dash.js counts with
ICE_IN_BYTE, ICE_OUT_BYTE = 40, 36       # the count threshold is 38.25 of 255: two bytes clear on either side, so a
                                         # decoder that is off by one cannot move 1-2 million km2 across the line
ICE_FILL_CELLS = 4.0         # a cell NSIDC does not observe borrows from an ocean cell at most 100 km away
ICE_WATER_MIN = 0.02         # ...and only if the atlas draws water in it (water.webp, cell mean)
_HEMI = (("N", F.NSIDC_NORTH), ("S", F.NSIDC_SOUTH))


def nsidc_stack(letter, grid):
    """(30, 12, ny, nx) monthly concentration 1991-2020 as fractions: NaN on NSIDC's land and
    coast, 1.0 in the pole hole. Every file's georeferencing is checked against frames.py."""
    out = np.empty((len(ICE_YEARS), 12, grid["ny"], grid["nx"]), np.float32)
    for yi, yr in enumerate(ICE_YEARS):
        for m in range(12):
            p = os.path.join(DATA, "nsidc", grid["name"], f"{letter}_{yr}{m + 1:02d}_concentration_v4.0.tif")
            if not os.path.exists(p):
                raise SystemExit(f"missing {p}: run build/fetch_sources.py nsidc")
            conc, raw = F.read_nsidc_concentration(p, grid)
            if (raw == F.NSIDC_MISSING).any():
                raise SystemExit(f"{p} has missing cells; the 30-year statistics assume none")
            out[yi, m] = conc
    ocean = ~np.isnan(out)
    if not (ocean == ocean[0, 0]).all():
        raise SystemExit(f"NSIDC {grid['name']}: the land mask changes between files")
    return out


def nsidc_extent_csv(letter):
    """NSIDC's own monthly extent and area, (30, 12) each, million km2: the mean of that month's
    DAILY extents (user guide section on monthly extent), not the extent of the monthly-mean grid."""
    import csv
    ext = np.full((len(ICE_YEARS), 12), np.nan); area = ext.copy()
    for m in range(12):
        for row in csv.reader(open(os.path.join(DATA, "nsidc", "extent", f"{letter}_{m + 1:02d}_extent_v4.0.csv"))):
            if row and row[0].strip().isdigit() and int(row[0]) in ICE_YEARS:
                ext[int(row[0]) - ICE_YEARS[0], m] = float(row[4]); area[int(row[0]) - ICE_YEARS[0], m] = float(row[5])
    if np.isnan(ext).any() or (ext < 0).any():
        raise SystemExit(f"NSIDC {letter} extent tables are incomplete for {ICE_YEARS[0]}-{ICE_YEARS[-1]}")
    return ext, area


class IceFrame:
    """One NSIDC grid against the canonical raster and the atlas's own ocean.

    A canonical cell is OBSERVED where its centre falls in an NSIDC ocean cell. NSIDC's 25 km
    land mask turns every cell that touches land into 'coast', so fjords, straits and the
    channels of the Canadian archipelago are land to it while the atlas draws water there. Such
    a cell borrows from the nearest observed ocean cell, at most ICE_FILL_CELLS away, and only if
    the atlas draws water in it: a valid-ocean cell that is all land or ice shelf on screen would
    add to the extent and show nothing (the fill would be +19% of the Antarctic February extent
    without that rule, +4% with it)."""

    def __init__(self, grid, valid, water, w, h):
        self.grid, self.w, self.h = grid, w, h
        self.pm = F.polar_map(grid, w, h)
        self.sl = slice(0, h // 2) if grid["sign"] > 0 else slice(h // 2, h)
        self.cell_km2 = F.polar_cell_area_km2(grid)
        self.area = (F.cell_area_km2(w, h) * np.ones((1, w)))[self.sl]
        self.valid = valid[self.sl]
        self.ocean = None
        self.water = water[self.sl]

    def set_ocean(self, ocean):
        """ocean: (ny, nx) bool, NSIDC's ocean cells (the pole hole included)."""
        self.ocean = ocean
        dist, idx = ndimage.distance_transform_edt(~ocean, return_indices=True)
        self.near = (idx[0], idx[1]); self.reach = dist <= ICE_FILL_CELLS
        seen = np.nan_to_num(F.resample_polar(ocean.astype(float), self.pm, "nearest")[self.sl]) > 0.5
        self.observed = seen
        self.unseen = self.valid & ~seen & (self.water < ICE_WATER_MIN)      # valid ocean, not observed, drawn as land: no ice
        self.borrowed = self.valid & ~seen & ~self.unseen                     # filled from the nearest observed cell (if in reach)

    def filled(self, a):
        """Native field (..., ny, nx) with land and coast taking the nearest ocean cell's value."""
        return np.where(self.reach, a[..., self.near[0], self.near[1]], np.nan)

    def to_canon(self, a, method):
        """Native field -> this hemisphere's canonical rows, coast filled, zero where the atlas has no sea to put it in."""
        c = F.resample_polar(self.filled(a), self.pm, method)[..., self.sl, :]
        return np.where(self.unseen, 0.0, np.nan_to_num(c, nan=0.0))

    def extent(self, iced):
        """Million km2 the way web/js/dash.js counts it: valid cells, whole spherical cell areas."""
        return ((iced & self.valid) * self.area).sum((-2, -1)) / 1e6


def ice_peryear_check(frames, stacks, verbose=True):
    """Each of the 720 monthly grids on its own: extent (>= 15%) counted on the canonical raster
    the way the dashboard counts, against (a) the same grid counted on NSIDC's cells with their
    true areas and (b) NSIDC's published extent for that month. (a) tests the conversion and the
    coast handling and nothing else. (b) also contains NSIDC's own definition gap: its monthly
    extent is the mean of the daily extents, and a monthly-MEAN grid clears 15% wherever ice sat
    for a fifth of the month."""
    out = {}
    for letter, grid in _HEMI:
        fr, c = frames[letter], stacks[letter]
        csv_ext, _ = nsidc_extent_csv(letter)
        native = ((np.nan_to_num(c) >= ICE_THRESHOLD) * fr.cell_km2).sum((2, 3)) / 1e6
        canon = np.stack([fr.extent(fr.to_canon(c[y], "nearest") >= ICE_THRESHOLD) for y in range(c.shape[0])])
        bare = np.stack([((np.nan_to_num(F.resample_polar(c[y], fr.pm, "nearest")[..., fr.sl, :]) >= ICE_THRESHOLD) * fr.area).sum((1, 2)) / 1e6
                         for y in range(c.shape[0])])
        e_conv = (canon - native) / native * 100
        e_bare = (bare - native) / native * 100
        e_def = (native - csv_ext) / csv_ext * 100
        e_csv = (canon - csv_ext) / csv_ext * 100

        def dist(e):
            return {"median": round(float(np.median(e)), 2), "p05": round(float(np.percentile(e, 5)), 2),
                    "p95": round(float(np.percentile(e, 95)), 2), "worst": round(float(e.flat[np.abs(e).argmax()]), 2),
                    "by_month_mean": [round(float(x), 2) for x in e.mean(0)]}
        out[grid["name"]] = {"canonical_vs_native_pct": dist(e_conv), "projection_only_vs_native_pct": dist(e_bare),
                             "native_vs_nsidc_csv_pct": dist(e_def), "canonical_vs_nsidc_csv_pct": dist(e_csv),
                             "nsidc_csv_extent_mkm2": [[round(float(x), 2) for x in r] for r in csv_ext],
                             "canonical_extent_mkm2": [[round(float(x), 3) for x in r] for r in canon]}
        if verbose:
            for k in ("projection_only_vs_native_pct", "canonical_vs_native_pct", "native_vs_nsidc_csv_pct", "canonical_vs_nsidc_csv_pct"):
                v = out[grid["name"]][k]
                print(f"    {grid['name']:5s} {k:32s} median {v['median']:+6.2f}  p05 {v['p05']:+6.2f}  p95 {v['p95']:+6.2f}  worst {v['worst']:+6.2f}")
    return out


def ice_typical_year(frames, stacks, verbose=True):
    """Twelve concentration fields for ONE typical year, on the canonical raster, and their diagnostics.

    The atlas shows one year, and anything that counts or draws its ice edge uses 15% of that
    field. So the 15% line has to enclose the area a typical year's ice covers: the 1991-2020
    mean of NSIDC's monthly extents. Three fields that do NOT do that, each measured on NSIDC's
    own cells against NSIDC's own extent (see Research/modeling/REGISTER-ice.md):
      the mean concentration        +4..+20% Arctic, +6..+30% Antarctic (a cell iced one year in five clears 15%)
      the median ice edge           -8..+14% (ice frequency is not symmetric about one half, least of all in an
                                    Antarctic summer, when little ice is left and it is somewhere else every year)
      any one fixed threshold       the level that works runs from 16% to 28% with the month
    What is shipped: rank every cell by how often it is iced (the share of the thirty years whose
    monthly mean is at least 15%; ties by mean concentration), and take cells from the top of
    that ranking until their area, counted as the dashboard counts it, reaches NSIDC's mean
    extent for the month. Inside that line the value is the plain 30-year mean concentration.
    Outside it the value is the same mean, held under 15% (clipped at 14.1%) so that nothing
    downstream counts it and the field stays continuous for the month-to-month blend and the
    drawn edge. 0.7-2.3 million km2 a month sits on that clip: ice that is there in some years.

    Frequency and mean are computed on NSIDC's cells and interpolated bilinearly, so the line is
    a smooth contour between cell centres, not a staircase of 25 km blocks.
    """
    w = frames["N"].w; h = frames["N"].h
    ice = np.zeros((12, h, w)); inside = np.zeros((12, h, w), bool)
    diag = {}
    for letter, grid in _HEMI:
        fr, c = frames[letter], stacks[letter]
        target = nsidc_extent_csv(letter)[0].mean(0)
        c0 = np.nan_to_num(c, nan=0.0)
        freq = (c0 >= ICE_THRESHOLD).mean(0)                     # (12, ny, nx)
        cbar = c0.mean(0)
        rank = freq + cbar / (len(ICE_YEARS) + 1)                # frequency first, mean concentration breaks ties
        rank_c = fr.to_canon(rank, "bilinear"); cbar_c = np.clip(fr.to_canon(cbar, "bilinear"), 0, 1)
        freq_c = fr.to_canon(freq, "nearest")
        d = {k: [] for k in ("target_mkm2", "shipped_mkm2", "level_frequency", "level_on_nsidc_cells", "median_edge_native_mkm2",
                             "mean_field_native_mkm2", "mean_of_yearly_native_mkm2", "borrowed_iced_mkm2", "observed_lost_mkm2",
                             "inside_lifted_pct", "area_shipped_mkm2")}
        for m in range(12):
            ok = fr.valid & (rank_c[m] > 0)
            order = np.argsort(-rank_c[m][ok], kind="stable")
            cum = np.cumsum(fr.area[ok][order]) / 1e6
            k = int(np.searchsorted(cum, target[m]))             # cum[k-1] < target <= cum[k]: take whichever is nearer
            if k > 0 and (k == cum.size or target[m] - cum[k - 1] < cum[k] - target[m]):
                k -= 1
            if k >= cum.size - 1:
                raise SystemExit(f"{grid['name']} month {m + 1}: NSIDC's mean extent {target[m]:.2f} is more ice than the 30 years ever show")
            level = float(rank_c[m][ok][order][k])
            ins = rank_c[m] >= level
            v = np.where(ins, np.maximum(cbar_c[m], (ICE_IN_BYTE + 0.2) / 255), np.minimum(cbar_c[m], ICE_OUT_BYTE / 255))
            ice[m, fr.sl] = v; inside[m, fr.sl] = ins
            # the same question asked on NSIDC's own cells, with their true areas
            A = fr.cell_km2
            o = np.argsort(-rank[m][fr.ocean], kind="stable")
            cumn = np.cumsum(A[fr.ocean][o]) / 1e6
            d["level_on_nsidc_cells"].append(round(float(rank[m][fr.ocean][o][min(int(np.searchsorted(cumn, target[m])), cumn.size - 1)]), 3))
            d["target_mkm2"].append(round(float(target[m]), 3))
            d["shipped_mkm2"].append(round(float(fr.extent(ins)), 3))
            d["level_frequency"].append(round(level, 3))
            d["median_edge_native_mkm2"].append(round(float(((freq[m] >= 0.5) * A).sum() / 1e6), 3))
            d["mean_field_native_mkm2"].append(round(float(((cbar[m] >= ICE_THRESHOLD) * A).sum() / 1e6), 3))
            d["mean_of_yearly_native_mkm2"].append(round(float((freq[m] * A).sum() / 1e6), 3))
            d["borrowed_iced_mkm2"].append(round(float(((ins & fr.borrowed) * fr.area).sum() / 1e6), 3))
            seen_ice = np.nan_to_num(F.resample_polar((rank[m] >= level).astype(float), fr.pm, "nearest")[fr.sl]) > 0.5
            d["observed_lost_mkm2"].append(round(float(((seen_ice & ~fr.valid) * fr.area).sum() / 1e6), 3))
            d["inside_lifted_pct"].append(round(float(((ins & fr.valid & (cbar_c[m] < ICE_THRESHOLD)) * fr.area).sum() / max(1e-9, (ins & fr.valid) .__mul__(fr.area).sum()) * 100), 3))
            d["area_shipped_mkm2"].append(round(float(((ins & fr.valid) * v * fr.area).sum() / 1e6), 3))
        diag[grid["name"]] = d
        if verbose:
            def row(k, f="{:6.2f}"):
                return " ".join(f.format(x) for x in d[k])
            print(f"  {grid['name']}: million km2 by month")
            print("    NSIDC mean of yearly extents  " + row("target_mkm2"))
            print("    shipped (>= 15%, as counted)   " + row("shipped_mkm2"))
            print("    ice frequency at the shipped line " + row("level_frequency", "{:5.2f}") + "   (0.50 would be the median edge)")
            print("    same, solved on NSIDC's cells     " + row("level_on_nsidc_cells", "{:5.2f}"))
            print("    median edge, NSIDC cells       " + row("median_edge_native_mkm2"))
            print("    mean field >= 15%, NSIDC cells " + row("mean_field_native_mkm2"))
            print("    iced cells borrowed at coasts  " + row("borrowed_iced_mkm2", "{:6.3f}"))
            print("    iced NSIDC cells the atlas calls land " + row("observed_lost_mkm2", "{:6.3f}"))
    return ice, inside, diag


def step_ocean():
    print("ocean")
    W, H = 1440, 720
    sst, lon, lat = psl_months("sst.mon.ltm.nc", "sst", "noaa.oisst.v2.highres/sst.mon.ltm.1991-2020.nc")
    sst = F.resample_grid(sst, lon, lat, W, H)
    valid = ~np.isnan(sst)
    assert (valid == valid[0]).all(), "the OISST ocean mask is the same in every month"

    # Sea ice is NOT OISST's. Its long-term-mean ice field ran 11-31% over the NSIDC Sea Ice Index
    # in the Arctic and 16-94% over in the Antarctic however it was thresholded (REGISTER-ice.md,
    # 2026-11-09). The field is rebuilt from NSIDC's own monthly grids, year by year.
    wpath = os.path.join(CACHE, "water4.npy")
    if not os.path.exists(wpath):
        raise SystemExit("missing data/_cache/water4.npy: run build/fields_surface.py water first (the sea-ice coast fill needs the atlas's water)")
    water = F.reduce_aligned(np.load(wpath).astype(np.float32), W, H)
    frames, stacks = {}, {}
    for letter, grid in _HEMI:
        stacks[letter] = nsidc_stack(letter, grid)
        frames[letter] = IceFrame(grid, valid[0], water, W, H)
        frames[letter].set_ocean(~np.isnan(stacks[letter][0, 0]))
    print("  sea ice, each of the 720 monthly grids on its own (% error in extent):")
    chk = ice_peryear_check(frames, stacks)
    for name in ("north", "south"):
        v = chk[name]["canonical_vs_native_pct"]
        assert abs(v["median"]) < 2.0 and abs(v["worst"]) < 5.0, f"NSIDC {name}: the canonical raster does not reproduce the grid's own extent: {v}"
    ice, inside, diag = ice_typical_year(frames, stacks)
    json.dump({"per_year": chk, "typical_year": diag}, open(os.path.join(CACHE, "ice_build_report.json"), "w"), indent=1)
    ice = np.where(valid, ice, np.nan)

    # Inland water. NSIDC's index is a SEA-ice index: it carries the Great Lakes, Ladoga, Baikal and
    # Great Bear as cells that are always open, and the Caspian and Azov lie off its grid. Their winter
    # ice is real, so water that does not connect to the world ocean keeps OISST's ice (corrected for
    # PSL's conditional mean, as before). It is marked in the valid channel (200, the sea is 255) so
    # that the sea-ice count leaves it out, as NSIDC's does.
    from scipy import ndimage
    lab, _ = ndimage.label(valid[0])
    sizes = np.bincount(lab.ravel()); sizes[0] = 0
    lake = valid[0] & (lab != sizes.argmax())
    ice_o, lon_o, lat_o = psl_months("icec.mon.ltm.nc", "icec", "noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc")
    nyr, _, _ = psl_months("icec.mon.ltm.nc", "valid_yr_count", "noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc")
    ice_o = np.nan_to_num(ice_o, nan=0.0) * np.clip(np.nan_to_num(nyr, nan=0.0) / 30.0, 0, 1)
    ice_o = np.nan_to_num(F.resample_grid(ice_o, lon_o, lat_o, W, H), nan=0.0)
    if np.nanmax(ice_o) > 1.5:
        ice_o = ice_o / 100.0
    ice = np.where(lake[None], ice_o, ice)
    inside = inside & ~lake[None]
    sea = valid & ~lake[None]
    lake_area = (lake * (F.cell_area_km2(W, H) * np.ones((1, W)))).sum() / 1e6
    print(f"  inland water kept on OISST ice: {lake_area:.2f} M km2 in {len(np.unique(lab[lake]))} bodies")
    # OISST's own mask has no Baikal, Great Bear or Victoria: those lakes still never freeze (register A5).
    assert at(lake, -87.5, 47.7) and at(lake, 51, 42) and at(lake, 31.5, 60.8), "Lake Superior, the Caspian and Ladoga are inland water"
    assert not at(lake, 20, 58) and not at(lake, -85, 60) and not at(lake, -40, -68), "the Baltic, Hudson Bay and the Weddell Sea are the sea"
    assert at(ice[1], -81.2, 42.2) > 0.3 and at(ice[7], -81.2, 42.2) < 0.08, "Lake Erie: ice in February, open in August"
    assert at(ice[2], 31.5, 60.8) > 0.4 and at(ice[7], 31.5, 60.8) == 0, "Lake Ladoga: ice in March, none in August"
    # OISST carries no ice at all on the Caspian or the Sea of Azov, which do freeze in the north: still open (A5).

    assert at(sst[8], -150, 5) > 26 and at(sst[2], 0, -60) < 3, "warm pool; Southern Ocean"
    assert at(ice[2], 0, 85) > 0.9 and at(ice[8], 0, 85) > 0.5, "central Arctic ice"
    assert at(ice[2], 0, 89.9) > 0.97 and at(ice[8], 0, 89.9) > 0.9, "the pole hole is ice"
    assert at(ice[8], -40, -68) > 0.9 and at(ice[1], -40, -68) < at(ice[8], -40, -68) - 0.3, "Weddell Sea: September maximum, February minimum"
    assert at(ice[2], 75, 76) > 0.9 and at(ice[2], 2, 68) < 0.01, "March: the Kara Sea is iced, the Norwegian Sea further south is open"
    assert at(ice[2], -85, 60) > 0.9 and at(ice[8], -85, 60) < 0.05, "Hudson Bay: frozen in March, open in September"
    assert at(ice[2], 145, 58) > 0.7 and at(ice[8], 145, 58) < 0.01, "northern Sea of Okhotsk: iced in March, open in September"
    assert at(ice[2], -20, 62) < 0.01 and at(ice[2], 35, 72) < 0.05, "March: no ice south of Iceland or in the southern Barents Sea"
    assert at(ice[8], -175, -72) > 0.85 and at(ice[1], -175, -76) < 0.15, "Ross Sea: September pack, February open water"
    assert at(ice[8], -60, -58) < 0.02 and at(ice[8], 20, -50) < 0.02, "September: Drake Passage and the ocean south of Africa are open"
    assert not at(valid[0], 10, 23) and at(valid[0], -150, 0), "Sahara is not ocean; the Pacific is"
    j35 = int(55 / 180 * H)
    assert np.nanmax(ice[:, j35: H - j35]) == 0, "no sea ice within 35 degrees of the equator"
    assert at(ice[0], 122, 40.4) > 0.3 and at(ice[6], 122, 40.4) == 0, "the lowest-latitude sea ice: Liaodong Bay in January"

    b_ice = enc("ice", fill_nearest(ice), 0, 1, units="fraction")
    # the one number everything downstream reads: valid cells at or above 15%, on the encoded bytes
    area = F.cell_area_km2(W, H) * np.ones((1, W))
    counted = (b_ice >= ICE_THRESHOLD * 255) & sea
    assert (counted == (inside & sea)).all(), "the encoded 15% line is the line that was solved for"
    for name, sl in (("north", slice(0, H // 2)), ("south", slice(H // 2, H))):
        ext = (counted[:, sl] * area[sl]).sum((1, 2)) / 1e6
        tgt = np.array(diag[name]["target_mkm2"])
        err = (ext - tgt) / tgt * 100
        print(f"  {name} sea-ice extent, shipped bytes (10^6 km2): " + " ".join(f"{e:.2f}" for e in ext))
        print(f"  {name} NSIDC 1991-2020 mean of yearly extents: " + " ".join(f"{e:.2f}" for e in tgt) + f"   (largest gap {np.abs(err).max():.2f}%)")
        assert np.abs(err).max() < 0.5, f"{name}: shipped extent is off NSIDC's mean by {err}"

    # OISST's quarter-degree mask stops short of the real shore, and the shader draws ice and SST only where
    # this channel says so: that left a strip of open water between the pack and the coast of Hudson Bay.
    # Two cells past the mask are marked 180: drawn (both fields are already filled outward), not counted.
    shore = ndimage.binary_dilation(valid[0], iterations=2) & ~valid[0]
    vch = np.where(lake[None], 200, valid * 255)
    vch = np.where(shore[None] & ~valid, 180, vch).astype(np.uint8)
    atlas("oceanA.png", enc("sst", fill_nearest(sst), -2, 35, units="C"), b_ice, vch)
    np.save(os.path.join(CACHE, "ice_extent_valid.npy"), valid[0])


def step_currents():
    print("currents (GODAS over OPeNDAP, 2019-2023 mean)")
    W, H = 720, 360
    us, vs = [], []
    lon = lat = None
    for yr in range(2019, 2024):
        for var, acc in (("ucur", us), ("vcur", vs)):
            cache = os.path.join(CACHE, f"godas_{var}_{yr}.npy")
            if not os.path.exists(cache):
                d = netCDF4.Dataset(f"{DODS}/godas/{var}.{yr}.nc")
                a = np.ma.filled(np.ma.masked_invalid(d[var][:, 0, :, :]).astype(np.float32), np.nan)
                a[np.abs(a) > 50] = np.nan
                np.save(cache, a)
                np.save(os.path.join(CACHE, "godas_lon.npy"), np.asarray(d["lon"][:]))
                np.save(os.path.join(CACHE, "godas_lat.npy"), np.asarray(d["lat"][:]))
                print(f"  fetched {var} {yr}")
            acc.append(np.load(cache))
    lon = np.load(os.path.join(CACHE, "godas_lon.npy")); lat = np.load(os.path.join(CACHE, "godas_lat.npy"))
    u = np.nanmean(np.stack(us), axis=0); v = np.nanmean(np.stack(vs), axis=0)
    u = F.resample_grid(u, lon, lat, W, H); v = F.resample_grid(v, lon, lat, W, H)
    # resample_grid clamps beyond the source's last latitude: GODAS stops at 65 N and 74 S,
    # and beyond that there is NO DATA - mask it rather than smear the last row to the pole.
    la = F.canon_lat(H)[:, None]
    outside = (la > lat.max()) | (la < lat.min())
    u[:, outside[:, 0]] = np.nan; v[:, outside[:, 0]] = np.nan
    valid = ~np.isnan(u)
    assert at(u[6], -72, 37) > 0.05, f"Gulf Stream flows east off Hatteras, got {at(u[6], -72, 37)}"
    assert at(u[6], -120, 0.5) < -0.05, "South Equatorial Current flows west"
    assert at(u[0], 142, 35) > 0.05, "Kuroshio extension flows east"
    assert at(u[0], 10, -50) > 0.02, "Antarctic Circumpolar Current flows east"
    assert not at(valid[0], 0, 80), "no GODAS data in the Arctic"
    sp = np.hypot(u, v)
    print(f"  surface speed: p50 {np.nanpercentile(sp, 50):.3f}  p99 {np.nanpercentile(sp, 99):.3f}  max {np.nanmax(sp):.2f} m/s")
    atlas("oceanB.png", enc("ucur", fill_nearest(u), -2, 2, "ssqrt", units="m/s"),
          enc("vcur", fill_nearest(v), -2, 2, "ssqrt", units="m/s"), (valid * 255).astype(np.uint8))


def main():
    args = sys.argv[1:] or ["atmo", "ocean", "currents"]
    meta_path = os.path.join(OUT, "climate.json")
    if os.path.exists(meta_path):
        ENC.update(json.load(open(meta_path)).get("encodings", {}))
        ENC.pop("deep", None)            # a channel that existed for an hour; `light` replaced it
    def save_meta():
        json.dump({
            "note": "Twelve canonical months stacked vertically, January first. value = lo + (hi-lo)*decode(byte/255); "
                    "decode is identity (linear), x^2 (sqrt) or signed x^2 about 0.5 (ssqrt).",
            "lapse_K_per_km": LAPSE,
            "atlases": {
                "atmoA": {"file": "atmoA.png", "w": 360, "h": 180, "channels": ["u10", "v10", "t0"]},
                "atmoB": {"file": "atmoB.png", "w": 360, "h": 180, "channels": ["slp", "cloud", "precip"]},
                "atmoC": {"file": "atmoC.png", "w": 360, "h": 180, "channels": ["u250", "v250", None]},
                "cloudT": {"file": "cloudT.png", "w": 360, "h": 180, "channels": ["deck", "cu", "light"]},
                "oceanA": {"file": "oceanA.png", "w": 1440, "h": 720, "channels": ["sst", "ice", "valid"]},
                "oceanB": {"file": "oceanB.png", "w": 720, "h": 360, "channels": ["ucur", "vcur", "valid"]},
            },
            "periods": {"atmo": "1991-2020 monthly means (NCEP/NCAR R1; GPCP v2.3)",
                        "cloud": "2007-2016 monthly means (ISCCP H-series HGM): total cloud and its amount by kind",
                        "ocean": "sea-surface temperature: 1991-2020 monthly means (NOAA OISST v2.1)",
                        "ice": "one typical year of 1991-2020: mean concentration inside the line that encloses the mean "
                               "of the yearly extents (NSIDC Sea Ice Index, Version 4, G02135, monthly 25 km grids)",
                        "currents": "2019-2023 monthly means, 5 m depth (NCEP GODAS)"},
            "encodings": ENC,
        }, open(meta_path, "w"), indent=1)

    for a in args:
        {"atmo": step_atmo, "ocean": step_ocean, "currents": step_currents}[a]()
        save_meta()          # after EVERY step: a later step that fails must not lose an earlier step's encodings
    need = {"u10", "v10", "t0", "slp", "cloud", "deck", "cu", "light", "precip", "u250", "v250", "sst", "ice", "ucur", "vcur"}
    missing = need - set(ENC)
    if missing:
        raise SystemExit(f"climate.json is missing encodings for {sorted(missing)}: rebuild those steps")
    from stamp import stamp
    stamp()
    print("climate: done")


if __name__ == "__main__":
    main()
