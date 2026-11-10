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

## APPLIED (verify round, 2026-11-09)

Eight NASA EPIC frames (two per season, four longitudes), the atlas rendered from the same place at the
same instant, both resampled to one disc. `Research/modeling/epic_compare.py`; pairs in `Research/figures/epic/`
(`_r0` before, `_r7` after). Display values 0-255, mean absolute difference over the eight frames:

| measure | before | after | what changed |
|---|---|---|---|
| glow outside the limb | 73.9 | 0.15 | the limb glow had a 57 km and a 190 km scale height; now one Rayleigh model, 8 km |
| clear-ocean colour (RGB distance) | 40.0 | 4.6 | exposure and gamma fitted to EPIC; water-leaving colour set to a few percent |
| clear-ground colour, 6 regions | 51.1 | 15.9 | same, plus two-way attenuation of the ground by the air |
| mean brightness of the disc | 27.0 | 7.0 | Reinhard tone map replaced by exposure 0.43, gamma 1.91, soft shoulder |
| bright-white fraction of the disc | 0.159 | 0.042 | cloud opacity steepened above the 60th percentile to match EPIC's distribution over open ocean |
| limb against centre (cos 0.1-0.2 / 0.8-1.0) | 0.132 | 0.063 | sunlight now falls as the cosine (was cos^0.72); haze from single scattering |
| sun glint, specular water against water 20-30 degrees off | 0.17 | 0.17 | gain now the physical one (Fresnel x pi x D / 4 mu); four of five frames within 0.14, one frame 0.5 low |
| contrast (std of luminance) | 2.4 | 3.5 | **worse by 1.1.** CANCELLATION: the old frame matched EPIC's spread while its mean was 27 high and its darkest twentieth 18 high. The atlas now lacks EPIC's brightest cloud tops (p99.5 204 against 221) |

Also shipped: cumulus over humid land (see B1); `?frozen=1` deterministic frames and `window.__FRAME_READY`;
a reference camera (`ATLAS.refView`); restart after a lost GL context; the fly-to animation clamped (it threw
the sheet camera to 0,0 when a frame's timestamp preceded the click). And the instruments: `audit_all.py`
with nine checks, six frozen baseline frames, the NSIDC witness for all twelve months, the EPIC sun witness.

**Honest answer against the standard in SCOPE section 8: not yet.** Colour, exposure, ocean, desert and the limb
now sit within a few display levels of the photograph. Cloud does not: where it is cannot be compared, its
texture is a magnified photograph, and vegetated land still reads darker than EPIC (A7).

---

## A. The lit globe (substrate)

| # | P | item | touches | from |
|---|---|---|---|---|
| A1 | — | **DELIVERED 2026-11-09.** Scored against eight EPIC frames; table above; held by `audit_all.py` (check `epic`). The remaining distance is A7 and B1 | `earth.frag.glsl`, `epic_compare.py` | SCOPE §8 |
| A2 | **P1** | **The zoom floor is not met by fields.** SCOPE asks for 2 km/px; shipped fields stop at 5 km (8192 px). Below that the picture is a magnified texture. Stream elevation (AWS terrain tiles, Web Mercator — needs a `frames` conversion and test) and imagery (NASA GIBS 500 m BMNG, EPSG:4326) into a focus window around the camera | new `detail.js`, two samplers in the shader | SCOPE §2 |
| A3 | P3 | **APPLIED 2026-11-09**: the gain is now physical. Residual: in the December Americas frame the specular point lies against the Chilean coast and the atlas's glint ratio is 1.04 against EPIC's 1.53; EPIC also shows a compact bright core the Cox-Munk mean slope does not produce | `earth.frag.glsl` water block | EPIC |
| A4 | P2 | Relief shading is weak at regional zoom and there is no sub-grid detail grown from mechanism. Blocked on A2 for real slopes | `Earth.reliefK`, shader | visual review |
| A5 | P3 | Lakes never freeze and shallow banks (Bahamas) render as land colour: the water mask is BMNG's ocean fill plus dark-pixel lakes, with no ice state for inland water | `fields_surface.step_water` | build notes |
| A6 | P3 | The Atlas style's permanent-ice test is a brightness-and-latitude heuristic; mountain glaciers and seasonal snow can be misread | `earth.frag.glsl` atlas block | build notes |

| A7 | P2 | **Vegetated land reads darker and bluer than EPIC.** With clouds off, land the atlas draws at about (40, 54, 62) sits under an EPIC clearest-twentieth of about (68, 70, 66), in every latitude band from the tropics to 70 N; desert and open ocean match. Cumulus (B1) closed part of it: over all land the atlas is now 10-15 levels under EPIC at every percentile (it was 23). Cause not established. Candidates: Blue Marble's display values understate dark-canopy reflectance (it is an enhanced picture, read here as sRGB); aerosol and humidity haze over land, which the Rayleigh-only air has none of; more small cloud than modelled. Needs a clear-sky EPIC composite (many days of one region) to separate ground from cloud | `fields_surface.step_albedo`, shader air block | EPIC |
| A8 | P3 | Snow and ice at a low Sun read grey: Antarctica in the December frames is far dimmer than in EPIC. Snow scatters forward and stays bright at grazing light; the surface model is Lambert. Seen, not measured | shader | EPIC |

## B. Atmosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| B1 | **P1** | **Clouds: the thing most expected to be wrong.** A 2002 cloud photograph moved by a 2.5° monthly-mean wind and thinned by reanalysis cloud fraction. **Measured 2026-11-09** (`epic_cloud_cdf.py`): over open ocean the brightness distribution now matches EPIC to the median and runs 6-17 levels dim from the 60th percentile up; over land 10-15 dim throughout. **Added:** a second regime, cumulus over humid land, with amount from the month's rainfall and the local solar time. Its cells are noise at 2-3 km, not cloud shapes, and close in the big systems are a magnified 10 km texture. Still to do: a satellite cloud climatology for coverage per 10° band (MODIS/ISCCP; needs an Earthdata route), and cloud that resolves below 10 km | `fields_climate.step_atmo`, `cloudAt()`, `cumulusAt()` | interview |
| B2 | P2 | No independent witness for wind, temperature, pressure or precipitation. Score the shipped means against ERA5 monthly means (measure-against only) | new `Research/modeling/audit_climate.py` | SOURCE-SURVEY §5 |
| B3 | P2 | The daily temperature cycle is a three-parameter model with no check. Compare its range against a station or reanalysis diurnal-range climatology | `airTemp()` in shader and `cards.js` | SCOPE §4 |
| B4 | P3 | The lapse-rate correction is a constant 6.5 K/km; winter inversions over ice sheets and basins are wrong in sign | same | SOURCE-SURVEY |
| B5 | P3 | Cloud drift is sped up 2.5× and cloud shadows use an exaggerated height. Both are stated in About; neither is measured | `earth.frag.glsl` | About panel |

## C. Ocean

| # | P | item | touches | from |
|---|---|---|---|---|
| C1 | **P1** | **Sea-ice extent runs high in every month.** `audit_ice.py` (2026-11-09) against NSIDC's own 1991-2020 means for all twelve months: Arctic +11% in winter and **+29 to +31% from July to October**; Antarctic +16% at the September maximum and **+55 to +94% from December to March**. The kickoff figures were four round numbers and understated it (Arctic September is 5.58, not 6.2). **CLOSED, negative result** for the cheap fix: counting only cells iced in at least half the years, or summing area times the fraction of years iced, still leaves +9 to +92%, so the excess is in OISST's ice field itself, not in how a mean is thresholded. The fix is a different source: NSIDC's monthly concentration grids per year (public; polar stereographic, so it needs a `frames` conversion and test), extent per year, then the mean | `fields_climate.step_ocean` | `REGISTER-ice.md` |
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
| F1 | **P1** | **Sheet-scale label coverage is far below the baseline.** At the whole-Earth framing on a 1440 px window **21 of 204 states** are named (`audit_labels.py`, measured from what the label layer placed; 10 on the globe); the National Geographic sheet names all of them. Needs a label placement pass (leader lines, abbreviations, smaller type for small states) and an audit that counts labelled sovereign states per zoom | `overlays.Labels`, `data.labelItems` | SCOPE §8 |
| F2 | P3 | **DELIVERED 2026-11-09** as `audit_population.py`: 192 units compared, the summed field 8.160 bn against 8.191 bn (-0.4%); **26 units differ by more than 10%**, listed in `REGISTER-population.md`. The largest are a border-raster effect (Republic of the Congo +48% beside Kinshasa; Moldova +40%), city states and islands (Macau, Singapore, Maldives, Cyprus) and vintage (Somalia, Yemen). Open: assign people by polygon, not by the 4 km country raster | `fields_human.step_countries` | SOURCE-SURVEY §5 |
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
| G1 | — | **DELIVERED 2026-11-09.** `audit_all.py`: frame tests, app math (now with eight EPIC sun positions), shader compile, audit selftests, sea ice, population, label coverage, EPIC, and the visual ratchet over six frozen frames. 2 min 19 s. Two captures of the same code differ by 0.000% of pixels; a 9% exposure change fails the ratchet (0.8% of pixels) | `Research/modeling/`, `Research/baselines/` | `/model-verify` |
| G2 | P2 | Not deployed. `docs/` is empty; publishing is the user's explicit decision. Before any deploy: code files need the version stamp too (only data and shaders carry it), and GHSL/EDGAR/WRI/World Bank attributions must be visible on the live page (they are, in About) | `build/` | SCOPE §11 |
| G3 | P2 | First-frame budget not measured. SCOPE says ≤ 6 MB and ≤ 1.5 s; the boot set is about 8 MB plus 23 MB of relief and elevation behind it | `fields.boot` | SCOPE §11 |
| G4 | P3 | Performance is unmeasured: full-screen shader at 2× device pixels, re-run on every camera move | `main.js` cache | build notes |
| G5 | P3 | **Mostly RESOLVED 2026-11-09.** Driven with real pointer and key events at 1440 x 900: drag turns the globe, wheel zooms both ways, G, A, space, N, / and Esc do what About says, a typed search flies to the place and opens its card (globe and sheet), both time sliders move the clock. One fault found and fixed (the fly-to clamp). **Still not done:** panel scrolling at small window sizes; satellites picked out by eye | `ui.js`, `main.js` | this session |
| G6 | P3 | Headless Chromium under software GL loses its first WebGL context at boot nearly every time. The app now reloads itself (three tries) and the second boot renders; cause not investigated. A frozen frame takes about 18 s there | `main.js` | this session |

---

**Count: 34 items; 4 open at P1** (A1 and G1 delivered this round; A7, A8, G6 added). In order:

1. **B1 + A7** - cloud and vegetated land are now the whole of the visible distance from the photograph.
2. **C1** - sea ice from NSIDC's yearly grids. The overshoot is larger than kickoff said and is on the dashboard.
3. **A2** - streamed detail, so the 2 km floor is met by fields.
4. **F1** - label coverage: 21 of 204 states at the baseline sheet's framing.
