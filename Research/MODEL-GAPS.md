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

## APPLIED (build round, 2026-11-10)

Scope agreed for the round: clouds (B1), vegetated land (A7), sea ice (C1). Display values 0-255; EPIC
figures are means over eight frames, software GL, as `audit_all.py` holds them.

| measure | before | after | what changed |
|---|---|---|---|
| clear-sky land, mean abs. error (170,000 pixels stable over 9+ days) | 13.0 | 5.0 | Blue Marble decoded through a measured table, not as sRGB (A7) |
| the same, held-out: table fitted on 3 frames, scored on the other 3 | 11.6 | 6.2 | the table is not fitted to the frames it is scored on |
| mean brightness of the disc | 6.96 | 1.94 | exposure 0.43 to 0.70, gamma 1.914 to 1.63, fitted at physical anchors |
| contrast (std of luminance) | 3.47 | 1.98 | cloud tops now reach EPIC's 245; they stopped at 206 |
| bright-white fraction | 0.042 | 0.015 | cloud reflectance from the photograph, capped near 0.9 |
| disc profile, centre to cos 0.2, by channel (new measure) | 9.31 | 4.22 | haze screened by the air above it; cloud reflects more of a slanting beam |
| clear-ground colour, 6 regions, single days | 15.9 | 13.1 | albedo table; cumulus halved and spread to moderately wet land |
| glow outside the limb | 0.15 | 0.09 | |
| sun glint | 0.17 | 0.17 | wind spread added; see A3 |
| clear-ocean colour, darkest fifth of each frame | 4.6 | 4.9 | **worse by 0.3.** The 4.6 was reached by tuning water colour to this very measure; the ocean is now physical constants and reads 3 levels low in green |
| limb ring against centre (cos 0.1-0.2 / 0.8-1.0) | 0.063 | 0.103 | **worse. CANCELLATION**: see A1 |
| cloud brightness over ocean, largest gap at any percentile p5-p99.5 | 17 | 5 | `epic_cloud_cdf.py` |
| cloud brightness over land, the same | 32 | 20 | within 6 to the median; dim by 8-20 from p60 to p98 |
| sea-ice extent, largest monthly error, Arctic / Antarctic | 31.5% / 93.5% | 0.1% / 0.0% | rebuilt from NSIDC's 720 grids; **the match is by construction** (C1) |
| sea-ice conversion, each of 720 grids on its own, median / worst | - | 0.6% / 3.7% | the independent evidence for C1 |

**What was actually wrong (A7).** Three errors were holding each other up. (1) Blue Marble's values were
read as sRGB; they are close to linear in reflectance with a different gain per channel, so forest and
savanna were drawn at a third of their brightness. (2) Last round's exposure and gamma were fitted to
"desert, ocean and bright cloud", and two of those were the atlas's own guesses: the fit absorbed the bad
decode. (3) Cumulus was then sized to fill the gap the dark ground left. This round fitted the display
transform only to targets whose reflectance is known without the atlas (deep convective cloud 0.9; clear
ocean, computed), and the Libya-4 calibration site, **not used in the fit**, landed at (155, 127, 98)
against EPIC's (154, 130, 100).

**Honest answer against the standard in SCOPE section 8: close, with named exceptions.** Colour, exposure,
ocean, desert, vegetated land, the disc profile and the brightness distribution of cloud now sit within a
few display levels of the photograph. Not there: where the clouds are (not compared: a typical year against
one day), cloud shapes close in (edge detail and cumulus clumps are noise, B1), cloud over land above the
median (8-20 levels dim), the outermost 2% of the disc (10 levels bright), snow and ice at
a low Sun (A8).

Also shipped: lake ice kept from OISST and left out of the sea-ice count; drawn ice extended two cells to
the shore; a precision fault in the cloud drift that smeared cloud into vertical streaks at regional zoom;
`shader_model.py` (the light model in numpy, checked against the shader's own render before every use);
`epic_clearsky.py`, `epic_anchors.py`, `land_transfer.py`; the audit suite's tenth check (`clear-sky`).

**Tried and dropped, measured:** ozone absorption (physically 3% of a vertical green beam; EPIC's
green-to-red ratio is 1.04-1.06 from centre to edge, so the reference shows none, and drawing it turned the
limb lilac); the two-stream gain below a Sun height of 17 degrees (made the outer ring 14 levels bright).

---

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
| A1 | — | **DELIVERED 2026-11-09; recalibrated 2026-11-10.** Scored against eight EPIC frames; held by `audit_all.py` (check `epic`). **limb_err rose 0.063 to 0.103 and is classified CANCELLATION**: the verify-round frame matched the ring-to-centre ratio because its whole outer disc was 5-15 levels dim in every channel (`disc_err` 9.3 on the same renders). The disc is now within 3 levels per channel from the centre to cos 0.2 over all frames pooled; the ring at cos 0.1-0.2 is (85, 94, 100) against EPIC's (80, 84, 95). Open as A9 | `earth.frag.glsl`, `epic_compare.py` | SCOPE §8 |
| A2 | **P1** | **The zoom floor is not met by fields.** SCOPE asks for 2 km/px; shipped fields stop at 5 km (8192 px). Below that the picture is a magnified texture. Stream elevation (AWS terrain tiles, Web Mercator — needs a `frames` conversion and test) and imagery (NASA GIBS 500 m BMNG, EPSG:4326) into a focus window around the camera | new `detail.js`, two samplers in the shader | SCOPE §2 |
| A3 | P3 | **APPLIED 2026-11-09, corrected 2026-11-10.** The physical gain was right but the field holds the mean wind VECTOR, slower than the mean wind speed, so the glint was too narrow and 1.4 times too strong in scene terms (hidden by the old gamma). A 4.5 m/s spread is added in quadrature: four of five frames now within 0.22. Residual unchanged: in the December Americas frame the specular point lies against the Chilean coast, 1.03 against EPIC's 1.53. The 4.5 is one number for the whole ocean; a wind-speed climatology would replace it | `earth.frag.glsl` water block | EPIC |
| A4 | P2 | Relief shading is weak at regional zoom and there is no sub-grid detail grown from mechanism. Blocked on A2 for real slopes | `Earth.reliefK`, shader | visual review |
| A5 | P2 | **The water mask is Blue Marble's ocean fill, and it is wrong in shallow or turbid water.** Seen 2026-11-10: a band up to 150 km wide along south-west Hudson Bay and James Bay is classed as land, drawn in Blue Marble's water colour, and never ices; the Bahamas banks render as land colour. Fix: sea from ETOPO (below sea level and connected to the ocean), lakes from a lake dataset. Also still true: Baikal, Great Bear, Victoria are not in OISST's mask and the Caspian and Azov carry no ice in it, so they never freeze; the Great Lakes and Ladoga do (C1) | `fields_surface.step_water` | visual review |
| A6 | P3 | The Atlas style's permanent-ice test is a brightness-and-latitude heuristic; mountain glaciers and seasonal snow can be misread | `earth.frag.glsl` atlas block | build notes |

| A7 | — | **RESOLVED 2026-11-10.** Cause established with a clear-sky composite of about a hundred EPIC frames (`epic_clearsky.py`): Blue Marble read as sRGB understated dark land threefold, and the display transform had been fitted around it. Now a nine-knot table per channel (`ALB_LUT`), fitted by `land_transfer.py`; held-out error 11.6 to 6.2; table above. **What the table is not:** surface reflectance. It is the albedo that reproduces EPIC's view, straight back along the sunlight, where rough ground hides its shadows. Dense forest sits at 0.07-0.09 in the red where field measurements say 0.03: the stable-pixel test passes few rainforest pixels (424 in the darkest bin), so the darkest end of the red curve rests on little | `earth.frag.glsl` `albedoOf()`, `shader_model.py` | EPIC |
| A8 | P3 | Snow and ice at a low Sun read grey. Partly better 2026-11-10: white Blue Marble pixels are now given snow's albedo (0.90) by rule, since the picture clips there, and Antarctica in December reads white. Sea ice and winter snow at high latitude are still grey: the surface model is Lambert (plus a Lommel-Seeliger share for land) and snow scatters forward. Seen, not measured: the composite excludes latitudes above 60 | shader | EPIC |
| A9 | P3 | **The outermost ring of the disc is 5-10 levels too bright and too green** (cos 0.1-0.2: atlas 85, 94, 100; EPIC 80, 84, 95). Rayleigh scattering saturates there in the model as in a plane atmosphere; the real loss is probably ozone, which EPIC's product does not show elsewhere on the disc, so it was not added. Would need a spherical-shell treatment of the last 2% of the radius | shader air block | EPIC |

## B. Atmosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| B1 | **P1** | **Clouds: brightness now measured and close; shape and place are not.** `epic_cloud_cdf.py`, 2026-11-10: over open ocean the atlas is within 5 levels of EPIC at every percentile from p5 to p99.5 (it was up to 17 dim); over land within 6 to the median and 8-20 dim from p60 to p98. By 10-degree band over ocean (`--zonal`, measured before the recalibration) ten of twelve bands were within 10 levels, the worst 40-60 N at 17-19 dim: no case yet for replacing the cloud-fraction climatology, and a satellite climatology (ISCCP-H at NCEI is public) stays an option, not a need. Cloud reflectance is the photograph's brightness, capped near 0.9, with the two-stream rise at a low Sun. Cumulus over land: amount from rainfall and local solar time, now clumps 3-12 km across (it was single-pixel noise in streaks). Below the photograph's 5 km texel, cloud edges are broken up by noise. **Still wrong:** both of those are noise, not cloud physics (no streets along the wind, no shadows from cumulus); positions are a 2002 photograph carried on a monthly-mean wind; single-day ground medians in the Congo and Amazon are off by 6-22 levels in either direction | `cloudAt()`, `cumulusAt()` | interview |
| B2 | P2 | No independent witness for wind, temperature, pressure or precipitation. Score the shipped means against ERA5 monthly means (measure-against only) | new `Research/modeling/audit_climate.py` | SOURCE-SURVEY §5 |
| B3 | P2 | The daily temperature cycle is a three-parameter model with no check. Compare its range against a station or reanalysis diurnal-range climatology | `airTemp()` in shader and `cards.js` | SCOPE §4 |
| B4 | P3 | The lapse-rate correction is a constant 6.5 K/km; winter inversions over ice sheets and basins are wrong in sign | same | SOURCE-SURVEY |
| B5 | P3 | Cloud drift is sped up 2.5× and cloud shadows use an exaggerated height. Both are stated in About; neither is measured | `earth.frag.glsl` | About panel |

## C. Ocean

| # | P | item | touches | from |
|---|---|---|---|---|
| C1 | — | **RESOLVED 2026-11-10** for extent. The field is built from NSIDC's Sea Ice Index v4 monthly grids, all 720 of 1991-2020, through a tested polar-stereographic conversion (`frames.py`). Per cell: how often it was iced and its mean concentration; the typical-year edge is drawn so that the extent, counted as the dashboard counts it, equals NSIDC's mean of yearly extents. **So the 0.0% is by construction.** The evidence is the per-year check: each grid on its own reproduces NSIDC's cell count within 0.6% median, 3.7% worst. Findings: the median ice edge (iced in half the years) overshoots the mean extent by up to 13.8%, and no fixed threshold works (16-28% by month), which is why the edge is solved per month. Ice AREA is not solved: concentration inside the edge is the plain mean and runs up to 15.5% under NSIDC's area (Antarctic February). Lake ice kept from OISST, not counted. Not done: the month-to-month blend was not watched in motion; 8.9 M km² of OISST-valid cells the atlas draws as less than half water were not investigated | `fields_climate.step_ocean`, `REGISTER-ice.md` | NSIDC |
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
| G1 | — | **DELIVERED 2026-11-09; ten checks since 2026-11-10** (`clear-sky` added: the ground alone against the EPIC composite, and the audit's numpy copy of the shader against the shader). `audit_all.py`: frame tests, app math (now with eight EPIC sun positions), shader compile, audit selftests, sea ice, population, label coverage, EPIC, and the visual ratchet over six frozen frames. 2 min 19 s. Two captures of the same code differ by 0.000% of pixels; a 9% exposure change fails the ratchet (0.8% of pixels) | `Research/modeling/`, `Research/baselines/` | `/model-verify` |
| G2 | P2 | Not deployed. `docs/` is empty; publishing is the user's explicit decision. Before any deploy: code files need the version stamp too (only data and shaders carry it), and GHSL/EDGAR/WRI/World Bank attributions must be visible on the live page (they are, in About) | `build/` | SCOPE §11 |
| G3 | P2 | First-frame budget not measured. SCOPE says ≤ 6 MB and ≤ 1.5 s; the boot set is about 8 MB plus 23 MB of relief and elevation behind it | `fields.boot` | SCOPE §11 |
| G4 | P3 | Performance is unmeasured: full-screen shader at 2× device pixels, re-run on every camera move | `main.js` cache | build notes |
| G5 | P3 | **Mostly RESOLVED 2026-11-09.** Driven with real pointer and key events at 1440 x 900: drag turns the globe, wheel zooms both ways, G, A, space, N, / and Esc do what About says, a typed search flies to the place and opens its card (globe and sheet), both time sliders move the clock. One fault found and fixed (the fly-to clamp). **Still not done:** panel scrolling at small window sizes; satellites picked out by eye | `ui.js`, `main.js` | this session |
| G6 | P3 | Headless Chromium under software GL loses its first WebGL context at boot nearly every time. The app now reloads itself (three tries) and the second boot renders; cause not investigated. A frozen frame takes about 18 s there | `main.js` | this session |

---

**Count: 35 items; 3 open at P1** (A7 and C1 resolved 2026-11-10; A9 added; A5 raised to P2). In order:

1. **B1** - cloud shape and place. Brightness is now right; what a cloud looks like close in, and where it is, are not.
2. **A2** - streamed detail, so the 2 km floor is met by fields.
3. **F1** - label coverage: 21 of 204 states at the baseline sheet's framing.
