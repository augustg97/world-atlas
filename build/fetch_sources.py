#!/usr/bin/env python3
"""Fetch every source dataset into ../data/ (gitignored). Idempotent: skips what exists.

    ./venv/bin/python build/fetch_sources.py            # everything
    ./venv/bin/python build/fetch_sources.py small      # only the small files (< 50 MB)
    ./venv/bin/python build/fetch_sources.py etopo ne   # by group
    ./venv/bin/python build/fetch_sources.py nsidc      # 720 monthly sea-ice grids + 24 extent tables
    ./venv/bin/python build/fetch_sources.py isccp      # 120 monthly cloud-type grids, 530 MB
    ./venv/bin/python build/fetch_sources.py hydrolakes # mean depth of 1.4 million lakes, 79 MB
    ./venv/bin/python build/fetch_sources.py lakeice    # freeze and thaw dates of 865 lakes (witness only), 3 MB
    ./venv/bin/python build/fetch_sources.py cloudtex   # three VIIRS cloud scenes for the cloud grain, 8 MB

This table IS the project's source record: name, URL, licence. Research/SOURCE-SURVEY.md
is written from it. Every source here is public domain or plain CC-BY, except NSIDC's Sea Ice
Index, which names no licence and asks for citation as its condition of use; see the survey for
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
# OISST's own ice field: no longer built from (it ran 11-94% over NSIDC's extent; fields_climate.py
# takes sea ice from the NSIDC group below). Kept so that comparison can be repeated.
add("psl", "psl/icec.mon.ltm.nc", f"{PSL}/noaa.oisst.v2.highres/icec.mon.ltm.1991-2020.nc",
    "public domain (NOAA OISST v2.1, Huang et al. 2021)")

# --- sea ice, year by year (NSIDC Sea Ice Index, G02135 Version 4) ----------------------
# Monthly mean concentration on NSIDC's 25 km polar stereographic grids (frames.NSIDC_NORTH /
# NSIDC_SOUTH), one GeoTIFF per month and hemisphere for 1991-2020: 720 files, 457 MB. The
# per-year extent tables (one CSV per calendar month, all years) are the witness the build
# and Research/modeling/audit_ice.py check against.
# --- cloud amount by type: ISCCP H-series monthly means, ten years ---------------------------
# 1 degree, 4.4 MB a month. The files state: "No constraints on data access or use", and ask for a
# citation of Rossow & Schiffer (1999) with the dataset (Young et al. 2018, doi:10.7289/V5QZ281S).
ISCCP = "https://www.ncei.noaa.gov/data/international-satellite-cloud-climate-project-isccp-h-series-data/access/isccp-basic/hgm"
ISCCP_YEARS = range(2007, 2017)
for yr in ISCCP_YEARS:
    for i in range(1, 13):
        f = f"ISCCP-Basic.HGM.v01r00.GLOBAL.{yr}.{i:02d}.99.9999.GPC.10KM.CS00.EA1.00.nc"
        add("isccp", f"isccp/{f}", f"{ISCCP}/{f}", "no constraints on access or use (ISCCP H-series HGM, NOAA NCEI CDR)")

# --- cloud grain: four VIIRS true-colour scenes at 2 km a pixel (build/cloud_grain.py) ----------
# NASA GIBS, the same service the page streams from. 1248 px: a 1024 px tile plus the 224 px its edges are
# cross-faded over. PNG: the JPEG's 8 x 8 coding blocks showed in the atlas's cloud. One per kind of cloud, and none of them a scene the texture audit scores against
# (Research/modeling/cloud_texture.py uses other oceans in 2024).
import math
GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
CLOUDTEX = {"sheet": (4.0, -17.0, "2023-09-05"), "cumulus": (75.0, -17.0, "2023-08-03"), "frontal": (80.0, -46.0, "2023-01-22"),
            "landcu": (-62.5, -1.0, "2023-08-27")}
for name, (lon, lat, day) in CLOUDTEX.items():
    half = 1248 * 2.0 / 2 / 111.195
    hx = half / math.cos(math.radians(lat))
    add("cloudtex", f"cloudtex/{name}_{day}.png",
        f"{GIBS_WMS}?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=VIIRS_NOAA20_CorrectedReflectance_TrueColor&CRS=EPSG:4326"
        f"&BBOX={lat - half:.4f},{lon - hx:.4f},{lat + half:.4f},{lon + hx:.4f}&WIDTH=1248&HEIGHT=1248&FORMAT=image/png&TIME={day}",
        "public domain (NASA EOSDIS GIBS, VIIRS NOAA-20 corrected reflectance; NASA asks for acknowledgement)")

# --- lake ice, the witness: freeze and thaw dates for 865 lakes and rivers -------------------
# Measured against only (Research/modeling/audit_lakeice.py); nothing from it is shipped. NSIDC asks for citation:
# Benson, B., Magnuson, J. and Sharma, S. (2000, updated 2020), Global Lake and River Ice Phenology Database,
# Version 1, NSIDC G01377, doi:10.7265/N5W66HP8.
for f in ("liag_freeze_thaw_table.csv", "liag_physical_character_table.csv"):
    add("lakeice", f"lakeice/{f}", f"https://noaadata.apps.nsidc.org/NOAA/G01377/{f}",
        "no licence named; citation required (Benson, Magnuson & Sharma 2000, NSIDC G01377)")

# --- lake depth: HydroLAKES v1.0, the pour-point table (mean depth, area, name for 1.4 million lakes) ----
# Used at build time only, by build/lakeice.py through fields_climate.step_ocean: a lake's mean depth sets how
# long it takes to freeze. CC BY 4.0: Messager, M. L., Lehner, B., Grill, G., Nedeva, I. and Schmitt, O. (2016),
# Estimating the volume and age of water stored in global lakes using a geo-statistical approach,
# Nature Communications 7, 13603, doi:10.1038/ncomms13603. Credited in the app's About panel.
add("hydrolakes", "hydrolakes/HydroLAKES_points_v10_shp.zip",
    "https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_points_v10_shp.zip", "CC BY 4.0 (HydroLAKES v1.0, Messager et al. 2016)")

NSIDC = "https://noaadata.apps.nsidc.org/NOAA/G02135"
# NSIDC names no licence for this product. Its landing page states one condition: "As a condition of
# using these data, you must cite the use of this data set"; its data policy says most of its
# holdings are government-funded and in the public domain. Both read on 2026-11-10.
NSIDC_LIC = ("no licence named; citation required as the condition of use (Fetterer, F., Knowles, K., Meier, W. N., Savoie, M., "
             "Windnagel, A. K. & Stafford, T. 2025: Sea Ice Index, G02135, Version 4, Boulder, Colorado USA, "
             "National Snow and Ice Data Center, doi:10.7265/a98x-0f50)")
NSIDC_YEARS = range(1991, 2021)
NSIDC_WORKERS = 3
_MON3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
for hemi, H in (("north", "N"), ("south", "S")):
    for i, m3 in enumerate(_MON3, 1):
        add("nsidc", f"nsidc/extent/{H}_{i:02d}_extent_v4.0.csv",
            f"{NSIDC}/{hemi}/monthly/data/{H}_{i:02d}_extent_v4.0.csv", NSIDC_LIC)
        for yr in NSIDC_YEARS:
            add("nsidc", f"nsidc/{hemi}/{H}_{yr}{i:02d}_concentration_v4.0.tif",
                f"{NSIDC}/{hemi}/monthly/geotiff/{i:02d}_{m3}/{H}_{yr}{i:02d}_concentration_v4.0.tif", NSIDC_LIC)

# --- vectors (Natural Earth 5.1.2, public domain) -------------------------------------
for f in ["ne_50m_admin_0_countries", "ne_50m_admin_0_boundary_lines_land",
          "ne_50m_admin_0_boundary_lines_disputed_areas", "ne_50m_admin_0_breakaway_disputed_areas",
          "ne_10m_populated_places_simple", "ne_50m_rivers_lake_centerlines", "ne_50m_lakes",
          "ne_50m_geography_regions_polys", "ne_50m_geography_marine_polys",
          "ne_50m_geography_regions_points", "ne_50m_geography_regions_elevation_points",
          "ne_50m_coastline", "ne_10m_time_zones",
          # the water mask (fields_surface.step_water): land, small islands, lakes and the ice shelves at 1:10m
          "ne_10m_land", "ne_10m_minor_islands", "ne_10m_lakes", "ne_10m_antarctic_ice_shelves_polys"]:
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
    big = {"etopo", "bmng", "pop", "ships", "nsidc", "isccp"}
    failed = []
    many = []            # groups of many small files: fetched a few at a time, after the rest
    for group, rel, url, _lic in SOURCES:
        if want and "small" in want and group in big:
            continue
        if want and "small" not in want and group not in want:
            continue
        if group in ("nsidc", "isccp"):
            many.append((rel, url))
            continue
        if not fetch(rel, url):
            failed.append(rel)
        if group == "psl":
            time.sleep(4)  # PSL THREDDS answers 429 to bursts
    todo = [(rel, url) for rel, url in many
            if not (os.path.exists(os.path.join(DATA, rel)) and os.path.getsize(os.path.join(DATA, rel)) > 0)]
    if many:
        print(f"  many-file groups: {len(many) - len(todo)} of {len(many)} already here", flush=True)
    if todo:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=NSIDC_WORKERS) as pool:   # polite: three connections, backoff in fetch()
            for (rel, _url), ok in zip(todo, pool.map(lambda t: fetch(*t), todo)):
                if not ok:
                    failed.append(rel)
    print("\nFAILED:" if failed else "\nall fetched", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
