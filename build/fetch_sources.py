#!/usr/bin/env python3
"""Fetch every source dataset into ../data/ (gitignored). Idempotent: skips what exists.

    ./venv/bin/python build/fetch_sources.py            # everything
    ./venv/bin/python build/fetch_sources.py small      # only the small files (< 50 MB)
    ./venv/bin/python build/fetch_sources.py etopo ne   # by group

This table IS the project's source record: name, URL, licence. Research/SOURCE-SURVEY.md
is written from it. Every source here is public domain or plain CC-BY; see the survey for
the ones that were refused and why.

Two hosts are unreachable from this machine as of 2026-11-09 and have working mirrors:
  eoimages.gsfc.nasa.gov      -> assets.science.nasa.gov/content/dam/science/esd/eo/images/
  downloads.psl.noaa.gov      -> psl.noaa.gov/thredds/fileServer/   (rate-limited: 429)
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

NASA = "https://assets.science.nasa.gov/content/dam/science/esd/eo/images"
PSL = "https://psl.noaa.gov/thredds/fileServer/Datasets"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]

# (group, relative path under data/, url, licence)
SOURCES: list[tuple[str, str, str, str]] = []


def add(group, rel, url, lic):
    SOURCES.append((group, rel, url, lic))


# --- solid surface -------------------------------------------------------------------
add("etopo", "etopo/ETOPO_2022_v1_60s_surface.nc",
    "https://www.ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/60s/60s_surface_elev_netcdf/"
    "ETOPO_2022_v1_60s_N90W180_surface.nc",
    "public domain (NOAA NCEI ETOPO 2022, doi:10.25921/fd45-gt74)")

# --- surface reflectance, twelve months ----------------------------------------------
for i, m in enumerate(MONTHS, 1):
    add("bmng", f"bmng/world.2004{i:02d}.3x21600x10800.jpg",
        f"{NASA}/bmng/bmng-base/{m}/world.2004{i:02d}.3x21600x10800.jpg",
        "public domain (NASA Blue Marble Next Generation, Stockli et al. 2005)")

add("night", "night/BlackMarble_2016_3km.jpg",
    f"{NASA}/imagerecords/144000/144898/BlackMarble_2016_3km.jpg",
    "public domain (NASA Black Marble 2016, Roman et al. 2018)")

# --- atmosphere and ocean climatology (NOAA PSL) -------------------------------------
R1 = f"{PSL}/ncep.reanalysis/Monthlies"
for rel, url in [
    ("uwnd.sig995.mon.ltm.nc", f"{R1}/surface/uwnd.sig995.mon.ltm.1991-2020.nc"),
    ("vwnd.sig995.mon.ltm.nc", f"{R1}/surface/vwnd.sig995.mon.ltm.1991-2020.nc"),
    ("slp.mon.ltm.nc", f"{R1}/surface/slp.mon.ltm.1991-2020.nc"),
    ("air.2m.mon.ltm.nc", f"{R1}/surface_gauss/air.2m.mon.ltm.1991-2020.nc"),
    ("tcdc.eatm.mon.ltm.nc", f"{R1}/other_gauss/tcdc.eatm.mon.ltm.1991-2020.nc"),
    ("uwnd.mon.ltm.nc", f"{R1}/pressure/uwnd.mon.ltm.1991-2020.nc"),
    ("vwnd.mon.ltm.nc", f"{R1}/pressure/vwnd.mon.ltm.1991-2020.nc"),
]:
    add("psl", f"psl/{rel}", url,
        "public domain (NCEP/NCAR Reanalysis 1, Kalnay et al. 1996; NOAA PSL)")
add("psl", "psl/precip.mon.ltm.nc", f"{PSL}/gpcp/precip.mon.ltm.1991-2020.nc",
    "public domain (GPCP v2.3, Adler et al. 2018; NOAA PSL)")
add("psl", "psl/sst.mon.ltm.nc", f"{PSL}/noaa.oisst.v2.highres/sst.mon.ltm.1991-2020.nc",
    "public domain (NOAA OISST v2.1, Huang et al. 2021)")
add("psl", "psl/icec.mon.ltm.nc", f"{PSL}/noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc",
    "public domain (NOAA OISST v2.1, Huang et al. 2021)")

# --- vectors (Natural Earth 5.1.2, public domain) -------------------------------------
for f in ["ne_50m_admin_0_countries", "ne_50m_admin_0_boundary_lines_land",
          "ne_50m_admin_0_boundary_lines_disputed_areas", "ne_50m_admin_0_breakaway_disputed_areas",
          "ne_10m_populated_places_simple", "ne_50m_rivers_lake_centerlines", "ne_50m_lakes",
          "ne_50m_geography_regions_polys", "ne_50m_geography_marine_polys",
          "ne_50m_geography_regions_points", "ne_50m_geography_regions_elevation_points",
          "ne_50m_coastline", "ne_10m_time_zones"]:
    add("ne", f"ne/{f}.geojson", f"{NE}/{f}.geojson", "public domain (Natural Earth 5.1.2)")

add("plates", "plates/PB2002_boundaries.json",
    "https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_boundaries.json",
    "ODC PDDL (Bird 2003, G-cubed 4(3) 1027; GeoJSON conversion H. Ahlenius)")
add("plates", "plates/PB2002_plates.json",
    "https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_plates.json",
    "ODC PDDL (Bird 2003; conversion H. Ahlenius)")

# --- human systems ---------------------------------------------------------------------
add("pop", "pop/GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.zip",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
    "GHS_POP_E2025_GLOBE_R2023A_4326_30ss/V1-0/GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.zip",
    "CC BY 4.0 (JRC GHSL GHS-POP R2023A, Schiavina et al. 2023, doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE)")
add("ships", "ships/shipdensity_global.zip",
    "https://datacatalogfiles.worldbank.org/ddh-published/0037580/DR0045406/shipdensity_global.zip",
    "CC BY 4.0 (World Bank / IMF Global Shipping Traffic Density, AIS 2015-2021)")
add("power", "power/global_power_plant_database_v_1_3.zip",
    "https://wri-dataportal-prod.s3.amazonaws.com/manual/global_power_plant_database_v_1_3.zip",
    "CC BY 4.0 (WRI Global Power Plant Database v1.3.0, 2021)")
add("air", "air/airports.csv", "https://davidmegginson.github.io/ourairports-data/airports.csv",
    "public domain (OurAirports)")
add("co2", "co2/EDGAR_2022_CO2_TOTALS_emi_nc.zip",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v80_FT2022_GHG/CO2/TOTALS/"
    "emi_nc/v8.0_FT2022_GHG_CO2_2022_TOTALS_emi_nc.zip",
    "CC BY 4.0 (EDGAR v8.0 GHG, Crippa et al. 2023, JRC)")


def fetch(rel: str, url: str, tries: int = 6) -> bool:
    dst = os.path.join(DATA, rel)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "world-atlas-build/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                want = int(r.headers.get("Content-Length") or 0)
                n = 0
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    n += len(b)
            if want and n != want:  # PSL truncates under load and still answers 200
                raise IOError(f"truncated: {n} of {want} bytes")
            os.replace(tmp, dst)
            print(f"  ok   {rel}  {n / 1e6:.1f} MB", flush=True)
            return True
        except Exception as e:  # noqa: BLE001 - report and retry; a failed fetch is reported, never swallowed
            wait = 20 * (k + 1)
            print(f"  retry {rel}: {e} (waiting {wait}s)", flush=True)
            time.sleep(wait)
    print(f"  FAILED {rel}", flush=True)
    return False


def main() -> int:
    want = set(sys.argv[1:])
    big = {"etopo", "bmng", "pop", "ships"}
    failed = []
    for group, rel, url, _lic in SOURCES:
        if want and "small" in want and group in big:
            continue
        if want and "small" not in want and group not in want:
            continue
        if not fetch(rel, url):
            failed.append(rel)
        if group == "psl":
            time.sleep(4)  # PSL THREDDS answers 429 to bursts
    print("\nFAILED:" if failed else "\nall fetched", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
