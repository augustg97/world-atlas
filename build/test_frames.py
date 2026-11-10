#!/usr/bin/env python3
"""Tests for build/frames.py.  ./venv/bin/python build/test_frames.py

Each source layout the project actually ingests is rebuilt synthetically from an analytic
field f(lon, lat), pushed through the conversion, and compared with f at the canonical pixel
centres - including at Greenwich, the antimeridian and both poles. A flipped, shifted or
half-cell-misregistered grid fails here rather than on screen.
"""
import sys

import numpy as np

import frames as F


def f(lon, lat):
    """Smooth, periodic in longitude, asymmetric in every direction."""
    lo, la = np.radians(lon), np.radians(lat)
    return 3.0 * np.sin(lo) * np.cos(la) + 2.0 * np.sin(la) + np.cos(2 * lo + 0.3) * np.cos(la) ** 2


def truth(w, h):
    return f(F.canon_lon(w)[None, :], F.canon_lat(h)[:, None])


def check(name, got, want, tol):
    err = float(np.nanmax(np.abs(got - want)))
    ok = err < tol and not np.isnan(got).any()
    print(f"  {'ok  ' if ok else 'FAIL'} {name:46s} max err {err:.4f} (tol {tol})")
    return ok


def main():
    W, H = 720, 360
    T = truth(W, H)
    ok = True

    # NCEP R1 pressure/surface: 2.5 deg, NODE registered, 0..357.5 E, 90..-90 (N to S)
    lons = np.arange(0, 360, 2.5); lats = np.arange(90, -90.1, -2.5)
    ok &= check("NCEP 2.5deg node grid, 0-360, N->S", F.resample_grid(f(lons[None], lats[:, None]), lons, lats, W, H), T, 0.02)

    # NCEP T62 Gaussian: 192 lons from 0, 94 irregular lats N->S (88.542 .. -88.542)
    glats = np.degrees(np.arcsin(np.polynomial.legendre.leggauss(94)[0]))[::-1]
    glons = np.arange(192) * 1.875
    g = F.resample_grid(f(glons[None], glats[:, None]), glons, glats, W, H)
    inner = np.abs(F.canon_lat(H)) < 88.5   # beyond the last Gaussian latitude the value is clamped, by design
    ok &= check("NCEP Gaussian T62, irregular lats", g[inner], T[inner], 0.02)

    # OISST: 0.25 deg CELL registered, 0.125..359.875 E, -89.875..89.875 (S to N)
    lons = np.arange(0.125, 360, 0.25); lats = np.arange(-89.875, 90, 0.25)
    ok &= check("OISST 0.25deg cell grid, 0-360, S->N", F.resample_grid(f(lons[None], lats[:, None]), lons, lats, W, H), T, 0.002)

    # GPCP: 2.5 deg CELL registered, 1.25..358.75, -88.75..88.75 (S to N)
    lons = np.arange(1.25, 360, 2.5); lats = np.arange(-88.75, 90, 2.5)
    g = F.resample_grid(f(lons[None], lats[:, None]), lons, lats, W, H)
    inner = np.abs(F.canon_lat(H)) < 88.75
    ok &= check("GPCP 2.5deg cell grid, 0-360, S->N", g[inner], T[inner], 0.02)

    # stacked (time, lat, lon) input keeps its leading axis
    st = np.stack([f(lons[None], lats[:, None])] * 3)
    ok &= F.resample_grid(st, lons, lats, 90, 45).shape == (3, 45, 90)

    # ETOPO-like: fine, aligned, -180..180, S->N  ->  reduce_aligned with flip
    w0, h0 = 2160, 1080
    lons = -180 + (np.arange(w0) + 0.5) * 360 / w0; lats = -90 + (np.arange(h0) + 0.5) * 180 / h0
    ok &= check("fine aligned S->N raster, area mean (ETOPO)", F.reduce_aligned(f(lons[None], lats[:, None]), W, H, flip_ns=True), T, 0.002)
    # non-integer ratio, as 21600 -> 8192
    ok &= check("non-integer reduction ratio", F.reduce_aligned(f(lons[None], lats[:, None]), 500, 250, flip_ns=True), truth(500, 250), 0.004)

    # bin_sum: a misregistered fine grid (GHSL starts at -180.0079, 89.0996; ships at -180.0128, 85.0)
    for name, lon0, lat0, d, n_lon, n_lat in [("GHSL-like offset grid", -180.00791593, 89.09958318, 1 / 120, 43202 // 20, 21384 // 20),
                                               ("ship-density-like offset grid", -180.012811275 - 0.005, 85.000147937 + 0.005, 0.01, 36003 // 20, 16999 // 20)]:
        d2 = d * 20                                    # 20x coarser so the test is quick; same registration
        lon_c = lon0 + (np.arange(n_lon) + 0.5) * d2
        lat_c = lat0 - (np.arange(n_lat) + 0.5) * d2
        acc = np.zeros((90, 180))
        vals = np.ones((n_lat, n_lon))
        F.bin_sum(vals, lon_c, lat_c, acc)
        tot_ok = abs(acc.sum() - vals.sum()) < 1e-6
        # a spike at a known place must land in the right canonical cell
        spike = np.zeros((n_lat, n_lon))
        jj = int((lat0 - 48.8566) / d2); ii = int((2.3522 - lon0) / d2)
        spike[jj, ii] = 1
        acc2 = np.zeros((90, 180)); F.bin_sum(spike, lon_c, lat_c, acc2)
        ci, cj = F.lonlat_to_px(2.3522, 48.8566, 180, 90)
        near = acc2[max(0, cj - 1):cj + 2, max(0, ci - 1):ci + 2].sum() == 1 and acc2[cj, ci] + acc2[cj, ci - 1] + acc2[cj, (ci + 1) % 180] >= 0
        good = tot_ok and near
        print(f"  {'ok  ' if good else 'FAIL'} {name:46s} sum conserved, spike lands at Paris")
        ok &= good

    # landmarks: pixel addressing
    assert F.lonlat_to_px(-180.0, 90.0, 360, 180) == (0, 0)
    assert F.lonlat_to_px(179.999, -89.999, 360, 180) == (359, 179)
    assert F.lonlat_to_px(0.0, 0.0, 360, 180) == (180, 90)
    assert F.lonlat_to_px(180.0, 0.0, 360, 180)[0] == 0        # the antimeridian wraps
    assert abs(F.cell_area_km2(360, 180).sum() * 360 - 4 * np.pi * F.R_EARTH_KM ** 2) < 1.0
    assert F.wb_code("KOS") == "XKX" and F.wb_code("FRA") == "FRA" and F.wb_code("TWN") is None
    print("  ok   pixel addressing, cell areas sum to the sphere, admin codes")

    print("\nframes: ALL PASS" if ok else "\nframes: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
