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


def step_political():
    print("political")
    fc = ne("ne_50m_admin_0_countries")
    fc.sort(key=lambda f: f["properties"]["ADM0_A3"])
    countries = []
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
            "bbox": [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)], "polys": rings})
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
                            "countries": countries, "borders": borders, "disputes": disputes})
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
