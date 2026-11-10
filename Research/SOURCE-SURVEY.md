# Source survey — World Atlas

*Surveyed 2026-11-09, at kickoff. Every source below was fetched and read on that date; sizes,
frames and licences are as found, not as assumed. `build/fetch_sources.py` is the executable
form of §1.*

## 1. What data exists, per layer

### Shipped (public domain or plain CC BY)

| layer | source | format | resolution | licence | access |
|---|---|---|---|---|---|
| land surface ×12 months | NASA Blue Marble Next Generation, base (unshaded), 2004 — Stöckli et al. 2005 | JPEG | 21600×10800 (500 m) | public domain | `assets.science.nasa.gov/.../bmng/bmng-base/<month>/` |
| elevation, bathymetry | NOAA NCEI ETOPO 2022 v1, 60″ ice surface, doi:10.25921/fd45-gt74 | NetCDF | 21600×10800 | public domain | NCEI THREDDS |
| night lights | NASA Black Marble 2016 — Román et al. 2018 | JPEG (lights on a tinted base) | 13500×6750 | public domain | `assets.science.nasa.gov` |
| cloud texture | NASA Blue Marble: Clouds — Stöckli, 2002 | JPEG | 4096×2048 (from 8192) | public domain | copied from `~/Tectonic Plate Model/web/imagery/` with its provenance record |
| wind (surface, 250 hPa), 2 m temperature, pressure, cloud fraction | NCEP/NCAR Reanalysis 1 — Kalnay et al. 1996; 1991–2020 monthly means | NetCDF | 2.5° / T62 Gaussian | public domain | NOAA PSL THREDDS |
| precipitation | GPCP v2.3 — Adler et al. 2018; 1991–2020 monthly means | NetCDF | 2.5° | public domain | NOAA PSL THREDDS |
| sea-surface temperature, sea ice | NOAA OISST v2.1 — Huang et al. 2021; 1991–2020 monthly means | NetCDF / OPeNDAP | 0.25° | public domain | NOAA PSL OPeNDAP |
| surface currents | NCEP GODAS, 5 m u/v, 2019–2023 | OPeNDAP | 1° × ⅓° | public domain | NOAA PSL OPeNDAP |
| countries, borders, disputes, places, rivers, physical names | Natural Earth 5.1.2 | GeoJSON | 1:50m (places 1:10m) | public domain | GitHub `nvkelso/natural-earth-vector` tag v5.1.2 |
| plate boundaries | Bird 2003, PB2002, G³ 4(3) 1027; GeoJSON by H. Ahlenius | GeoJSON | — | ODC PDDL | GitHub `fraxen/tectonicplates` |
| earthquakes (record) | USGS ANSS ComCat, M ≥ 6, 2000–2025 (3,875 events) | CSV | — | public domain | USGS FDSN event service |
| volcanoes | NOAA NCEI Global Volcano Locations (1,609) | JSON | — | public domain | NCEI HazEL API |
| population | JRC GHSL GHS-POP R2023A, epoch 2025 — Schiavina et al. 2023 | GeoTIFF | 30″ | CC BY 4.0 | JRC open data FTP |
| shipping density | World Bank / IMF Global Shipping Traffic Density, AIS 2015–2021 | GeoTIFF + overviews | 0.005° (0.01° overview used) | CC BY 4.0 | World Bank Data Catalog 0037580 |
| fossil CO₂ | EDGAR v8.0 GHG, CO₂ totals 2022 — Crippa et al. 2023 | NetCDF | 0.1° | CC BY 4.0 | JRC open data FTP |
| power stations | WRI Global Power Plant Database v1.3.0 (2021) | CSV | 34,936 plants | CC BY 4.0 | WRI data portal |
| airports | OurAirports (1,151 large airports with scheduled service) | CSV | — | public domain | ourairports-data |
| country statistics | World Bank Open Data, 11 indicators, most recent value | JSON | per economy | CC BY 4.0 | World Bank API v2 |

### Live at runtime (fetched by the browser; nothing redistributed)

| layer | source | CORS | notes |
|---|---|---|---|
| earthquakes, past 30 days | USGS real-time GeoJSON feed | `*` | public domain |
| today's Earth | NASA GIBS WMS, VIIRS NOAA-20 corrected reflectance | `*` | public domain; any date 2018 → yesterday |
| aurora | NOAA SWPC OVATION nowcast | `*` | public domain; 1° node grid, 0–359°E |
| satellites | CelesTrak GP element sets (stations, GPS, visual) | `*` | propagated with satellite.js 5.0.0 (MIT, vendored) |

### Refused or unavailable — recorded so nobody retries without a reason

| wanted | source | why not |
|---|---|---|
| temperature and rainfall at 10′ | WorldClim 2.1 (already on this machine, in the Tectonic project) | licence forbids redistribution. Replaced by reanalysis means with a lapse-rate correction on our own elevation |
| submarine cables | TeleGeography | CC BY-NC-SA: both clauses refused by house policy. Layer omitted |
| air routes | OpenFlights | ODbL (share-alike). Replaced by a labelled gravity model |
| live aircraft / ships | OpenSky, commercial AIS | non-commercial or proprietary terms. Flows are modelled and say so |
| volcano catalogue | Smithsonian GVP direct | terms unclear for redistribution; NOAA NCEI's public-domain derivative used |
| vegetation index, fires, chlorophyll, cloud fraction (satellite) | NASA NEO monthly archives | **the NEO archive now redirects to a landing page; four listing attempts returned nothing.** A negative result, not a blank: the same products exist at LAADS/GES DISC behind Earthdata login |
| population (GPW v4) | SEDAC | Earthdata login; GHSL is open and newer |
| ocean currents (OSCAR) | PO.DAAC | Earthdata login; GODAS used instead |
| Black Marble greyscale (lights only) | NASA | 404 at the mirror; lights extracted from the colour composite by their warm excess over the blue base (measured: Sahara 37,34,62 · ocean 5,5,15 · Paris 255,248,231) |

Two hosts were unreachable from this machine and have working mirrors: `eoimages.gsfc.nasa.gov`
→ `assets.science.nasa.gov/content/dam/science/esd/eo/images/`; `downloads.psl.noaa.gov` →
`psl.noaa.gov/thredds/` (rate-limited; its file server **truncates large files and still answers
200**, so the fetcher checks Content-Length and the two ocean fields are read over OPeNDAP).

## 2. Frames

| source | coordinates | time | naming / units | vintage |
|---|---|---|---|---|
| BMNG, Black Marble, clouds | −180…180, 90…−90, cell-registered, **north first** — canonical | calendar months of 2004 / 2016 composite / 2002 composite | sRGB display values | 2004 / 2016 / 2002 |
| ETOPO 2022 | −180…180 cell-centred, **south first** | — | metres, ice surface | 2022 |
| NCEP R1 surface & pressure | **0…357.5°E, node-registered**, 90…−90 incl. both poles | calendar-month means 1991–2020 | m/s, hPa | 1991–2020 |
| NCEP R1 Gaussian (2 m temp, cloud) | 0…358.125°E, **94 irregular latitudes** ±88.542 | same | K, % | 1991–2020 |
| GPCP | 1.25…358.75°E cell-centred, **south first** | same | mm/day | 1991–2020 |
| OISST | 0.125…359.875°E cell-centred, **south first** | same; **ice mean is conditional on ice being present** (§4) | °C, fraction | 1991–2020 |
| GODAS | **velocity points at 1…360°E**, −74…+65 only | calendar months, 2019–2023 | m/s | 2019–2023 |
| GHSL | corner at **−180.0079, 89.0996**; 43202×21384 | — | people per cell (float64) | 2025 epoch |
| ship density | world file gives the **centre** of the top-left pixel: −180.0128, 85.0001; spans 85°N…85°S | 2015–2021 total | AIS positions per cell (p50 1.8×10⁴, max 4.8×10⁷) | 2015–2021 |
| EDGAR | −179.95…179.95 cell-centred, **south first** | year 2022 | tonnes per cell per year | 2022 |
| Natural Earth | WGS84 degrees | — | English `NAME_EN`; key `ADM0_A3`; `ISO_A3` is `-99` for France, Norway, Kosovo | 2022 |
| World Bank | — | most recent value, year varies | ISO 3166-1 alpha-3, `XKX` for Kosovo | 2020–2024 |
| OVATION | 0…359°E, −90…90, **node-registered**, lon-major order | forecast time in the file | probability 0–100 | now |

**Canonical frame chosen:** equirectangular WGS84, pixel-centre registered, column 0 centred at
−180 + ½Δ, row 0 centred at +90 − ½Δ; one clock, UTC milliseconds; climatology addressed by
fractional month with keyframes at mid-month; `ADM0_A3` as the administrative key.

**Conversions:** `build/frames.py` (`resample_grid`, `reduce_aligned`, `bin_sum`, `wb_code`),
tested by `build/test_frames.py` against an analytic field pushed through each source layout —
node and cell grids, 0–360 and ±180, both row orders, Gaussian latitudes, the two offset rasters.
Every build step additionally asserts real landmarks (Everest high, Mariana deep, the Himalayan
front sloping up to the north, trades easterly, Bengal wet in July and dry in January, Dhaka
dense, the Dover Strait busy) so a flipped or shifted product fails the build, not the eye.

## 3. Where the record stops

At **now**. The model holds a typical year, not a history and not a forecast. Live feeds exist
only within their own latency of the present (earthquakes 30 days; aurora ~30 min; orbital
elements ± ~2 weeks; daily imagery from 2018 to yesterday). Past that, the UI switches the layer
off or changes its badge, and the clock reads *Typical year*. Offline, live layers say
*unavailable*.

## 4. Where the sources disagree

| disagreement | shape | handling |
|---|---|---|
| **OISST long-term-mean ice vs the NSIDC Sea Ice Index** | amount. PSL's mean averages only years with ice: extent came out 12.3 M km² for the Antarctic February minimum against NSIDC's ~3.0. Corrected with `valid_yr_count / 30` → 5.6. Residual against NSIDC's twelve 1991–2020 monthly means (measured in the verify round; the kickoff figures were approximate): Arctic 16.75 vs 15.03 (Mar), 7.20 vs 5.58 (Sep); Antarctic 21.54 vs 18.61 (Sep), 5.61 vs 3.09 (Feb) | corrected; residual stated on the layer card and the dashboard; register C1 |
| de facto vs claimed borders | existence / position | de facto drawn, disputes dashed, 27 dispute cards, hatched in the Atlas style |
| gridded population products | amount (rural cells) | GHSL only, named; totals conserved exactly through the pipeline (8.192 bn) |
| vintages: surface 2004, lights 2016, borders 2022, population 2025 | existence | every layer states its vintage |
| reanalysis cloud vs satellite cloud | amount | clouds badged MODELLED; register B1 |
| EDGAR total vs its published figure | none: 38.52 Gt reproduced exactly | a check that the frame and units are right |

## 5. The independent witness

| what | witness | status |
|---|---|---|
| Sun and Moon | published almanac values: 2026 equinox and solstice instants, equation of time, the 3 March and 12 August 2026 eclipses | **built**: `build/test_app_math.mjs`, all pass (declination within 0.004°; Sun–Moon separation at the solar eclipse 0.84°) |
| sea ice | NSIDC Sea Ice Index v4, monthly extent, mean of 1991–2020 from the yearly files (`Research/modeling/witness/`) | **built**: `audit_ice.py`. Arctic +11 to +31%, Antarctic +16 to +94% by month. The four figures quoted at kickoff were rounder and kinder than the record — register C1 |
| global mean temperature | observed ~12.5 °C January, ~16 °C July | reproduced: 12.48 / 15.95 |
| population | World Bank national totals vs the field summed per country | **built**: `audit_population.py`. Total −0.4%; 26 of 192 units differ by more than 10% — register F2 |
| wind, cloud, precipitation, currents | ERA5 / satellite retrievals | **none in the repository.** A known limit |
| the lit globe as a picture | NASA EPIC natural colour, eight frames (public domain; `epic.gsfc.nasa.gov`), camera and clock matched | **built**: `epic_compare.py`; table in MODEL-GAPS. Clear ocean within 5 display levels, ground within 16, cloud and vegetated land short — registers A7, B1 |
| the Sun over the turning Earth | EPIC's J2000 Sun and spacecraft vectors with the sub-spacecraft longitude | **built** into `build/test_app_math.mjs`: eight instants, within 0.22° of longitude and 0.005° of latitude |

## 6. Layers with no usable source

- **Air traffic** — modelled (gravity on catchment population × national income); airports are real.
- **Ship motion** — modelled along measured lanes.
- **The daily temperature cycle** — modelled from local solar time, aridity and cloud.
- **Greenness** — a visible-band proxy from the reflectance field, labelled as a proxy.
- **Submarine cables, fires, ocean colour, electricity demand** — not present. Not invented.
