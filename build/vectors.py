#!/usr/bin/env python3
"""Feature data: political geometry, places, physical labels, plates, earthquakes, volcanoes,
power stations, airports and modelled air routes, country statistics.  Output: ../web/data/*.json

    ./venv/bin/python build/vectors.py                 # all
    ./venv/bin/python build/vectors.py political places

Coordinates are WGS84 degrees, quantised to 0.01 deg (about 1 km) as integers x100.
Country ids are 1 + index in ADM0_A3 order - the same order fields_human.step_countries uses.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
import urllib.request

import numpy as np

import frames as F

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "web", "data")
CACHE = os.path.join(DATA, "_cache")
os.makedirs(OUT, exist_ok=True)


def ne(name):
    return json.load(open(os.path.join(DATA, "ne", f"{name}.geojson")))["features"]


def q(ring):
    """Quantise a coordinate list to flat [lon*100, lat*100, ...] ints, dropping repeats."""
    out = []
    last = None
    for x, y in ring:
        p = (int(round(x * 100)), int(round(y * 100)))
        if p != last:
            out.extend(p)
            last = p
    return out


def dump(name, obj):
    p = os.path.join(OUT, name)
    json.dump(obj, open(p, "w"), separators=(",", ":"), ensure_ascii=False)
    print(f"  wrote {name} {os.path.getsize(p) / 1e6:.2f} MB")


def get(url, cache_name, tries=5):
    p = os.path.join(CACHE, cache_name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, "rb").read()
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "world-atlas-build/1.0"})
            b = urllib.request.urlopen(req, timeout=120).read()
            open(p, "wb").write(b)
            return b
        except Exception as e:  # noqa: BLE001 - reported, retried, and fatal if it never succeeds
            print(f"  retry {cache_name}: {e}")
            time.sleep(10 * (k + 1))
    raise SystemExit(f"could not fetch {url}")


# The main official language of a country, where Natural Earth carries a translation in it.
# Authored. Used only to show an endonym second, after the English name (SCOPE section 6).
ENDONYM_LANG = {
    "AR": "DZA BHR EGY IRQ JOR KWT LBN LBY MAR MRT OMN QAT SAU SDN SYR TUN ARE YEM PSX SAH",
    "BN": "BGD", "DE": "DEU AUT LIE", "EL": "GRC CYP", "FA": "IRN", "FR": "FRA MCO", "HE": "ISR",
    "HI": "IND", "HU": "HUN", "ID": "IDN", "IT": "ITA SMR", "JA": "JPN", "KO": "KOR PRK",
    "NL": "NLD", "PL": "POL", "PT": "PRT BRA AGO MOZ", "RU": "RUS", "SV": "SWE", "TR": "TUR",
    "UK": "UKR", "UR": "PAK", "VI": "VNM", "ZH": "CHN", "ZHT": "TWN",
    "ES": "ESP MEX ARG COL PER VEN CHL ECU GTM CUB BOL DOM HND PRY SLV NIC CRI PAN URY",
}
LANG_OF = {a3: lang for lang, lst in ENDONYM_LANG.items() for a3 in lst.split()}


# ---------------------------------------------------------------------------- label geometry
# What the label layer needs to choose a place for a name from the state's own shape (register F1):
# its area, the deepest interior point, a few more good interior points, the centre of the largest
# box of each name-like proportion that fits inside it, and how far that deepest point is from open
# water. All of it is geometry of the Natural Earth polygons; none of it is authored.
LABEL_ASPECTS = [1.5, 2.5, 4.0, 6.0, 9.0, 14.0]          # width : height of a name's box
KM_DEG = F.R_EARTH_KM * math.pi / 180


def ring_area_km2(ring):
    """Area enclosed by a lon/lat ring on the sphere: the line integral of sin(lat) d(lon)."""
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        dx = (x2 - x1 + 540.0) % 360.0 - 180.0
        a += math.radians(dx) * (2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(a) * F.R_EARTH_KM ** 2 / 2


def label_geometry(polys):
    """polys: [[exterior, hole, ...], ...] of (lon, lat). Returns area (km2) and, for the MAIN part (the
    largest polygon), lp [lon, lat, r_km] (its pole of inaccessibility) and inner ([lon, lat, width_km]
    per LABEL_ASPECTS: the largest box of that proportion inside it); and pts, further interior points
    [lon, lat, r_km, main] on the main part (main = 1) and on every other part of at least 4% of its area
    (main = 0: Alaska, Svalbard, Guiana - where the name may go only when the main part is out of view).
    Each part is rasterised in its own sinusoidal frame, so a width is true at its own latitude."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    areas = [ring_area_km2(list(p[0])) - sum(ring_area_km2(list(h)) for h in p[1:]) for p in polys]
    order = sorted(range(len(polys)), key=lambda i: -areas[i])
    pts, inner = [], [None] * len(LABEL_ASPECTS)
    for n, pi in enumerate(order[:6]):
        if n and areas[pi] < 0.04 * areas[order[0]]:
            break
        poly = [np.asarray(r, dtype=np.float64)[:, :2] for r in polys[pi]]
        lon0 = (poly[0][:, 0].min() + poly[0][:, 0].max()) / 2

        def xy(r):
            return np.column_stack(((r[:, 0] - lon0) * np.cos(np.radians(r[:, 1])) * KM_DEG, r[:, 1] * KM_DEG))
        e = xy(poly[0])
        x0, y0 = e.min(0); x1, y1 = e.max(0)
        s = max(x1 - x0, y1 - y0, 0.2) / 220.0                      # km per cell
        W, H = int(math.ceil((x1 - x0) / s)) + 4, int(math.ceil((y1 - y0) / s)) + 4
        img = Image.new("L", (W, H), 0)
        dr = ImageDraw.Draw(img)

        def pix(r):
            v = xy(r)
            return [((x - x0) / s + 1.5, (y1 - y) / s + 1.5) for x, y in v]
        dr.polygon(pix(poly[0]), fill=1)
        for hole in poly[1:]:
            dr.polygon(pix(hole), fill=0)
        full = np.asarray(img, dtype=bool)
        m = ndimage.binary_erosion(full)                             # PIL fills boundary pixels: stay inside
        if not m.any():
            m = full
        if not m.any():
            continue

        def back(i, j):
            y = y1 - (i - 1.0) * s; x = x0 + (j - 1.0) * s
            lat = y / KM_DEG
            return lon0 + x / (KM_DEG * max(0.01, math.cos(math.radians(lat)))), lat
        d = ndimage.distance_transform_edt(m) * s
        taken = []
        for _ in range(5):
            i, j = np.unravel_index(int(np.argmax(d)), d.shape)
            r = float(d[i, j])
            if r <= 0 or (taken and r < 0.4 * taken[0][2]):
                break
            taken.append((i, j, r))
            pts.append((r, *back(i, j), 1 if n == 0 else 0))
            ii, jj = np.ogrid[:H, :W]
            d[(ii - i) ** 2 + (jj - j) ** 2 < (2.0 * r / s) ** 2] = 0   # the next point is clear of this one
        I = np.zeros((H + 1, W + 1), dtype=np.int32)
        I[1:, 1:] = m.cumsum(0).cumsum(1)
        for k, a in enumerate(LABEL_ASPECTS):
            def fit(t):
                hh, hw = t, int(round(a * t))
                h, w = 2 * hh + 1, 2 * hw + 1
                if h > H or w > W:
                    return None
                ok = (I[h:, w:] - I[:-h, w:] - I[h:, :-w] + I[:-h, :-w]) == h * w
                if not ok.any():
                    return None
                ii, jj = np.nonzero(ok)
                b = int(np.argmin((ii - ii.mean()) ** 2 + (jj - jj.mean()) ** 2))
                return ii[b] + hh, jj[b] + hw, w * s
            lo, hi, best = 0, max(H, W), fit(0)
            while lo < hi:                                           # the largest half-height that still fits
                mid = (lo + hi + 1) // 2
                r = fit(mid)
                if r:
                    lo, best = mid, r
                else:
                    hi = mid - 1
            if best and n == 0:
                lon, lat = back(best[0], best[1])
                inner[k] = (lon, lat, best[2])
    pts.sort(key=lambda p: (-p[3], -p[0]))                           # the main part's deepest point first
    def row(lon, lat, km):
        return [round(((float(lon) + 180.0) % 360.0) - 180.0, 3), round(float(lat), 3), round(float(km), 1)]
    return {"area": float(sum(areas)), "lp": row(pts[0][1], pts[0][2], pts[0][0]) if pts else None,
            "pts": [row(p[1], p[2], p[0]) + [p[3]] for p in pts[1:6]],
            "inner": [row(*v) if v else None for v in inner]}


def sea_distances(all_polys, points):
    """km from each (lon, lat) to the nearest cell that belongs to no unit, on a 0.05 degree raster of
    every unit's exterior. Lakes that Natural Earth leaves outside the country polygons count as water."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from scipy.spatial import cKDTree
    W, H, c = 7200, 3600, 0.05
    img = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(img)
    for polys in all_polys:
        for poly in polys:
            dr.polygon([((x + 180) / c, (90 - y) / c) for x, y in (pt[:2] for pt in poly[0])], fill=1)
    land = np.asarray(img, dtype=bool)
    shore = ~land & ndimage.binary_dilation(land)
    jj, ii = np.nonzero(shore)

    def xyz(lo, la):
        lo, la = np.radians(lo), np.radians(la)
        return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    tree = cKDTree(xyz(-180 + (ii + 0.5) * c, 90 - (jj + 0.5) * c))
    chord, _ = tree.query(xyz(np.array([p[0] for p in points]), np.array([p[1] for p in points])))
    wt = np.cos(np.radians(90 - (np.arange(H) + 0.5) * c))            # a row's share of the sphere
    return 2 * F.R_EARTH_KM * np.arcsin(np.clip(chord / 2, 0, 1)), float((land.mean(1) * wt).sum() / wt.sum())


def step_political():
    print("political")
    fc = ne("ne_50m_admin_0_countries")
    fc.sort(key=lambda f: f["properties"]["ADM0_A3"])
    from shapely.geometry import Point, shape
    countries, geoms = [], []
    for i, f in enumerate(fc):
        p = f["properties"]
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [[q(r) for r in poly] for poly in polys]
        xs = [x for poly in polys for x, _ in poly[0]]; ys = [y for poly in polys for _, y in poly[0]]
        lang = LANG_OF.get(p["ADM0_A3"])
        endo = p.get(f"NAME_{lang}") if lang else None
        if endo == p["NAME_EN"]:
            endo = None
        countries.append({
            "id": i + 1, "a3": p["ADM0_A3"], "wb": F.wb_code(p["ADM0_A3"]), "name": p["NAME_EN"] or p["NAME"],
            "short": p["NAME"], "formal": p.get("FORMAL_EN"), "endonym": endo, "type": p["TYPE"], "sov": p["SOVEREIGNT"],
            "continent": p["CONTINENT"], "subregion": p["SUBREGION"], "rank": p["LABELRANK"],
            "lon": round(p["LABEL_X"], 3), "lat": round(p["LABEL_Y"], 3),
            "pop": p["POP_EST"], "pop_year": p["POP_YEAR"], "gdp_md": p["GDP_MD"], "gdp_year": p.get("GDP_YEAR"),
            "color": p["MAPCOLOR7"], "note": p.get("NOTE_BRK") or p.get("NOTE_ADM0"),
            # for the label layer (register F1): Natural Earth's own abbreviation, whether this unit is the
            # home part of its sovereignty, and the geometry a name is placed by
            "abbr": p.get("ABBREV") or None, "home": p.get("HOMEPART") == 1,
            "bbox": [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)], "polys": rings})
        lg = label_geometry(polys)
        if lg["lp"] is None or not shape(g).contains(Point(lg["lp"][0], lg["lp"][1])):
            rp = shape(g).representative_point()                     # a unit too small for the raster
            lg["lp"] = [round(rp.x, 4), round(rp.y, 4), lg["lp"][2] if lg["lp"] else 0.0]
        assert shape(g).contains(Point(lg["lp"][0], lg["lp"][1])), f"label point of {p['ADM0_A3']} is outside it"
        # how far the part that holds the label point reaches from it: a name "beside" the state belongs within this
        main = next((pl for pl in polys if shape({"type": "Polygon", "coordinates": pl}).contains(Point(lg["lp"][0], lg["lp"][1]))), polys[0])
        ext = np.asarray(main[0], dtype=np.float64)
        reach = float(np.max(gc_km(lg["lp"][0], lg["lp"][1], ext[:, 0], ext[:, 1])))
        countries[-1].update(area=round(lg["area"], 1), lp=lg["lp"], reach=round(reach, 1), pts=lg["pts"], inner=lg["inner"])
        geoms.append(polys)
    sea, land_frac = sea_distances(geoms, [c["lp"] for c in countries])
    for c, d in zip(countries, sea):
        # a lower bound: the raster is good to about a cell and a half, and water is never nearer than the clear radius
        c["sea"] = round(max(c["lp"][2], float(d) - 8.0), 1)
    # Landmarks. Areas are the polygons' own (50 m generalisation), so the tolerances are loose.
    by = {c["a3"]: c for c in countries}
    assert 0.28 < land_frac < 0.30, f"the units cover {land_frac:.3f} of the sphere on the sea raster; land is 0.292"
    assert abs(by["BRA"]["area"] / 8.51e6 - 1) < 0.03 and abs(by["RUS"]["area"] / 17.1e6 - 1) < 0.03, (by["BRA"]["area"], by["RUS"]["area"])
    assert abs(sum(c["area"] for c in countries) / 148.9e6 - 1) < 0.03, sum(c["area"] for c in countries)
    assert by["VAT"]["area"] < 2 and by["CHE"]["abbr"] == "Switz." and by["USA"]["home"] and not by["GRL"]["home"]
    assert -125 < by["USA"]["lp"][0] < -67 and 25 < by["USA"]["lp"][1] < 49, by["USA"]["lp"]         # the conterminous states, not Alaska
    assert -5 < by["FRA"]["lp"][0] < 8 and 42 < by["FRA"]["lp"][1] < 51, by["FRA"]["lp"]               # France, not Guiana
    assert by["RUS"]["inner"][2][0] > 60, by["RUS"]["inner"]                                            # a name's box fits in Siberia
    assert 120 < by["CHE"]["sea"] < 350 and by["MNG"]["sea"] > 500 and by["NRU"]["sea"] < 10, (by["CHE"]["sea"], by["MNG"]["sea"], by["NRU"]["sea"])
    assert by["CHL"]["lp"][2] < 150 < by["BRA"]["lp"][2], (by["CHL"]["lp"], by["BRA"]["lp"])           # Chile is narrow, Brazil is not
    assert all(q[1] < 72 for q in by["NOR"]["pts"] if q[3]) and any(q[1] > 76 and not q[3] for q in by["NOR"]["pts"]), by["NOR"]["pts"]   # Svalbard is a far part
    assert 900 < by["NOR"]["reach"] < 1500 and by["FRA"]["reach"] < 800, (by["NOR"]["reach"], by["FRA"]["reach"])   # the mainland: not Svalbard, not Guiana
    borders = {"international": [], "disputed": [], "claim": []}
    for f in ne("ne_50m_admin_0_boundary_lines_land"):
        cla = f["properties"]["FEATURECLA"]
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        key = "international" if cla.startswith("International") else "disputed"
        borders[key].extend(q(l) for l in lines)
    claims = []
    for f in ne("ne_50m_admin_0_boundary_lines_disputed_areas"):
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        borders["claim"].extend(q(l) for l in lines)
    disputes = []
    seen = set()
    for f in ne("ne_50m_admin_0_breakaway_disputed_areas"):
        p = f["properties"]
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        big = max(polys, key=lambda poly: len(poly[0]))[0]
        cx = sum(x for x, _ in big) / len(big); cy = sum(y for _, y in big) / len(big)
        name = p.get("BRK_NAME") or p.get("NAME")
        note = p.get("NOTE_BRK")
        if not note or (name, note) in seen:
            continue
        seen.add((name, note))
        disputes.append({"name": name, "note": note, "admin": p.get("ADMIN"), "lon": round(cx, 2), "lat": round(cy, 2),
                         "polys": [[q(poly[0])] for poly in polys], "confidence": "contested"})
    dump("political.json", {"source": "Natural Earth 5.1.2 (public domain), default de facto worldview", "vintage": 2022,
                            "label_aspects": LABEL_ASPECTS, "countries": countries, "borders": borders, "disputes": disputes})
    print(f"  {len(countries)} units, {len(borders['international'])} border lines, {len(borders['disputed'])} disputed lines, "
          f"{len(borders['claim'])} claim lines, {len(disputes)} dispute areas, endonyms on {sum(1 for c in countries if c['endonym'])}")


def step_places():
    print("places")
    rows = []
    for f in ne("ne_10m_populated_places_simple"):
        p = f["properties"]
        rows.append([p["name"], round(p["longitude"], 3), round(p["latitude"], 3), int(p["pop_max"] or 0), p["scalerank"],
                     1 if p["adm0cap"] else 0, p["adm0_a3"], p["adm1name"] or "", p["namealt"] or "", 1 if p["megacity"] else 0])
    rows.sort(key=lambda r: (r[4], -r[3]))
    dump("places.json", {"source": "Natural Earth 5.1.2 populated places (public domain)",
                         "columns": ["name", "lon", "lat", "pop_max", "scalerank", "capital", "a3", "adm1", "altname", "megacity"], "rows": rows})


def rep_point(geom):
    from shapely.geometry import shape
    s = shape(geom)
    if s.geom_type == "MultiPolygon":
        s = max(s.geoms, key=lambda g: g.area)
    pt = s.representative_point()
    return round(pt.x, 2), round(pt.y, 2), s.area


def step_physical():
    print("physical")
    feats = []
    for f in ne("ne_50m_geography_regions_polys"):
        p = f["properties"]
        x, y, area = rep_point(f["geometry"])
        feats.append({"name": p["NAME_EN"] or p["NAME"], "kind": p["FEATURECLA"], "rank": p["SCALERANK"], "lon": x, "lat": y,
                      "size": round(math.sqrt(area), 2), "realm": "land"})
    for f in ne("ne_50m_geography_marine_polys"):
        p = f["properties"]
        x, y, area = rep_point(f["geometry"])
        feats.append({"name": p["name_en"] or p["name"], "kind": p["featurecla"], "rank": p["scalerank"], "lon": x, "lat": y,
                      "size": round(math.sqrt(area), 2), "realm": "sea"})
    peaks = [{"name": f["properties"]["name_en"] or f["properties"]["name"], "elev": f["properties"]["elevation"],
              "kind": f["properties"]["featurecla"], "rank": f["properties"]["scalerank"],
              "lon": round(f["geometry"]["coordinates"][0], 3), "lat": round(f["geometry"]["coordinates"][1], 3)}
             for f in ne("ne_50m_geography_regions_elevation_points")]
    rivers = []
    for f in ne("ne_50m_rivers_lake_centerlines"):
        p = f["properties"]; g = f["geometry"]
        if not g:
            continue
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        rivers.append({"name": p.get("name_en") or p.get("name"), "rank": p["scalerank"], "lines": [q(l) for l in lines]})
    dump("physical.json", {"source": "Natural Earth 5.1.2 (public domain)", "features": feats, "peaks": peaks, "rivers": rivers})
    print(f"  {len(feats)} named regions, {len(peaks)} peaks, {len(rivers)} rivers")


def step_plates():
    print("plates")
    lines = []
    for f in json.load(open(os.path.join(DATA, "plates", "PB2002_boundaries.json")))["features"]:
        p = f["properties"]; g = f["geometry"]
        ls = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for l in ls:
            lines.append({"name": p["Name"], "a": p["PlateA"], "b": p["PlateB"], "subduction": p["Type"] == "subduction", "line": q(l)})
    plates = []
    for f in json.load(open(os.path.join(DATA, "plates", "PB2002_plates.json")))["features"]:
        p = f["properties"]
        x, y, _ = rep_point(f["geometry"])
        plates.append({"code": p["Code"], "name": p["PlateName"], "lon": x, "lat": y})
    dump("plates.json", {"source": "Bird, P. (2003) An updated digital model of plate boundaries, G-cubed 4(3) 1027 (PB2002); GeoJSON by H. Ahlenius, ODC PDDL",
                         "boundaries": lines, "plates": plates})


def step_quakes():
    print("earthquakes (USGS ComCat, M>=6, 2000-2025)")
    rows = []
    for y0, y1 in ((2000, 2013), (2013, 2026)):
        url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&minmagnitude=6"
               f"&starttime={y0}-01-01&endtime={y1}-01-01&orderby=time-asc")
        txt = get(url, f"usgs_m6_{y0}_{y1}.csv").decode()
        for r in csv.DictReader(txt.splitlines()):
            rows.append([r["time"][:16], round(float(r["longitude"]), 2), round(float(r["latitude"]), 2),
                         round(float(r["depth"] or 0)), float(r["mag"]), r["place"]])
    dump("quakes.json", {"source": "USGS ANSS Comprehensive Earthquake Catalog (public domain)", "span": "2000-01-01 to 2025-12-31, M >= 6",
                         "columns": ["time_utc", "lon", "lat", "depth_km", "mag", "place"], "rows": rows})
    mags = np.array([r[4] for r in rows])
    print(f"  {len(rows)} events; M>=7: {(mags >= 7).sum()}, M>=8: {(mags >= 8).sum()}  (long-run rates: ~15 and ~1 per year)")


def step_volcanoes():
    print("volcanoes (NOAA NCEI)")
    rows, page = [], 1
    while True:
        j = json.loads(get(f"https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/volcanolocs?page={page}", f"ncei_volc_{page}.json"))
        for v in j["items"]:
            if v.get("latitude") is None or v.get("longitude") is None:
                continue
            rows.append([v.get("name"), round(v["longitude"], 3), round(v["latitude"], 3), v.get("elevation"),
                         v.get("morphology") or "", v.get("country") or "", v.get("timeErupt") or ""])
        if page >= j.get("totalPages", 1):
            break
        page += 1
    dump("volcanoes.json", {"source": "NOAA NCEI Global Volcano Locations Database (public domain; after the Smithsonian GVP)",
                            "columns": ["name", "lon", "lat", "elev_m", "type", "country", "last_eruption_code"], "rows": rows})
    print(f"  {len(rows)} volcanoes")


FUELS = ["Coal", "Gas", "Oil", "Nuclear", "Hydro", "Wind", "Solar", "Biomass", "Geothermal", "Waste", "Other"]


def step_power():
    print("power stations (WRI GPPD v1.3)")
    cols = {k: [] for k in ("lon", "lat", "mw", "fuel", "name", "country", "year")}
    tot = {}
    with open(os.path.join(DATA, "power", "global_power_plant_database.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            mw = float(r["capacity_mw"] or 0)
            fuel = r["primary_fuel"]
            fi = FUELS.index(fuel) if fuel in FUELS else {"Petcoke": 0, "Cogeneration": 1, "Storage": 10, "Wave and Tidal": 10}.get(fuel, 10)
            tot[FUELS[fi]] = tot.get(FUELS[fi], 0) + mw
            if mw < 20:
                continue                       # the long tail of small plants is counted in totals, not drawn
            cols["lon"].append(round(float(r["longitude"]), 3)); cols["lat"].append(round(float(r["latitude"]), 3))
            cols["mw"].append(round(mw)); cols["fuel"].append(fi); cols["name"].append(r["name"]); cols["country"].append(r["country"])
            cols["year"].append(int(float(r["commissioning_year"])) if r["commissioning_year"] else 0)
    dump("power.json", {"source": "WRI Global Power Plant Database v1.3.0 (2021), CC BY 4.0", "fuels": FUELS,
                        "note": "plants of 20 MW and above are listed; totals include all plants in the database",
                        "capacity_gw_by_fuel": {k: round(v / 1000, 1) for k, v in tot.items()}, **cols})
    print(f"  {len(cols['mw'])} plants >= 20 MW; database total {sum(tot.values()) / 1e6:.2f} TW (world installed ~8 TW in 2021; the database is known to be incomplete for wind and solar)")


def gc_km(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * F.R_EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def step_air():
    """MODELLED air traffic. Airports are real (OurAirports); the flows between them are a
    gravity model, not a schedule: flow_ij ~ m_i m_j / d_ij, where m is the economic output of
    the population the model's own GHSL field puts within ~150 km of the airport. Labelled MODELLED in the app."""
    print("airports and modelled routes")
    from scipy.spatial import cKDTree
    pop = np.load(os.path.join(CACHE, "pop_count4.npy")).astype(np.float64)
    H, W = pop.shape
    coarse = pop.reshape(H // 4, 4, W // 4, 4).sum(axis=(1, 3))      # 1024 x 512 cells of 0.35 deg
    stats = json.load(open(os.path.join(OUT, "stats.json")))["by_code"]
    iso2to3 = {}
    for f in ne("ne_50m_admin_0_countries"):                          # sovereign states win a shared ISO-2 code
        pr = f["properties"]
        if pr["ISO_A2_EH"] not in iso2to3 or pr["TYPE"] in ("Sovereign country", "Country"):
            iso2to3[pr["ISO_A2_EH"]] = pr["ADM0_A3"]
    aps, missing = [], set()
    with open(os.path.join(DATA, "air", "airports.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["type"] != "large_airport" or r["scheduled_service"] != "yes" or not r["iata_code"]:
                continue
            a3 = iso2to3.get(r["iso_country"])
            v = stats.get(F.wb_code(a3) or "", {}).get("NY.GDP.PCAP.CD") if a3 else None
            if v is None:
                missing.add(r["iso_country"])
            aps.append({"iata": r["iata_code"], "name": r["name"], "city": r["municipality"], "cc": r["iso_country"],
                        "lon": round(float(r["longitude_deg"]), 3), "lat": round(float(r["latitude_deg"]), 3),
                        "gdp_pc": v[0] if v else None})
    lon = np.array([a["lon"] for a in aps]); lat = np.array([a["lat"] for a in aps])
    gdp_pc = np.array([a.pop("gdp_pc") or np.nan for a in aps], dtype=float)
    med = float(np.nanmedian(gdp_pc))
    print(f"  no GDP figure for {int(np.isnan(gdp_pc).sum())} airports in {sorted(missing)}; they take the median (${med:,.0f}) - a declared approximation")
    gdp_pc = np.where(np.isnan(gdp_pc), med, gdp_pc)

    # Catchments: every populated cell goes to its NEAREST large airport, if one is within
    # 200 km. Each person is counted once (an earlier box catchment gave Philadelphia all of
    # New York - measured, and wrong).
    def xyz(lo, la):
        lo, la = np.radians(lo), np.radians(la)
        return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    jj, ii = np.nonzero(coarse > 0)
    cl = F.canon_lon(W // 4)[ii]; ca = F.canon_lat(H // 4)[jj]
    dist, near = cKDTree(xyz(lon, lat)).query(xyz(cl, ca))
    ok = dist < 2 * math.sin(200.0 / F.R_EARTH_KM / 2)
    people = np.bincount(near[ok], weights=coarse[jj, ii][ok], minlength=len(aps))
    print(f"  {people.sum() / 1e9:.2f} bn people live within 200 km of a large airport")
    # People fly in proportion to income, not headcount: the mass is the catchment's economic
    # output (population x national GDP per person). Population alone ranked Dhaka and
    # Faisalabad above Atlanta and Heathrow - measured, and wrong.
    m = np.maximum(people * gdp_pc, 2e9) ** 0.8                      # sub-linear: a small city's airport still flies
    D = gc_km(lon[:, None], lat[:, None], lon[None, :], lat[None, :])
    n = len(aps)
    flow = np.outer(m, m) / np.maximum(D, 300.0)
    flow[D < 250] = 0                                                # nobody flies 200 km between hubs
    flow[D > 15500] = 0                                              # beyond the longest scheduled sectors
    iu = np.triu_indices(n, 1)
    order = np.argsort(-flow[iu])[:2600]
    fmax = flow[iu][order[0]]
    routes = [[int(iu[0][k]), int(iu[1][k]), round(float(flow[iu][k] / fmax), 4), int(D[iu][k])] for k in order]
    for a, mi in zip(aps, m):
        a["m"] = round(float(mi / m.max()), 4)
    dump("air.json", {"source": "airports: OurAirports (public domain). Flows: MODELLED by a gravity model (catchment population from the GHSL field x national GDP per person, over distance) - not a schedule.",
                      "confidence": "moderate", "airports": aps, "routes_columns": ["from", "to", "relative_flow", "km"], "routes": routes})
    top = sorted(aps, key=lambda a: -a["m"])[:12]
    print(f"  {n} large airports, {len(routes)} routes; largest modelled hubs: " + " ".join(a["iata"] for a in top))


WB = {  # indicator code -> (label, unit, decimals)
    "SP.POP.TOTL": ("Population", "", 0), "NY.GDP.MKTP.CD": ("GDP", "US$", 0), "NY.GDP.PCAP.CD": ("GDP per person", "US$", 0),
    "SP.DYN.LE00.IN": ("Life expectancy", "years", 1), "SP.URB.TOTL.IN.ZS": ("Urban population", "%", 1),
    "EN.GHG.CO2.PC.CE.AR5": ("CO₂ per person", "t", 2), "EG.USE.ELEC.KH.PC": ("Electricity per person", "kWh", 0),
    "EG.ELC.ACCS.ZS": ("Access to electricity", "%", 1), "AG.LND.FRST.ZS": ("Forest area", "% of land", 1),
    "IT.NET.USER.ZS": ("Internet users", "%", 1), "SP.POP.GROW": ("Population growth", "% / yr", 2),
}


def step_stats():
    print("country statistics (World Bank)")
    out = {}
    for code, (label, unit, dec) in WB.items():
        try:
            raw = get(f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&mrnev=1&per_page=400", f"wb_{code}.json")
            j = json.loads(raw)
            rows = j[1] or []
        except (SystemExit, ValueError, IndexError, TypeError) as e:
            print(f"  indicator {code} unavailable ({e}); omitted - cards will show no value for it")
            continue
        n = 0
        for r in rows:
            if r.get("value") is None or not r.get("countryiso3code"):
                continue
            out.setdefault(r["countryiso3code"], {})[code] = [round(r["value"], dec) if dec else round(r["value"]), int(r["date"])]
            n += 1
        print(f"  {code:22s} {label:26s} {n} economies")
        time.sleep(0.5)
    dump("stats.json", {"source": "World Bank Open Data (CC BY 4.0), most recent value per economy; year given with each value",
                        "indicators": {k: {"label": v[0], "unit": v[1]} for k, v in WB.items()}, "by_code": out})


STEPS = {"political": step_political, "places": step_places, "physical": step_physical, "plates": step_plates,
         "quakes": step_quakes, "volcanoes": step_volcanoes, "power": step_power, "air": step_air, "stats": step_stats}


def main():
    for a in (sys.argv[1:] or list(STEPS)):
        STEPS[a]()
    from stamp import stamp
    stamp()
    print("vectors: done")


if __name__ == "__main__":
    main()
