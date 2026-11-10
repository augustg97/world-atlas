#!/usr/bin/env python3
"""Tests for build/frames.py.  ./venv/bin/python build/test_frames.py

Each source layout the project actually ingests is rebuilt synthetically from an analytic
field f(lon, lat), pushed through the conversion, and compared with f at the canonical pixel
centres - including at Greenwich, the antimeridian and both poles. A flipped, shifted or
half-cell-misregistered grid fails here rather than on screen.
"""
import os
import sys

import numpy as np

import frames as F

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# NSIDC, "A Guide to NSIDC's Polar Stereographic Projection", tables 6 and 7: x km, y km, lat, lon E
# of the four outer corners and four side midpoints of each 25 km grid, as published (0.01 deg).
NSIDC_PUBLISHED = {
    "north": [(-3850, 5850, 30.98, 168.35), (0, 5850, 39.43, 135.00), (3750, 5850, 31.37, 102.34), (3750, 0, 56.35, 45.00),
              (3750, -5350, 34.35, 350.03), (0, -5350, 43.28, 315.00), (-3850, -5350, 33.92, 279.26), (-3850, 0, 55.50, 225.00)],
    "south": [(-3950, 4350, -39.23, 317.76), (0, 4350, -51.32, 0.00), (3950, 4350, -39.23, 42.24), (3950, 0, -54.66, 90.00),
              (3950, -3950, -41.45, 135.00), (0, -3950, -54.66, 180.00), (-3950, -3950, -41.45, 225.00), (-3950, 0, -54.66, 270.00)],
}


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


def nsidc_tests():
    """NSIDC's two sea-ice grids (EPSG:3411 / 3412) -> canonical. The projection is tested against
    NSIDC's published table, the cell areas against the ellipsoid, the resampling against an
    analytic field, and the whole chain against real places in real files."""
    ok = True
    for g in (F.NSIDC_NORTH, F.NSIDC_SOUTH):
        tab = NSIDC_PUBLISHED[g["name"]]
        # the published corners and midpoints: inverse to the table's rounding, forward to ~1 km
        worst_deg = worst_km = 0.0
        for xk, yk, la, lo in tab:
            lon, lat = F.polar_stereo_lonlat(xk * 1e3, yk * 1e3, g)
            worst_deg = max(worst_deg, abs(float(lat) - la), abs(((float(lon) - lo) + 180) % 360 - 180) * np.cos(np.radians(la)))
            x, y = F.polar_stereo_xy(lo, la, g)
            worst_km = max(worst_km, float(np.hypot(x - xk * 1e3, y - yk * 1e3)) / 1e3)
        good = worst_deg < 0.006 and worst_km < 1.0
        print(f"  {'ok  ' if good else 'FAIL'} {'NSIDC ' + g['name'] + ' published corners':46s} max err {worst_deg:.4f} deg, {worst_km:.2f} km (table is rounded to 0.01 deg)")
        ok &= good
        # the grid's own outline must be those corners: x0/y0 and the raster size
        x1 = g["x0"] + g["nx"] * g["cell"]; y1 = g["y0"] - g["ny"] * g["cell"]
        assert {(g["x0"] / 1e3, g["y0"] / 1e3), (x1 / 1e3, g["y0"] / 1e3), (x1 / 1e3, y1 / 1e3), (g["x0"] / 1e3, y1 / 1e3)} == \
               {(t[0], t[1]) for t in tab[0::2]}, "grid outline is the published one"
        # round trip, and the pole: a pixel CORNER on both grids, the same one from every longitude
        lon = np.array([-179.9, -90.0, -45.0, 0.0, 33.3, 135.0, 180.0]); lat = g["sign"] * np.array([35.0, 50.0, 60.0, 70.0, 80.0, 89.0, 89.99])
        lo2, la2 = F.polar_stereo_lonlat(*F.polar_stereo_xy(lon, lat, g), g)
        rt = float(np.max(np.abs(la2 - lat)) + np.max(np.abs((lo2 - lon + 180) % 360 - 180) * np.cos(np.radians(lat))))
        pole = [F.polar_px(lo, g["sign"] * 90.0, g) for lo in (-180.0, -45.0, 0.0, 77.0)]
        want = (154.0, 234.0) if g["sign"] > 0 else (158.0, 174.0)
        good = rt < 1e-9 and all(abs(c - want[0]) < 1e-6 and abs(r - want[1]) < 1e-6 for c, r in pole)
        print(f"  {'ok  ' if good else 'FAIL'} {'NSIDC ' + g['name'] + ' round trip; pole at col,row ' + str(want):46s} round trip {rt:.1e} deg")
        ok &= good
        # which way is up: the meridian that runs straight down (north) or up (south) the grid from the pole
        c, r = F.polar_px(g["lon0"], g["sign"] * 80.0, g)
        assert abs(c - want[0]) < 1e-6 and (r > want[1] if g["sign"] > 0 else r < want[1]), "central meridian orientation"
        c, r = F.polar_px(g["lon0"] + 90.0, g["sign"] * 80.0, g)
        assert abs(r - want[1]) < 1e-6 and c > want[0], "90 degrees east of the central meridian is to the right"
        # cell areas: NSIDC states 382..664 km2 (north) and 443..664 km2 (south); their sum poleward of
        # 70 degrees must be the ellipsoid's cap
        A = F.polar_cell_area_km2(g)
        xs = g["x0"] + (np.arange(g["nx"]) + 0.5) * g["cell"]; ys = g["y0"] - (np.arange(g["ny"]) + 0.5) * g["cell"]
        _, clat = F.polar_stereo_lonlat(xs[None, :], ys[:, None], g)
        e, b = F.HUGHES_E, F.HUGHES_B / 1e3

        def zone(phi):                       # ellipsoid area from the equator to geodetic latitude phi
            sn = np.sin(np.radians(phi))
            return np.pi * b * b * (sn / (1 - e * e * sn * sn) + np.log((1 + e * sn) / (1 - e * sn)) / (2 * e))
        cap = zone(90.0) - zone(70.0)
        got = float((A * (np.abs(clat) >= 70.0)).sum())
        lo_a, hi_a = (382.0, 664.5) if g["sign"] > 0 else (443.0, 664.5)
        good = abs(got / cap - 1) < 1e-3 and lo_a <= A.min() < lo_a + 2 and hi_a - 1 < A.max() <= hi_a
        print(f"  {'ok  ' if good else 'FAIL'} {'NSIDC ' + g['name'] + ' cell areas':46s} {A.min():.1f}..{A.max():.1f} km2; cap poleward of 70: {got / 1e6:.4f} vs ellipsoid {cap / 1e6:.4f} M km2")
        ok &= good
        # an analytic field sampled at the grid's cell centres comes back right on the canonical raster
        W, H = 720, 360
        clon, clat = F.polar_stereo_lonlat(xs[None, :], ys[:, None], g)
        pm = F.polar_map(g, W, H)
        T = truth(W, H)
        inner = np.zeros((H, W), bool)
        inner[pm["rows"]] = (pm["fc"] > 1) & (pm["fc"] < g["nx"] - 1) & (pm["fr"] > 1) & (pm["fr"] < g["ny"] - 1)
        for method, tol in (("bilinear", 0.002), ("nearest", 0.02)):
            got = F.resample_polar(f(clon, clat), pm, method)
            ok &= check(f"NSIDC {g['name']} 25 km grid, {method}", got[inner], T[inner], tol)
        other = F.canon_lat(H) * g["sign"] < 0
        assert np.isnan(F.resample_polar(f(clon, clat), pm, "nearest")[other]).all(), "nothing lands in the other hemisphere"
        assert inner[0 if g["sign"] > 0 else H - 1].all(), "the pole row is inside the grid"

    # the sphere the atlas measures area on, against the ellipsoid NSIDC measures on: this is a
    # property of the canonical frame (CLAUDE.md), and it is why an extent counted on the canonical
    # raster reads 0.7-0.9% under the same cells counted with NSIDC's areas
    sph = 2 * np.pi * F.R_EARTH_KM ** 2 * (1 - np.sin(np.radians(70.0)))
    assert -0.009 < sph / cap - 1 < -0.007, sph / cap - 1
    print(f"  ok   spherical cell areas poleward of 70 run {100 * (1 - sph / cap):.2f}% under the ellipsoid's")

    # real files: georeferencing read from the tags, then real places
    files = [(F.NSIDC_NORTH, os.path.join(DATA, "nsidc", "north", "N_199103_concentration_v4.0.tif")),
             (F.NSIDC_SOUTH, os.path.join(DATA, "nsidc", "south", "S_199109_concentration_v4.0.tif"))]
    if not all(os.path.exists(p) for _, p in files):
        print("  SKIP NSIDC real-file landmarks: data/nsidc is not fetched (build/fetch_sources.py nsidc)")
        return ok
    import tifffile
    W, H = 1440, 720
    for g, path in files:
        with tifffile.TiffFile(path) as t:
            pg = t.pages[0]
            scale = pg.tags["ModelPixelScaleTag"].value; tie = pg.tags["ModelTiepointTag"].value
            keys = pg.tags["GeoKeyDirectoryTag"].value; text = pg.tags["GeoAsciiParamsTag"].value
            shape = pg.shape
        geo = {keys[k]: keys[k + 3] for k in range(4, len(keys), 4)}
        assert shape == (g["ny"], g["nx"]) and scale[0] == scale[1] == g["cell"], (shape, scale)
        assert tie[0] == tie[1] == 0 and (tie[3], tie[4]) == (g["x0"], g["y0"]), tie      # pixel (0,0)'s outer corner
        assert geo[3072] == g["epsg"] and geo[1025] == 1 and geo[3076] == 9001, geo            # EPSG; pixel-is-area; metres
        assert "Hughes 1980" in text and ("North" if g["sign"] > 0 else "South") in text, text
        conc, raw = F.read_nsidc_concentration(path, g)
        pm = F.polar_map(g, W, H)
        near = F.resample_polar(conc, pm, "nearest"); bil = F.resample_polar(conc, pm, "bilinear")

        def at(a, lon, lat):
            i, j = F.lonlat_to_px(lon, lat, W, H)
            return a[j, i]
        if g["sign"] > 0:                                   # March 1991
            assert (raw == F.NSIDC_POLE).sum() == 468 and at(near, 0, 89.9) == 1.0 and at(near, 180, 89.9) == 1.0, "the pole hole is filled as ice"
            for a in (near, bil):
                assert at(a, 75, 76) > 0.95 and at(a, 2, 68) == 0, "Kara Sea iced, Norwegian Sea open"
                assert at(a, -85, 60) > 0.95 and at(a, -65, 73) > 0.95, "Hudson Bay and Baffin Bay iced"
                assert at(a, 35, 72) == 0 and at(a, -20, 62) == 0 and at(a, -30, 50) == 0, "Barents Sea and the Atlantic south of Iceland open"
                assert 0.2 < at(a, 148, 55) < 0.8 and at(a, -175, 62) > 0.8, "Sea of Okhotsk partly iced; northern Bering Sea iced"
                assert np.isnan(at(a, -40, 72)) and np.isnan(at(a, 100, 65)), "Greenland and Siberia are land"
            assert np.isnan(at(near, 50, 46)) and np.isnan(at(near, -150, 50)), "the northern Caspian and 50N 150W are outside the grid"
        else:                                               # September 1991
            assert not (raw == F.NSIDC_POLE).any(), "no pole hole in the south: the pole is land"
            for a in (near, bil):
                assert at(a, -40, -68) > 0.8 and at(a, -175, -72) > 0.8 and at(a, -85, -70) > 0.8, "Weddell, Ross and Bellingshausen Seas iced"
                assert at(a, 80, -62) > 0.7 and at(a, -55, -72) > 0.9, "Indian-sector pack; western Weddell"
                assert at(a, -60, -58) == 0 and at(a, 20, -50) == 0 and at(a, -120, -55) == 0, "Drake Passage, south of Africa, South Pacific open"
                assert np.isnan(at(a, 100, -75)) and np.isnan(at(a, 0, -89.9)) and np.isnan(at(a, -175, -81)), "the ice sheet, the pole and the Ross Ice Shelf are land"
            assert np.isnan(at(near, 140, -68)) and at(near, -40, -68) > 0.8, "a half-turn would swap Adelie Land for the Weddell Sea"
            assert np.isnan(at(near, 60, -72)) and at(near, -55, -72) > 0.9, "a mirror would swap Dronning Maud Land for the western Weddell"
        # the grid's own extent, counted on its cells with their true areas, against NSIDC's table for that month
        ext = float((((raw >= 150) & (raw <= 1000) | (raw == F.NSIDC_POLE)) * F.polar_cell_area_km2(g)).sum() / 1e6)
        table = os.path.join(DATA, "nsidc", "extent", "N_03_extent_v4.0.csv" if g["sign"] > 0 else "S_09_extent_v4.0.csv")
        pub = [float(ln.split(",")[4]) for ln in open(table) if ln.startswith("1991,")][0]
        good = abs(ext / pub - 1) < 0.03                     # the table is the mean of DAILY extents: 1-2% under the monthly grid's
        print(f"  {'ok  ' if good else 'FAIL'} {'NSIDC ' + g['name'] + ' real file: tags, landmarks':46s} extent {ext:.2f} vs published {pub} M km2")
        ok &= good
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

    ok &= nsidc_tests()

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
