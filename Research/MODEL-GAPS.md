# Model gaps register — World Atlas

Every open item, tied to the specific subsystem it would change. **This is the handover surface
between research and the build.**

Priority: **P1** = closes a known visible defect · **P2** = adds real fidelity ·
**P3** = correctness housekeeping · **P4** = worth knowing, no action yet.

Status: **RESOLVED** · **MEASURED** · **DELIVERED** · **APPLIED** · **RETIRED** ·
**CLOSED, negative result** · items with no status are open.

IDs are referenced from code comments and commit messages. **Never recycle one.**

---

## APPLIED (kickoff session, 2026-11-09)

| item | what shipped | measured |
|---|---|---|
| frame conversions as tested code | `build/frames.py` + `build/test_frames.py` | 9 layouts pass; max error 0.003 of field range |
| conditional sea-ice mean | `valid_yr_count / 30` correction in `fields_climate.step_ocean` | Antarctic February extent 12.3 → 5.6 M km² (NSIDC ~3.0); Arctic September 9.7 → 7.2 (NSIDC ~6.2) |
| air-traffic mass | catchment GDP, nearest-airport catchments | largest modelled hubs went from DAC, LYP, CCU… to HND, EWR, ATL, LHR… |
| ship lanes | ridge + coherence detector in `fields_human.step_lanes` | "ridge" cells 21% → 6% of the grid; tracers leave open-ocean speckle and follow the lanes the lens shows |
| stale-data guard | `web/version.json` stamp on every fetch | a cached two-key `climate.json` had crashed the tracers once |
| ephemeris check | `build/test_app_math.mjs` | Sun declination within 0.004° at the four 2026 seasonal instants |

---

## A. The lit globe (substrate)

| # | P | item | touches | from |
|---|---|---|---|---|
| A1 | **P1** | **No side-by-side against the reference yet.** Fetch 6–8 NASA EPIC full-disc frames at stated instants, set the clock and camera to match, and compare limb, glint position, ocean colour and overall contrast. This is the standard-for-done in SCOPE §8 and nothing has been scored against it | `earth.frag.glsl` lighting constants | SCOPE §8 |
| A2 | **P1** | **The zoom floor is not met by fields.** SCOPE asks for 2 km/px; shipped fields stop at 5 km (8192 px). Below that the picture is a magnified texture. Stream elevation (AWS terrain tiles, Web Mercator — needs a `frames` conversion and test) and imagery (NASA GIBS 500 m BMNG, EPSG:4326) into a focus window around the camera | new `detail.js`, two samplers in the shader | SCOPE §2 |
| A3 | P2 | Sun glint reads as a broad grey patch rather than a bright specular highlight. The Cox–Munk width is physical; the tone map and gain are not. Check against EPIC (A1) before touching | `earth.frag.glsl` water block | visual review |
| A4 | P2 | Relief shading is weak at regional zoom and there is no sub-grid detail grown from mechanism. Blocked on A2 for real slopes | `Earth.reliefK`, shader | visual review |
| A5 | P3 | Lakes never freeze and shallow banks (Bahamas) render as land colour: the water mask is BMNG's ocean fill plus dark-pixel lakes, with no ice state for inland water | `fields_surface.step_water` | build notes |
| A6 | P3 | The Atlas style's permanent-ice test is a brightness-and-latitude heuristic; mountain glaciers and seasonal snow can be misread | `earth.frag.glsl` atlas block | build notes |

## B. Atmosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| B1 | **P1** | **Clouds: the thing most expected to be wrong.** A 2002 cloud photograph moved by a 2.5° monthly-mean wind and thinned by reanalysis cloud fraction. Replace the coverage driver with a satellite cloud climatology (MODIS/ISCCP monthly — needs an Earthdata route; NEO is gone) and measure the result against it per 10° band | `fields_climate.step_atmo`, `cloudAt()` | interview |
| B2 | P2 | No independent witness for wind, temperature, pressure or precipitation. Score the shipped means against ERA5 monthly means (measure-against only) | new `Research/modeling/audit_climate.py` | SOURCE-SURVEY §5 |
| B3 | P2 | The daily temperature cycle is a three-parameter model with no check. Compare its range against a station or reanalysis diurnal-range climatology | `airTemp()` in shader and `cards.js` | SCOPE §4 |
| B4 | P3 | The lapse-rate correction is a constant 6.5 K/km; winter inversions over ice sheets and basins are wrong in sign | same | SOURCE-SURVEY |
| B5 | P3 | Cloud drift is sped up 2.5× and cloud shadows use an exaggerated height. Both are stated in About; neither is measured | `earth.frag.glsl` | About panel |

## C. Ocean

| # | P | item | touches | from |
|---|---|---|---|---|
| C1 | **P1** | **Sea-ice extent still runs high** after the presence correction: +10% Arctic March, +16% Arctic September, +17% Antarctic September, +87% Antarctic February against NSIDC. Part is definitional (the extent of a 30-year mean field is larger than the mean of yearly extents). Fix by building the climatology from yearly monthly files (extent per year, then mean), and write the comparison as `audit_ice.py` | `fields_climate.step_ocean` | witness at kickoff |
| C2 | P2 | Currents come from a 1° ocean model: no eddies, a weak Gulf Stream (0.12 m/s where drifters give ~1), nothing poleward of 65°N / 74°S. A drifter-derived climatology would be the better source | `fields_climate.step_currents` | landmark check |
| C3 | P3 | Ocean colour is one hue plus a shelf tint; no chlorophyll field | shader water block | source survey (NEO gone) |

## D. Solid Earth

| # | P | item | touches | from |
|---|---|---|---|---|
| D1 | P3 | Plate boundaries carry only subduction / other; ridges and transforms are not distinguished | `vectors.step_plates` | build notes |
| D2 | P3 | Volcano "last eruption" is NCEI's coded class, not a date | `cards.volcanoCard` | build notes |

## E. Biosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| E1 | P2 | The system has one lens, and it is a proxy. Add a real vegetation index (monthly NDVI/EVI), fire counts and ocean chlorophyll once a shippable route exists | `catalog.js`, a new atlas | source survey |

## F. Humanity

| # | P | item | touches | from |
|---|---|---|---|---|
| F1 | **P1** | **Sheet-scale label coverage is far below the baseline.** At the whole-Earth framing on a 1440 px window about 25 states are named; the National Geographic sheet names all of them. Needs a label placement pass (leader lines, abbreviations, smaller type for small states) and an audit that counts labelled sovereign states per zoom | `overlays.Labels`, `data.labelItems` | SCOPE §8 |
| F2 | P2 | Population witness: sum the GHSL field per country (already cached) against World Bank totals and list every unit off by more than 5% | new audit | SOURCE-SURVEY §5 |
| F3 | P2 | Air traffic cannot reproduce hubs (Atlanta, Dubai, Istanbul are under-weighted; small rich catchments over-weighted). Score modelled airport ranks against a published passenger ranking and state the rank correlation on the card | `vectors.step_air` | build notes |
| F4 | P2 | Endonyms exist for 50 of 242 units (those whose main language Natural Earth translates). The rest show English only | `vectors.ENDONYM_LANG` | SCOPE §6 |
| F5 | P2 | No electricity-demand field although SCOPE's layer table lists a demand wave; only the people-awake indicator exists | `dash.js` | SCOPE §4 |
| F6 | P3 | A straight amber lane lies along ~3°N across the eastern Pacific. It is in the AIS data; it may be a real Panama–Asia track or a latitude artefact. Inspect the full-resolution source | `fields_human.step_ships` | visual review |
| F7 | P3 | Dispute cards carry Natural Earth's one-line notes only | `cards.disputeCard` | card contract |
| F8 | P3 | Feature, volcano and power-station cards are generic tier; no curated text exists for any physical feature | `cards.js` | card contract |
| F9 | P3 | Country tints are a 4 km raster sampled nearest: stair-stepped along borders when zoomed in (hidden under the vector line at most scales) | `fields_human.step_countries` | build notes |
| F10 | P4 | Time zones (Natural Earth, public domain) are downloaded and unused | — | fetch list |

## G. Engine, delivery and verification

| # | P | item | touches | from |
|---|---|---|---|---|
| G1 | **P1** | **No audit suite and no visual ratchet.** `Research/modeling/audit_all.py` is the scaffold's template. Wire in the frame tests, the app-math tests, the landmark asserts, C1, F1, F2 and `tools/frame_baseline.py` (the app can already render a deterministic frame: `ATLAS.step()` + a fixed `#t=`) | `Research/modeling/` | `/model-verify` |
| G2 | P2 | Not deployed. `docs/` is empty; publishing is the user's explicit decision. Before any deploy: code files need the version stamp too (only data and shaders carry it), and GHSL/EDGAR/WRI/World Bank attributions must be visible on the live page (they are, in About) | `build/` | SCOPE §11 |
| G3 | P2 | First-frame budget not measured. SCOPE says ≤ 6 MB and ≤ 1.5 s; the boot set is about 8 MB plus 23 MB of relief and elevation behind it | `fields.boot` | SCOPE §11 |
| G4 | P3 | Performance is unmeasured: full-screen shader at 2× device pixels, re-run on every camera move | `main.js` cache | build notes |
| G5 | P3 | The live-feed paths (aurora, satellites) were written and not exercised in a visible browser this session | `live.js` | this session |

---

**Count: 31 items — 6 at P1.** The ones that would move the model furthest, in order:

1. **A1** — score the globe against EPIC. Until then "reads as a photograph" is an opinion.
2. **B1** — the clouds, which the interview named as the likeliest thing to be wrong.
3. **A2** — streamed detail, so the 2 km floor is met by fields rather than by magnification.
4. **G1** — the audit suite and visual ratchet, so the next change cannot move these backwards.
5. **C1** — sea ice built per year, with its audit.
6. **F1** — label coverage against the baseline sheet.
