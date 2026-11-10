# SCOPE — World Atlas

The contract. Produced by the scoping interview at kickoff; every later "was that in scope?" is
settled by reading this file. Amend it deliberately, with a date, rather than drifting.

*Scoped 2026-11-09. Interview answers are recorded verbatim in §12.*

---

## 1. The claim

**The Earth is one coupled machine.** Sunlight drives the air and the water; life follows the
water; people follow both. Every human system on the globe visibly rides on a planetary one:
cities sit on rivers and coasts, night lights trace rainfall and deltas, shipping threads the
chokepoints the continents leave open, air traffic rises and falls with the terminator, and the
demand for power follows the sun around the planet. A viewer should leave able to point at any
place and say what the sun, the air, the sea, the ground and the people are doing there *now*, and
why those five answers are related.

## 2. Extent

| | |
|---|---|
| time | one climatological year, cyclic, entered at the real current UTC instant |
| stored step | monthly keyframes (12, mid-month, cyclic) for every seasonal field; static fields carry a vintage year; live feeds carry their own timestamps |
| shown step | continuous. Any UTC instant: fields interpolate between the two bracketing mid-months, and everything diurnal (sun, terminator, temperature cycle, traffic, demand) is computed from the instant |
| space / extent of the thing | the whole Earth, surface to low Earth orbit |
| finest legible thing | a mountain range, a river valley, a delta, a metro area — about **2 km per pixel**. Baked fields carry 5 km (8192 × 4096); below that, elevation and imagery stream per region |
| substrate family | **terrain** — the planet's surface, with the ocean and the air rendered as real media on it |
| frame | WGS84 lon/lat on a sphere. Two cameras on the same per-pixel composition: an orthographic-perspective **globe**, and a **Winkel Tripel** sheet (the projection of the National Geographic baseline), central meridian 0° |

## 3. The substrate

**The real thing this model renders:** the Earth as it would be seen from space at a stated
instant — rock, soil, vegetation, snow, ice, liquid water, cloud and air, lit by the actual Sun
from its actual position, with the dark side lit by the electric light people make.

**Its substrate family:** terrain, because the subject *is* a planetary surface and everything in
the claim happens on it or just above it.

**Why not a map:** it is a map, and that is the honest surface here — the claim is about spatial
co-location of systems on the planet's surface, and nothing in it is hidden by plan view. The two
things a plan view *does* hide are stated as limits: the vertical structure of the atmosphere
(the jet stream is drawn as a second wind layer, never as a volume) and the depth of the ocean
(surface currents only). Neither is in the claim.

**The fields it is composed from,** per pixel at render time. All are equirectangular WGS84,
pixel-centre registered, longitude −180 at the left edge, latitude +90 at the top (§6).

| field | indexed on | resolution | encoding | source or mechanism | confidence channel? |
|---|---|---|---|---|---|
| surface reflectance ×12 months | lon/lat | 8192×4096 (+2048 preview) | RGB lossy WebP | NASA Blue Marble Next Generation 2004, base (unshaded) | no — vintage 2004 stated |
| elevation / bathymetry | lon/lat | 4096×2048 | 16-bit, R=hi G=lo, lossless | NOAA ETOPO 2022 60″ ice-surface | no |
| relief gradient (∂z/∂east, ∂z/∂north) | lon/lat | 8192×4096 | 2 × 8-bit, tanh-companded slope | derived from ETOPO 2022 at native 60″, then area-averaged | no |
| water fraction | lon/lat | 8192×4096 | 8-bit coverage | derived (BMNG water fill or Natural Earth 10m land, decided by measurement) | no |
| night lights | lon/lat | 8192×4096 | 8-bit | NASA Black Marble 2016 | no — vintage 2016 stated |
| cloud texture | lon/lat | 4096×2048 | 8-bit | NASA Blue Marble Clouds (2002 composite); *shapes* are real, *positions* are modelled | modelled badge |
| atmosphere ×12: 10 m wind u,v · 2 m temperature · sea-level pressure · cloud fraction · precipitation · 250 hPa wind u,v | lon/lat | 360×180 | 8-bit per channel, lossless | NCEP/NCAR Reanalysis 1 and GPCP v2.3, 1991–2020 monthly means | no — coarse source (2.5°) stated |
| ocean ×12: sea-surface temperature · sea-ice concentration | lon/lat | 1440×720 | 8-bit, lossless | NOAA OISST v2.1, 1991–2020 monthly means | land mask channel |
| ocean ×12: surface current u,v | lon/lat | 720×360 | 8-bit, lossless | NCEP GODAS 5 m currents, recent-years monthly mean | valid mask channel |
| population density | lon/lat | 4096×2048 | 8-bit log-companded | JRC GHSL GHS-POP R2023A, epoch 2025 | no |
| shipping density | lon/lat | 4096×2048 | 8-bit log-companded | World Bank / IMF AIS density 2015–2021 | no |
| fossil CO₂ emission flux | lon/lat | 3600×1800 | 8-bit log-companded | EDGAR v8.0, year 2022 | no |
| country identity | lon/lat | 8192×4096 | 16-bit id, lossless, nearest | rasterised Natural Earth 5.1.2 admin-0 | disputed-area flag |

Not shipped because they are closed forms of what is: sun and moon position, the terminator,
day length, local solar time, the diurnal temperature cycle, air density and haze with altitude,
snow-line and lapse-rate temperature (from elevation + the 2 m field), sun-glint geometry.

**Scale and exaggeration shown on screen:** a scale bar in km that follows zoom; relief shading
uses a stated vertical exaggeration (readout in the About panel, with separate values for land
and sea floor — TRAPS §B4). Clouds, aircraft and satellites are drawn at exaggerated height only
in the sense of parallax; the readout gives true altitude.

**The visual bar, as a testable sentence:** *at any time of any day the globe reads as a
photograph of the Earth from space — the terminator is where the Sun puts it, the lit side shows
relief shaded from the elevation field with snow, desert, forest and water distinguishable by
material, the ocean carries a sun-glint whose position follows the Sun, clouds cast onto the
ground beneath them, and the dark side shows city lights — and at 2 km per pixel a mountain
range, a delta and a metro area are each still resolved from fields rather than from a stretched
picture.*

**Three concrete facts a viewer must be able to read off a full-frame screenshot with no legend:**

1. Where it is day and where it is night right now, and which hemisphere is in summer (the tilt
   of the terminator and the extent of snow and sea ice).
2. Where people live — the lit coasts and river valleys on the dark side, against the empty
   deserts, ice and ocean.
3. Which way the air and the water are moving — the trade winds and westerlies, the storm tracks,
   and the major currents — and that ships and aircraft follow lanes.

Secondary views, reached from the real one and never the substrate: the system dashboard (global
totals and derived indicators), cards, and data-lens colour ramps laid over the lit terrain.

## 4. The layer table

Kinds: **modelled** (computed from a mechanism), **authored** (hand-entered from the record),
**interpolated** (between stored keyframes), **static** (one vintage), **live** (network feed with
its own timestamp — an addition to the house's four, needed because this model is anchored at now).

| system | layer | kind | mechanism or source | engine |
|---|---|---|---|---|
| Sun & orbit | sun position, terminator, twilight bands, seasons | modelled | solar ephemeris (Meeus low-precision), obliquity, equation of time | procedural |
| | moon position and phase, sub-lunar point | modelled | lunar ephemeris (Meeus truncated) | procedural |
| | satellites in orbit | live / modelled | SGP4 on CelesTrak GP elements; valid ± ~2 weeks of element epoch, labelled outside | feature |
| | aurora | live | NOAA SWPC OVATION nowcast; absent away from now | field |
| Solid Earth | relief, bathymetry | static | ETOPO 2022 | field |
| | plate boundaries | static | Bird 2003 PB2002 | feature |
| | earthquakes — record | static | USGS ComCat M ≥ 6, 2000–2025 | feature |
| | earthquakes — now | live | USGS real-time feed, past 30 days | feature |
| | volcanoes | static | NOAA NCEI volcano locations | feature |
| Atmosphere | surface wind (flow) | interpolated | NCEP R1 monthly means | field + particles |
| | jet stream (250 hPa flow) | interpolated | NCEP R1 monthly means | field + particles |
| | air temperature | interpolated + modelled | 2 m monthly mean, lapse-rate-downscaled on elevation, plus a diurnal cycle driven by local solar time and continentality | field |
| | pressure | interpolated | NCEP R1 sea-level pressure | field |
| | precipitation | interpolated | GPCP v2.3 | field |
| | clouds | modelled | real cloud texture, coverage set by monthly cloud-fraction climatology, advected along the wind field | field |
| | today's Earth | live | NASA GIBS VIIRS true-colour daily mosaic, any date 2012 → yesterday | field |
| Ocean | sea-surface temperature | interpolated | OISST | field |
| | sea ice | interpolated | OISST ice concentration | field |
| | surface currents (flow) | interpolated | GODAS | field + particles |
| | sun-glint, depth colour | modelled | specular geometry, roughness from wind speed; depth from bathymetry | procedural |
| Biosphere | land surface through the year (snow, green-up, senescence) | interpolated | BMNG 12 months | field |
| | greenness index | modelled | visible-band proxy from the reflectance field — *not* NDVI; labelled as a proxy | field |
| Humanity | countries, borders, disputed lines | static | Natural Earth 5.1.2, de facto worldview | feature + field |
| | cities and labels | static | Natural Earth populated places | feature |
| | population density | static | GHSL 2025 | field |
| | night lights | static | Black Marble 2016, lit by the model's own night | field |
| | people in daylight / darkness | modelled | population field × solar elevation, integrated | readout |
| | shipping lanes | static + modelled | AIS density (measured) with tracer motion along the lanes' own orientation (modelled) | field + particles |
| | air traffic | modelled | gravity model between large airports on great circles, departures gated by local time | particles |
| | power stations | static | WRI GPPD v1.3 | feature |
| | electricity demand wave | modelled | population × local-time load curve | readout + field |
| | fossil CO₂ emissions | static | EDGAR 2022 | field |
| | country statistics | static | World Bank indicators, most recent value, year shown | card |

## 5. The evidence boundary

This model has an unusual boundary: it is not an age, it is **now**.

| tier | what it means | badge |
|---|---|---|
| **LIVE** | a network feed timestamped within its own latency (earthquakes: minutes; aurora: ~30 min; satellites: element epoch) | `LIVE` + timestamp |
| **OBSERVED** | a measurement of a specific past date (GIBS daily imagery for the clock's date) | `OBSERVED` + date |
| **CLIMATOLOGY** | a 1991–2020 mean for this time of year. *It is a typical day, not this day.* | `CLIMATOLOGY` + period |
| **STATIC** | one vintage that does not change with the clock | `STATIC` + year |
| **MODELLED** | computed from a mechanism on the fields above | `MODELLED` |

Where the record stops and inference begins: **the present instant, and the edge of each feed's
latency window.** The model holds no weather history and no forecast.

What the UI does past it: every layer shows its tier badge at all times. When the clock is moved
more than an hour from the real present, LIVE layers switch themselves off (earthquakes, aurora)
or change badge (satellites → `MODELLED from elements of <date>`), a *Return to now* control
appears, and the clock readout itself says *Typical year* instead of *Now*. Dates in the future
never show OBSERVED imagery. Offline, LIVE layers report *unavailable*, never a stale value
presented as current.

Where the sources disagree, and the shape of the disagreement:

| disagreement | shape | how the model handles it |
|---|---|---|
| sovereignty over ~30 areas (Kashmir, Crimea, Taiwan, Western Sahara, Palestine, Kosovo, …) | existence / position | de facto control drawn; every disputed line dashed in a distinct style; one card per dispute naming claimants; `confidence: contested` on the data |
| gridded population (GHSL vs WorldPop vs GPW) | amount — up to a factor of 2 in rural cells, national totals agree | one source (GHSL), named on the card; totals checked against UN/World Bank national figures |
| surface vintage: BMNG is 2004, night lights 2016, population 2025, borders 2022 | existence — the Aral Sea, glaciers, new cities and reservoirs differ between vintages | each layer states its vintage; known large mismatches get a curated card |
| reanalysis cloud and precipitation vs satellite retrievals | amount — R1 cloud fraction is the weakest field shipped | cloud *shapes* are illustrative and badged MODELLED; a satellite cloud climatology is a P1 register item |
| ETOPO vs GEBCO under ice shelves and in unsurveyed deep ocean | amount | ETOPO only; stated |

## 6. The canonical frame

| dimension | canonical choice | sources that differ, and the conversion |
|---|---|---|
| coordinates | WGS84 geographic degrees. Rasters are equirectangular, **pixel-centre registered**, column 0 centred at −180 + ½Δ, row 0 centred at +90 − ½Δ. Rendering treats geodetic latitude as spherical latitude on a 6371.0088 km sphere (max 0.19° discrepancy, below a pixel at every shipped scale; stated). | NCEP R1 pressure/surface grids: 0–360° east, **node**-registered 2.5° including both poles, N→S. NCEP Gaussian T62 grids: 0–360°, irregular latitudes. OISST, GPCP, GODAS, EDGAR: 0–360° or −180–180, cell-centred, **S→N**. ETOPO: −180–180, cell-centred, S→N. BMNG / Black Marble / clouds: already canonical. GHSL and ship density: geotransform read from the file, never assumed. AWS terrain tiles: Web Mercator. All conversions go through `build/frames.py::to_canonical()`, which is tested (`build/test_frames.py`) by round-tripping known points: Greenwich, the antimeridian, both poles and a landmark per source. |
| dates / calendar | one scalar `t` = UTC milliseconds since the Unix epoch, proleptic Gregorian. Climatology is addressed by fractional month of year with keyframes at mid-month, cyclic. Local solar time = UTC + λ/15 h + equation of time. Civil time zones are a display overlay and never enter the physics. | BMNG composites are calendar months of 2004; PSL long-term means are calendar months of 1991–2020; GODAS is calendar months; feeds are UTC. |
| names | Common English name first (Natural Earth `NAME_EN` / `name`), local-language endonym second where the source carries one. | Natural Earth carries endonyms unevenly — closing that is a register item, not a silent omission. |
| administrative units | Natural Earth 5.1.2 default (de facto) worldview. Key = `ADM0_A3`. | World Bank uses ISO 3166-1 alpha-3 with its own exceptions (`XKX` Kosovo; NE codes France/Norway `ISO_A3 = -99`). `build/frames.py::wb_code()` maps them; unmapped units get *no statistics*, not a neighbour's. |

Conversions live in `build/frames.py` with tests. **Never combine two sources without checking
they are in the same frame.**

## 7. The card contract

Every card carries:

- eyebrow (what kind of thing this is), title, and the secondary name where there is one
- 2–5 fact rows
- prose **for the current time** — computed rows for the instant (local solar time, sun height,
  day length, the climatological season here) plus curated `seasons: [{from, to, text}]` month
  windows where something seasonal is worth saying (monsoon, sea-ice maximum, hurricane season)
- the vintage or period of every number shown
- citations
- `confidence: good | moderate | contested`, rendered

Fallback tiers, and the heading each is shown under:

1. curated exception → "Curated"
2. model-derived → "Computed from the fields at this place and time"
3. generic → "Generic — Natural Earth attributes only" — **the heading must say it is generic.**

**The probe is a card too:** clicking any pixel returns every field's value at that point and
instant, each with its tier badge. Where a field is silent it returns *no data*, not a neighbour.

Approximate card counts: ~240 countries and territories (generated + World Bank facts), ~1,200
cities (generated), ~250 physical and marine features (generic tier), ~30 disputes (curated),
~50 plates and ~1,500 volcanoes (generic), ~30 layer cards (curated: what it is, source, vintage,
mechanism, known limits).

## 8. The standard for done

Named reference artefacts a result is compared against, at a stated scale:

- **National Geographic, *The World — Political* (Winkel Tripel)** — the attached sheet. The
  Atlas style is compared against it for label coverage and legibility at sheet scale: every
  sovereign state labelled on the sheet is labelled here at the same framing. Measured against,
  never reproduced, never committed (© National Geographic Society; `reference/` is gitignored).
- **NASA EPIC (DSCOVR) natural-colour full-disc images** at a stated UTC instant — the space
  view: with the model's clock set to the image time and the camera at the sub-solar point, the
  continents, limb, glint position and overall colour balance are compared side by side.
- **NASA GIBS VIIRS true-colour mosaic** at 2 km/px over five named regions (Himalaya–Ganges,
  Nile delta, Alps–Po, Andes–Atacama, Great Lakes) — the regional zoom floor.

The independent witness:

- for the sun, terminator and moon: **JPL Horizons** sub-solar and sub-lunar points at 24 instants
  across a year — genuinely independent, and the instrument for every dispute about lighting;
- for sea ice: **NSIDC Sea Ice Index** monthly extent against extent integrated from the shipped
  field (partly independent — different algorithm, same satellite class);
- for population: UN/World Bank national totals against the GHSL field summed per country
  (a consistency check, not independent: gridded products are calibrated to census totals);
- for cloud, wind and temperature there is **no independent witness in the repository** — ERA5
  would be one and is a register item. A known limit from day one.

## 9. Sensitivities

- **Contested sovereignty** → carried by the border style (dashed, distinct), a dispute card per
  area naming every claimant in the same register, `confidence: contested` on the geometry, and
  the country card of each party. Not a disclaimer.
- **Whose names** → English first, endonym second; the gap in endonyms is a tracked defect.
- **"Dark means empty"** — night lights measure electricity, not people. → carried by putting the
  population field one click from the lights, and by a standing indicator on the Humanity panel:
  people living in lit versus unlit cells.
- **Responsibility for emissions** → country cards give both total and per-capita CO₂ with year.
- **Antarctica** → no territorial claims drawn (Antarctic Treaty), matching the baseline sheet.

Naming convention and why: Natural Earth's de facto worldview, because it is public domain,
documented, and is the same policy the baseline sheet states for itself — show who administers the
ground, mark what is disputed.

## 10. Non-goals

- A weather forecast, nowcast or weather history. The atmosphere is a typical year.
- Decadal change — climate trends, urban growth, 1950–2100. A different project.
- Live aircraft or ship positions (licence-blocked for a published site). Flows are modelled and say so.
- Submarine cable maps (the canonical source is CC BY-NC-SA).
- Street-level detail, routing, search for addresses.
- A volumetric atmosphere or extruded 3D terrain mesh.
- Mobile-first layout. Desktop WebGL2 is the target; mobile should not break.

## 11. Budget and delivery

| | |
|---|---|
| delivery | static site in `web/`, served locally (`python -m http.server`). `docs/` + GitHub Pages is a later decision the user makes explicitly |
| total bytes over the wire | first usable frame ≤ 6 MB; settled working set ≤ 70 MB; whole site ≤ 300 MB |
| time to first usable frame | ≤ 1.5 s on localhost (preview tier), full detail ≤ 5 s |
| offline / `file://` required? | offline yes (the baked year needs no network); `file://` no — a local server is assumed |
| pipeline? | yes — `build/` (Python): fetch → `frames.py` → fields → `web/fields/`, `web/data/` |

## 12. Interview record (2026-11-09)

| question | answer |
|---|---|
| A1 the claim | *One coupled machine* |
| A2 time axis | *A year of Earth, anchored at now* |
| A3 zoom floor | *Regional, about 2 km per pixel* (baked ~10 km → revised to 5 km baked, streamed below) |
| B2 human systems | all four: *Political and settlement · Movement · Energy and emissions · Connectivity and economy* |
| C8 borders and names | *De facto, disputes dashed and carded* |
| C4 default view | *Earth from space, labels on zoom*, with a separate Atlas style |
| D3 live data | *Baked year plus labelled live feeds* |
| D1 delivery | *~/World Atlas, static site, local first*; ask before publishing |

Answered by the session rather than asked, and open to amendment: the substrate family (terrain),
the projection pair, the tier badges, the card contract, the reference set, the non-goals and the
budget.

**What is most expected to be wrong:** the clouds. They are a real cloud photograph moved by a
coarse monthly-mean wind and thinned by a reanalysis cloud climatology; they will look right from
orbit and be wrong about any particular place on any particular day. That is at the top of the
gap register.
