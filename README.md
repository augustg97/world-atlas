# World Atlas

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
  fields_climate.py  atmosphere and ocean climatologies -> month-stacked atlases + climate.json
  fields_human.py    population, shipping density and lane ridges, CO2, country raster
  vectors.py         political geometry, places, names, plates, quakes, volcanoes, power, air model, statistics
  check_shaders.py   test_app_math.mjs   stamp.py   serve.py
web/          the app: no build step, ES modules
  shaders/    common.glsl (the two cameras)  earth.frag.glsl (the substrate)  lines.*  points.*
  js/         main (loop, state)  fields (the field store)  earth  camera  astro  overlays  particles
              catalog (every layer, tier, source, limit)  cards  data  dash  live  ui
  fields/     69 MB of rasters      data/  4 MB of features      version.json
data/         2.6 GB of sources and caches - gitignored
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
  measured shipping-lane ridges; aircraft as a pure function of the clock on a gravity model.
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
./venv/bin/python build/fetch_sources.py        # ~2.6 GB into data/ (gitignored); idempotent
./venv/bin/python build/fields_surface.py       # water albedo elev night clouds   (albedo:7 = one month)
./venv/bin/python build/fields_climate.py       # atmo ocean currents
./venv/bin/python build/fields_human.py         # pop ships lanes co2 countries
./venv/bin/python build/vectors.py              # political places physical plates quakes volcanoes power stats air

# look at a frame at full resolution (the browser pane may be hidden or scaled)
#   in the page:  ATLAS.step(200); await ATLAS.shot('name.jpg')   ->  scratchpad/name.jpg
```

The build **runs the validators first and refuses to publish if one moved backwards**:

```bash
./venv/bin/python Research/modeling/audit_all.py           # nine checks, 2-3 min
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
| night lights | NASA Black Marble 2016 (Roman et al. 2018) - public domain |
| clouds (texture) | NASA Blue Marble: Clouds (Stockli 2002) - public domain |
| wind, temperature, pressure, cloud fraction | NCEP/NCAR Reanalysis 1 (Kalnay et al. 1996), 1991-2020 means, NOAA PSL - public domain |
| precipitation | GPCP v2.3 (Adler et al. 2018), 1991-2020 means - public domain |
| sea-surface temperature, sea ice | NOAA OISST v2.1 (Huang et al. 2021), 1991-2020 means - public domain |
| surface currents | NCEP GODAS 5 m, 2019-2023 means - public domain |
| countries, borders, places, names | Natural Earth 5.1.2, de facto worldview - public domain |
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
- **Clouds are illustrative**: real shapes, modelled positions (register B1).
- **Sea-ice extent runs 10-17% high at the seasonal maxima** and more at the Antarctic minimum (C1).
- **Below 5 km per pixel the picture is magnified fields, not finer fields** (A2).
- **Air traffic and ship motion are modelled flows.** No vehicle on screen is a real vehicle.
- **Vintages differ**: land surface 2004, night lights 2016, borders 2022, emissions 2022, population 2025.
- **At whole-Earth framing only about 25 states are named**, far fewer than the baseline sheet (F1).
- **Nothing has yet been scored against the reference imagery** (A1). The full list is `Research/MODEL-GAPS.md`: 31 items, 6 at P1

---

## 10. Reference material

- **National Geographic, *The World - Political*** (Winkel Tripel) - the baseline for the Atlas register. Copyright
  National Geographic Society: measured against, never reproduced, never committed (`reference/` is gitignored).
- **NASA EPIC (DSCOVR) full-disc imagery** - the standard for the Space register. Eight frames scored in the verify round; `Research/modeling/epic_compare.py`, pairs in `Research/figures/epic/`.
- **NSIDC Sea Ice Index** - the witness for sea ice. **Published almanac values** - the witness for the Sun and Moon.

`HANDOFF.md` carries the live state, the measured facts, and the work queue for a fresh session.
