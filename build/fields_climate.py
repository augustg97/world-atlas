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
    cld = grid("tcdc.eatm.mon.ltm.nc", "tcdc") / 100.0
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
    print(f"  global mean T2m: Jan {np.average(t2[0], weights=np.cos(np.radians(F.canon_lat(H)))[:, None] * np.ones((1, W))):.2f} C, "
          f"Jul {np.average(t2[6], weights=np.cos(np.radians(F.canon_lat(H)))[:, None] * np.ones((1, W))):.2f} C  (observed ~12.5 / ~16)")

    atlas("atmoA.png", enc("u10", u, -32, 32, units="m/s"), enc("v10", v, -32, 32, units="m/s"),
          enc("t0", t0, -55, 50, units="C at sea level"))
    atlas("atmoB.png", enc("slp", slp, 960, 1060, units="hPa"), enc("cloud", cld, 0, 1, units="fraction"),
          enc("precip", pr, 0, 40, "sqrt", units="mm/day"))
    atlas("atmoC.png", enc("u250", u250, -90, 90, units="m/s"), enc("v250", v250, -90, 90, units="m/s"),
          np.zeros_like(enc("u10", u, -32, 32, units="m/s")))
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


def step_ocean():
    print("ocean")
    W, H = 1440, 720
    sst, lon, lat = psl_months("sst.mon.ltm.nc", "sst", "noaa.oisst.v2.highres/sst.mon.ltm.1991-2020.nc")
    ice, _, _ = psl_months("icec.mon.ltm.nc", "icec", "noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc")
    # PSL's long-term mean of ice concentration is CONDITIONAL: it averages only the years in
    # which the cell had ice, so it overstates extent everywhere ice is intermittent (measured:
    # Antarctic February extent 12.3 against NSIDC's 3.0 million km2). valid_yr_count is the
    # number of those years; concentration x (years with ice / 30) is the unconditional mean.
    nyr, _, _ = psl_months("icec.mon.ltm.nc", "valid_yr_count", "noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc")
    print(f"  ice valid_yr_count: max {np.nanmax(nyr):.0f} (expect 30)")
    ice = np.nan_to_num(ice, nan=0.0) * np.clip(np.nan_to_num(nyr, nan=0.0) / 30.0, 0, 1)
    sst = F.resample_grid(sst, lon, lat, W, H)
    ice = F.resample_grid(ice, lon, lat, W, H)
    if np.nanmax(ice) > 1.5:
        ice = ice / 100.0
    valid = ~np.isnan(sst)
    ice = np.where(valid, np.nan_to_num(ice, nan=0.0), np.nan)

    assert at(sst[8], -150, 5) > 26 and at(sst[2], 0, -60) < 3, "warm pool; Southern Ocean"
    assert at(ice[2], 0, 85) > 0.9 and at(ice[8], 0, 85) > 0.5, "central Arctic ice"
    assert at(ice[8], -40, -68) > 0.9 and at(ice[1], -40, -68) < at(ice[8], -40, -68) - 0.3, "Weddell Sea: September maximum, February minimum"
    assert not at(valid[0], 10, 23) and at(valid[0], -150, 0), "Sahara is not ocean; the Pacific is"
    area = F.cell_area_km2(W, H) * np.ones((1, W))
    for name, sl in (("Arctic", slice(0, H // 2)), ("Antarctic", slice(H // 2, H))):
        ext = [(np.nan_to_num(ice[m, sl]) >= 0.15).astype(float).__mul__(area[sl]).sum() / 1e6 for m in range(12)]
        print(f"  {name} sea-ice extent (10^6 km2) by month: " + " ".join(f"{e:.1f}" for e in ext))
    print("    NSIDC 1991-2020: Arctic ~15.3 (Mar) .. ~6.2 (Sep);  Antarctic ~3.0 (Feb) .. ~18.5 (Sep)")

    atlas("oceanA.png", enc("sst", fill_nearest(sst), -2, 35, units="C"), enc("ice", fill_nearest(ice), 0, 1, units="fraction"),
          (valid * 255).astype(np.uint8))
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
    def save_meta():
        json.dump({
            "note": "Twelve canonical months stacked vertically, January first. value = lo + (hi-lo)*decode(byte/255); "
                    "decode is identity (linear), x^2 (sqrt) or signed x^2 about 0.5 (ssqrt).",
            "lapse_K_per_km": LAPSE,
            "atlases": {
                "atmoA": {"file": "atmoA.png", "w": 360, "h": 180, "channels": ["u10", "v10", "t0"]},
                "atmoB": {"file": "atmoB.png", "w": 360, "h": 180, "channels": ["slp", "cloud", "precip"]},
                "atmoC": {"file": "atmoC.png", "w": 360, "h": 180, "channels": ["u250", "v250", None]},
                "oceanA": {"file": "oceanA.png", "w": 1440, "h": 720, "channels": ["sst", "ice", "valid"]},
                "oceanB": {"file": "oceanB.png", "w": 720, "h": 360, "channels": ["ucur", "vcur", "valid"]},
            },
            "periods": {"atmo": "1991-2020 monthly means (NCEP/NCAR R1; GPCP v2.3)",
                        "ocean": "1991-2020 monthly means (NOAA OISST v2.1)",
                        "currents": "2019-2023 monthly means, 5 m depth (NCEP GODAS)"},
            "encodings": ENC,
        }, open(meta_path, "w"), indent=1)

    for a in args:
        {"atmo": step_atmo, "ocean": step_ocean, "currents": step_currents}[a]()
        save_meta()          # after EVERY step: a later step that fails must not lose an earlier step's encodings
    need = {"u10", "v10", "t0", "slp", "cloud", "precip", "u250", "v250", "sst", "ice", "ucur", "vcur"}
    missing = need - set(ENC)
    if missing:
        raise SystemExit(f"climate.json is missing encodings for {sorted(missing)}: rebuild those steps")
    from stamp import stamp
    stamp()
    print("climate: done")


if __name__ == "__main__":
    main()
