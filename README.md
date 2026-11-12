# World Atlas

**Live: https://augustg97.github.io/world-atlas/**

A living atlas of the present-day Earth: one year of the planet and its people, composed per pixel and anchored at now.

**Live:** not published. Local only: `python3 build/serve.py` then http://localhost:8150 (publishing is the owner's explicit decision - SCOPE section 11)
**Contact:** the repository owner

---

## 1. What this is trying to be

A **model**, not a slideshow. It ships **fields** - twelve months of land reflectance, elevation, a water mask, night lights, monthly climatologies of the air and the sea, population, shipping and emissions - and **rules**: a solar and lunar ephemeris, a lighting model, a temperature model, transport along the wind — the app ships state and rules and assembles
the world at render time. Nothing is a pre-rendered picture of a moment.

That choice is the whole architecture, and everything below follows from it:

- the terminator, the seasons, the snow line and the sea ice **move** because the clock moves, not because one picture fades into another;
- the globe, the flat sheet, the probe, the cards and the dashboard all read the **same fields**, so "people in daylight" cannot disagree with the terminator you are looking at.
- Every layer is derived from the same underlying data, so the layers cannot disagree with each
  other.

### Goals

1. **Veracity first.** Where the record says something, follow it. Where it does not, model the
   mechanism and say plainly that it is modelled.
2. **Coherence.** One world, internally consistent.
3. **Detail that survives inspection.** Baked fields carry 5 km. At 2 km per pixel a range, a delta and a metro area still resolve - today by magnification of real fields, and by streamed fields once register item A2 lands.
4. **Honesty about uncertainty.** Every layer and every number on a card carries its evidence tier (LIVE, OBSERVED, CLIMATOLOGY, STATIC, MODELLED) and its vintage; contested borders are dashed and carded; where a field has no data the probe says so. The UI says so, and the model degrades
   gracefully rather than inventing confident detail.

---

## 2. Working rules

Standing constraints on how work is done here, not suggestions. Each came from a specific
failure. *(Copied from `Modeling Studio/references/WORKING-RULES.md` — keep in sync; add rules
as new failures produce them.)*

**2.1 Always visually verify.** An update is not done when the data contains the value. It is
done when it has been rendered and looked at.

**2.2 Fix the system, not the instance.** Make the change at the level that fixes the whole class
across the whole timeline.

**2.3 Prefer structural, model-based changes over cosmetic ones.** Model the object or process;
let the appearance fall out of it.

**2.4 Measure before tuning.** If you cannot say what the number is now, you cannot say your
change improved it.

**2.5 Track every request; never silently drop one.** If something cannot be done, say so and say
why.

**2.6 Always deploy, and verify the live artefact.** Local-only changes read as "not done".

**2.7 Never ship on an average.** Score every item individually and classify every regression.

**2.8 When an audit disagrees with the app, check the audit first.**

**2.9 Say what is contested.** Confidence is a field on the data, not a footnote.

**2.10 "Unknown" is a legitimate return** — and where a fallback is unavoidable, the UI labels it.

11. **Every number on screen carries its tier and its vintage.** A climatological mean shown as "the temperature" is the
    failure this atlas exists to avoid. Tiers are a field in `web/js/catalog.js`, never prose.
12. **Away from now, live layers go dark - they do not go stale.** A feed that cannot be fetched reports *unavailable*.
13. **Modelled motion is labelled as modelled.** Aircraft and ship tracers are not vehicles; the cards say so.
14. **Borders follow who administers the ground; every dispute is dashed, hatched and carded.** No disputed line is
    ever drawn solid.
15. **A source goes through `build/frames.py` or it does not go in.** Each build step asserts real-world landmarks.

---

## 3. Repository layout

```
```
build/        the offline pipeline (Python) and the tests
  fetch_sources.py   every source, with URL and licence - the executable source table
  frames.py          THE canonical frame and every conversion into it     test_frames.py
  fields_surface.py  water, 12 months of reflectance, elevation, relief gradient, night lights, clouds
  cloud_grain.py     cloud's fine structure: three VIIRS scenes reduced to tileable rank fields
  lakeice.py         lake ice from air temperature (used by fields_climate.py ocean)
  fields_climate.py  atmosphere and ocean climatologies -> month-stacked atlases + climate.json
  fields_human.py    population, shipping density and lane ridges, CO2, country raster
  vectors.py         political geometry, places, names, plates, quakes, volcanoes, power, air model, statistics
  units.py           the list of political units: Natural Earth's countries, France's overseas departments apart
  check_shaders.py   test_app_math.mjs   closewater_flags.mjs (the app's water rule, for the audit)   stamp.py   serve.py
web/          the app: no build step, ES modules
  shaders/    common.glsl (the two cameras)  earth.frag.glsl (the substrate)  lines.*  points.*
  js/         main (loop, state)  fields (the field store)  earth  camera  astro  overlays  particles
              catalog (every layer, tier, source, limit)  cards  data  dash  live  ui
              detail (the focus window)  water + water.worker (land or water in it)  insets
  fields/     69 MB of rasters      data/  4 MB of features      version.json
data/         about 3.6 GB of sources and caches - gitignored
Research/     SOURCE-SURVEY.md  MODEL-GAPS.md  modeling/ (audits, the EPIC harness)  baselines/ (six frozen frames)  figures/epic/ - never imported by build/
docs/         empty until the owner decides to publish
```
```

---

## 4. The layers

| layer | kind | source or mechanism |
|---|---|---|
| see SCOPE.md section 4 for the full table (35 layers across six systems) | modelled / authored / interpolated / static | `web/js/catalog.js` is the same table as code, with each layer's tier, source and known limits |

---

## 5. Subsystems

- **The substrate** (`shaders/earth.frag.glsl`) - one full-screen triangle. Each pixel finds its lon/lat (ray-cast globe
  or Newton-inverted Winkel Tripel), reads the fields and composes land, water, ice, cloud, air and electric light
  under the Sun's actual position. A second register, *Atlas*, renders the same fields as political tints with oblique
  relief. It is drawn into a cache and re-run only when the camera, clock or toggles change.
- **The field store** (`js/fields.js`) - loads every raster, owns its texture and its CPU copy, tolerates absence,
  caps full-resolution months on the GPU at three, and is the single reader for the shader, the probe, the tracers
  and the dashboard.
- **The clock** - one scalar, `state.t` (UTC ms). LIVE follows the wall clock; scrubbing or playing makes it a typical year.
- **Things that move** (`js/particles.js`) - tracers advected through the wind, jet and current fields; tracers along
  measured shipping-lane ridges; aircraft as a pure function of the clock on a gravity model, drawn as fine fading
  threads. Tracers are spread evenly over the screen, so each remembers the scale it was spawned at and is recast
  when the camera moves.
- **The focus window** (`js/detail.js`) - closer than 5 km a pixel, finer ground, relief and, on the night side, city
  lights (to 0.49 km) are streamed for the view and composed by the same shader. Ground is Blue Marble to 0.49 km and
  Sentinel-2 cloudless below that; relief to 32 m; the zoom floor is 5 m a pixel, where the window's grid is
  Sentinel-2's 10 m magnified to 2.4 m for the streets drawn on it. Blue Marble's fine structure is added to the
  shipped month. The lights ride in the imagery texture's alpha (under a street plan, in the elevation texture's):
  the shader has no spare sampler. A window arrives in two passes (`quickPlan`): the same rectangle two levels coarser, whole, then
  the full layers, the imagery painted in from the middle of the window as its tiles land.
- **Sentinel-2's colours and the month** (`earth.frag.glsl`: `s2Scene`, `AIR_LT`, `AIR_I`, `detPack`;
  `Research/modeling/s2_transfer.py`; `build/season_ref.py`) - the picture is read as scene light by one curve
  for its three channels and the shader's own air at a standard Sun is taken out to give albedo: the ground at the
  picture's own season. The month is Blue Marble's, joined in albedo: its brightness as a ratio at 5 km, its
  colour as a shift, Blue Marble's month against Blue Marble at the picture's own season
  (`fields/albedo_ref.webp`, carried to the shader as two bytes packed into the elevation texture's fourth
  channel). What Sentinel-2 photographs grey is drawn grey, and fields turn with the year as they do from further
  out. From 125 m a device pixel inwards the air's veil is thinned and the contrast raised (`airCut`), by eye.
  `audit_closecolour.py` holds the constants to the shader's air and scores the grey at eleven cities and the
  season at 23 places.
- **Streets and buildings** (`js/streets.js`, `js/streets.worker.js`, `js/detail.js :: _streets`) - closer than
  120 m a pixel, OpenStreetMap's roads, buildings and commercial ground as vector tiles from OpenFreeMap, decoded
  by the page's own reader and drawn by a worker on the window's grid, each tile inside its own square. Two
  things are drawn: a DAY OVERLAY laid over Sentinel-2 (roads at their width on the ground; from 8 m a pixel
  roofs, and shadows for Sentinel-2's mid-morning Sun), and a PATTERN in the imagery texture's alpha (roads 0.5
  and over by class, built ground under 0.3). At night the shader puts Black Marble's measured light on the
  pattern as lamps (`lamps()`, `streetLit`); in the Atlas style it reads the pattern as a street plan.
  `audit_streets.py` checks the footprints' place against ESA WorldCover's built-up ground.
- **Land or water, close in** (`js/detail.js :: _occurrence`) - inside the window each texel is land or water by
  JRC Global Surface Water's record (Landsat 30 m, 1984-2021; water at least half the time), streamed as tiles
  on the elevation's own tiling and carried as a share in the elevation texture's third channel. Polewards of
  78 N and 59 S the record has no tiles and release 1.6's rule stands in (`js/water.js`, in a worker: NASA's
  250 m mask, sharpened by the picture's colour, doubted where it floods Manhattan). Scored by
  `audit_closewater.py` at 23 places against ESA WorldCover 2021.
- **The political units** (`build/units.py`) - Natural Earth's countries with France's five overseas departments
  taken out as units of their own. The names, the identity raster and the label audit all read this one list.
- **The probe and cards** (`js/cards.js`) - click any pixel for every field's value there and then, each with its tier.
- **Planet now** (`js/dash.js`) - integrals of the shown fields: people in daylight, sea-ice extent, global mean temperature.

---

## 6. Build and deploy

```bash
# serve the app (no caching)          -> http://localhost:8150
python3 build/serve.py 8150

# tests and pre-flight - run before and after any change
./venv/bin/python build/test_frames.py          # every source layout -> canonical frame
node build/test_app_math.mjs                     # ephemeris vs almanac, projection, cameras
./venv/bin/python build/check_shaders.py        # compile every shader

# rebuild data (each step asserts landmarks and stamps web/version.json)
./venv/bin/python build/fetch_sources.py        # ~3.6 GB into data/ (gitignored); idempotent
./venv/bin/python build/fields_surface.py       # water albedo elev night clouds   (albedo:7 = one month)
./venv/bin/python build/cloud_grain.py          # cloud grain (fetch_sources.py cloudtex first)
./venv/bin/python build/fields_climate.py       # atmo ocean currents
./venv/bin/python build/fields_human.py         # pop ships lanes co2 countries
./venv/bin/python build/vectors.py              # political places physical plates quakes volcanoes power stats air

# look at a frame at full resolution (the browser pane may be hidden or scaled)
#   in the page:  ATLAS.step(200); await ATLAS.shot('name.jpg')   ->  scratchpad/name.jpg
```

The build **runs the validators first and refuses to publish if one moved backwards**:

```bash
./venv/bin/python Research/modeling/audit_all.py           # eleven checks, 3-4 min
./venv/bin/python build/build_site.py                     # audits, then docs/ for GitHub Pages; never pushes
./venv/bin/python Research/modeling/audit_all.py --quick   # skip the three that need a browser
```

| check | baseline | what it catches |
|---|---|---|
| `build/test_frames.py` · `build/test_app_math.mjs` · landmark asserts in every build step | all pass (2026-11-09) | a flipped, shifted or mis-registered source; a wrong Sun; a camera and shader that disagree |

The baselines are not all zero and should not be — a genuine open disagreement belongs in the
baseline with a note. The rule is that **none of them may move backwards**; when one legitimately
improves, tighten the baseline in the same commit, so the ratchet turns one way only.
`SKIP_AUDIT=1` overrides, deliberately awkwardly.

**Verify the live data-version stamp after every push.**

---

## 7. Traps

Failures that have each cost real time here. *(The general catalogue is in
`Modeling Studio/references/TRAPS.md`; add new ones to both.)*

- **NOAA PSL's file server truncates large files and still answers 200**, and answers 429 to bursts. The fetcher checks
  Content-Length; the two OISST fields are read month by month over OPeNDAP with backoff.
- **PSL's long-term-mean sea-ice concentration is conditional on ice being present.** Uncorrected it gave an Antarctic
  February extent four times the observed one. Multiply by `valid_yr_count / 30`. Found by the NSIDC witness, not by eye.
- **A build step that fails must not lose an earlier step's metadata.** `climate.json` was once written with 2 of 12
  encodings; the shader silently fell back to [0,1] and the tracers crashed. Metadata is now saved after every step and
  the script refuses to finish with a missing encoding.
- **Stale browser cache looks like a failed build.** Every data and shader URL carries `?v=` from `web/version.json`.
  The dev server sends `no-store`. Code files do not carry the stamp yet (register G2).
- **The browser pane can be hidden or zero-sized.** `requestAnimationFrame` stops, the canvas stays black and screenshots
  are scaled down. Use `ATLAS.step(n)` to run frames by hand and `ATLAS.shot()` to capture at device resolution.
- **A landmark assertion is an instrument too.** Four of this session's failed asserts were wrong thresholds or wrong
  places (an oasis in the "empty" Western Desert; a coastal pixel for the Singapore Strait). Check the audit first.
- **None of the three big rasters starts at -180/90.** GHSL starts at -180.0079, 89.0996; the ship-density world file
  gives a pixel centre, not a corner; EDGAR and ETOPO are south-first. Read the georeferencing; go through `frames.py`.
- **A lane is not a density.** Smoothed AIS density sent ship tracers swirling over open ocean; a lane is a coherent
  ridge. Model the object (WORKING-RULES 3).

---

## 8. Sources

| role | source |
|---|---|
| see below | full table follows |
| land surface, 12 months | NASA Blue Marble Next Generation 2004 (Stockli et al. 2005) - public domain |
| elevation and bathymetry | NOAA NCEI ETOPO 2022 60 arc-second ice surface, doi:10.25921/fd45-gt74 - public domain |
| night lights | NASA Black Marble 2016 (Roman et al. 2018) - public domain; close in, the same picture at 500 m through NASA GIBS |
| the ground closer in than 0.6 km a pixel (streamed) | Sentinel-2 cloudless 2016 by EOX IT Services GmbH, https://s2maps.eu (contains modified Copernicus Sentinel data 2016) - CC BY 4.0 |
| land and water closer in than 5 km a pixel (streamed) | Global Surface Water, occurrence 1984-2021 (Pekel et al. 2016, Nature 540) - Source: EC JRC/Google; free with attribution. Checked against ESA WorldCover 2021 v200 (CC BY 4.0), not shipped |
| streets and buildings closer in than 120 m a pixel (streamed) | (c) OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright), as vector tiles in the OpenMapTiles schema from OpenFreeMap (https://openfreemap.org) - credited on the map while its tiles are on screen |
| the season of the close-in picture | `fields/albedo_ref.webp`: this project's own composite of the Blue Marble months above, by `build/season_ref.py` |
| wide rivers | NASA MODIS Land Water Mask MOD44W (Carroll et al. 2009) through NASA GIBS, along Natural Earth 1:10m river lines - public domain |
| clouds (texture) | NASA Blue Marble: Clouds (Stockli 2002) - public domain |
| clouds (fine structure) | NASA VIIRS (NOAA-20) corrected reflectance via GIBS, four scenes of 2023 - public domain |
| wind, temperature, pressure, cloud fraction | NCEP/NCAR Reanalysis 1 (Kalnay et al. 1996), 1991-2020 means, NOAA PSL - public domain |
| precipitation | GPCP v2.3 (Adler et al. 2018), 1991-2020 means - public domain |
| sea-surface temperature, lake ice | NOAA OISST v2.1 (Huang et al. 2021), 1991-2020 means - public domain |
| sea ice | NSIDC Sea Ice Index v4 (G02135; Fetterer et al. 2025), 720 monthly grids 1991-2020 - public domain, citation requested |
| surface currents | NCEP GODAS 5 m, 2019-2023 means - public domain |
| countries, borders, places, names | Natural Earth 5.1.2, de facto worldview - public domain |
| where the sea, the land and the lakes are | Natural Earth 5.1.2, 1:10m land, minor islands, lakes - public domain; Antarctica's ice front and the colour of shallow water from Blue Marble |
| lake depth (build time; the ice it helps compute ships) | HydroLAKES v1.0 (Messager et al. 2016) - CC BY 4.0 |
| lake ice (witness only, not shipped) | NSIDC Global Lake and River Ice Phenology Database, G01377 - citation required |
| plate boundaries | Bird (2003) PB2002, G-cubed 4(3) 1027; GeoJSON H. Ahlenius - ODC PDDL |
| earthquakes | USGS ANSS ComCat (record) and real-time feed (live) - public domain |
| volcanoes | NOAA NCEI Global Volcano Locations - public domain |
| population | JRC GHSL GHS-POP R2023A epoch 2025 (Schiavina et al. 2023) - CC BY 4.0 |
| shipping density | World Bank / IMF Global Shipping Traffic Density, AIS 2015-2021 - CC BY 4.0 |
| fossil CO2 | EDGAR v8.0 (Crippa et al. 2023, JRC), 2022 - CC BY 4.0 |
| power stations | WRI Global Power Plant Database v1.3.0 - CC BY 4.0 |
| airports | OurAirports - public domain (flows between them are this project's model) |
| country statistics | World Bank Open Data - CC BY 4.0 |
| live imagery, aurora, satellites | NASA GIBS (VIIRS); NOAA SWPC OVATION; CelesTrak + satellite.js 5.0.0 (MIT) |

**Canonical frame:** Equirectangular WGS84 rasters, pixel-centre registered, column 0 centred at -180 + half a cell, row 0 centred at +90 - half a cell (north first). One clock: UTC milliseconds. Climatology is addressed by fractional month with keyframes at mid-month, cyclic. Administrative key: Natural Earth `ADM0_A3`. Rendering treats latitude as spherical on a 6371.0088 km sphere — every source is converted into it; the conversions are
in `build/frames.py`, tested by `build/test_frames.py`.

---

## 9. Known limits

The section that makes the rest credible. State plainly what is reconstructed, what is contested,
and what the model cannot know.

- **This is a typical year, not this year.** No weather history, no forecast.
- **Lake ice is modelled.** Outside the Great Lakes and Ladoga a lake's ice comes from the air temperature there and the lake's depth (`build/lakeice.py`): 10 days a year out on lakes it was not fitted to. Depth is measured for every lake over 500 km² and mostly estimated below that (Mjøsa is iced 135 days against 50); a great lake freezes whole or not at all. Wide rivers are lines, not water (C4, A10).
- **Clouds are illustrative.** How much cloud there is and how much light it returns come from a satellite climatology (ISCCP) and are checked against VIIRS and EPIC; where each cloud is, is modelled. Close in, the fine structure is real cloud's, borrowed: one photographed sheet, one cumulus field and one storm stand in for all of their kind and repeat every 2048 km. It reads as cloud; it is not the cloud of the place. Wrong in measured ways over the Amazon, the trades and the Congo (register B1).
- **Sea-ice extent matches NSIDC because the edge is placed to make it match**; ice area inside the edge runs up to 15% low. Each of NSIDC's 720 monthly grids on its own converts within 1.5% in the middle case and 4.0% at worst (C1).
- **The ground's albedo is Blue Marble re-read against EPIC's view from the Sun's side**, not measured reflectance; dense forest is probably drawn too bright in the red (A7).
- **Below 5 km per pixel the finer ground is streamed** from NASA and AWS while you look (the page says so in About); without a network it falls back to magnified fields. The sea floor is not refined (A2).
- **Air traffic and ship motion are modelled flows.** No vehicle on screen is a real vehicle.
- **Rivers are water only where they fill a 5 km cell**: about 2.5 km wide and up. Nine wide reaches are drawn for 87% of their length on average; the Parana for half, the Congo for 71%; the Mississippi, Danube, Nile and upper Yangtze stay lines. The check that says so is not independent of the mask's own source.
- **Close in, the night ground is brighter than it is**, about ten times moonlight and shaded from the north-west, so that the lights have a landscape under them. The Night lights card says so. Seen whole, the night is the real one.
- **A large city at night is one even field of gold between 100 m and 2 km a pixel**, and the step from that to the street view is abrupt. Every public 500 m night picture is at full brightness there.
- **Night, close in, is a model of where light comes from.** How much light leaves each 500 m is measured; that it sits along OpenStreetMap's streets as lamps, in yards and car parks, and not in parks, is a rule. Which streets are lit, where a lamp stands and its colour are not known, and the lamps' light is not made to add up to the measured amount (F16).
- **Close in, four things are not the real view, and each card says so**: cloud thins and is gone by 150 m a pixel; the exposure rises by up to 1.7 times; from 125 m a pixel the air's veil is thinned by four fifths and the contrast raised, by eye (A19); a city's light at night is placed by rule (the amount is measured, the placing modelled).
- **The close-in ground is 2016, one season, another camera.** Sentinel-2 is read by its own table: ground it photographs grey is drawn 5% off grey at eleven city places (48% before release 1.7). Sentinel-2's grey is taken as grey; nothing independent says so. The month's change of colour reaches the close view whole (0.4% short at 23 places; 39% by release 1.7's rule), given a reference month per place that is fitted and has no witness; the picture's form is still one season's. Grey ground is 5.4% off grey, 9.1% at the worst city (Amsterdam). Winter snow close in is the shipped field's 5 km patches.
- **Streets and buildings are OpenStreetMap's**: complete in some countries, sparse in others; few buildings have a height (the rest are drawn at 7 m); shadows are for one Sun, not the hour shown; below 10 m a pixel the photograph under them is only magnified. Footprints sit within 12 m of an independent map of built-up ground at eight cities; the roads have no such check. On a wide screen at high latitude their grid is 5 m, not 2.5 (A20). Central Paris at 5 m a pixel is about 10 MB of street tiles.
- **Where the water is, close in, is a 37-year record, not the picture**: JRC Global Surface Water, water at least half of 1984-2021. 2.2% of the ground wrong at 23 places against ESA WorldCover 2021 (release 1.6's reading 3.2%, NASA's mask alone 5.6%, the 5 km field 11%). A lake or reservoir that has fallen is drawn wider than the picture under it (Lake Mead, the Dead Sea: A17); the record lies 10 to 30 m west of the picture across Europe and the north-eastern United States; polewards of 78 N and 59 S release 1.6's reading stands in.
- **The close-in picture is audited in three places only**: where its water is, where its buildings are, and what its join does to grey ground and to the season (by an emulation of the join, not the shader itself). Its relief, its loading and everything else about it are checked by eye. Loading times were measured from one place on one network.
- **Vintages differ**: land surface 2004, night lights 2016, borders 2022, emissions 2022, population 2025.
- **At whole-Earth framing 125 of the 177 states in view are named**, 18 of them only in the Europe and Lesser Antilles insets. Sixteen European states, the Levant and the Caucasus still are not; the insets need open sea between the panels and are left out in a small window (F1).
- **Against NASA EPIC the Space style is close, with named exceptions**: cloud over land above the median, the outermost 2% of the disc, snow at a low Sun (A1, A8, A9). The full list is `Research/MODEL-GAPS.md`: 50 items, none at P1

---

## 10. Reference material

- **National Geographic, *The World - Political*** (Winkel Tripel) - the baseline for the Atlas register. Copyright
  National Geographic Society: measured against, never reproduced, never committed (`reference/` is gitignored).
- **NASA EPIC (DSCOVR) full-disc imagery** - the standard for the Space register. Eight frames scored in the verify round; `Research/modeling/epic_compare.py`, pairs in `Research/figures/epic/`.
- **NSIDC Sea Ice Index** - now the SOURCE for sea ice; its per-year grids and extents remain the check on the conversion. **NASA EPIC**, eight frames and a hundred more composited cloud-free - the witness for the lit globe. **Published almanac values** - the witness for the Sun and Moon.

`HANDOFF.md` carries the live state, the measured facts, and the work queue for a fresh session.
