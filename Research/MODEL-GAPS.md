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

## APPLIED (third round, 2026-11-10)

Scope agreed for the round: cloud close in (B1), and insets, continent names and panels for the labels (F1).

**Clouds (B1): the fine structure is real cloud's now.** Closer than the cloud photograph resolves, the
atlas knew how much cloud there is and generated its shape from noise. It now takes the shape from three
VIIRS scenes at 2 km a pixel, one per kind of cloud (a Namibian stratocumulus sheet, shallow cumulus in the
southern Indian Ocean, a Southern Ocean storm), each reduced to an **ordering field**: every pixel's rank,
0 to 1, among its neighbours (`build/cloud_grain.py`, shipped as `fields/cloudgrain.jpg`, 1.4 MB). The
shader asks one thing of it: with a share p of this sky under cloud, is this pixel under it? Yes if its
rank is above 1 - p. Ranks are uniform by construction, so the cut covers p with no curve to measure. All
the noise-based drawing is gone (`worley`, `cutFor`, the clump and pavement generators).

| measure, close in (2 km a pixel, 15 VIIRS scenes, none of them a grain scene) | before | after |
|---|---|---|
| variance by wavelength, 4-256 km in six octaves | 0.621 | 0.226 |
| direction | 0.052 | 0.032 |
| cover (share brighter than reflectance 0.30) | 0.423 | 0.254 |
| contrast (std of reflectance) | 0.026 | **0.088, worse** |
| SE Pacific sheet: mean reflectance, atlas minus VIIRS | +0.129 | +0.063 |
| the same ground at 2 and at 8 km a pixel, mean reflectance | 0.00-0.01 apart | 0.005-0.022 apart (**worse**; Amazon +0.022: close in, clear gaps between pieces are not shaded by the cloud around them) |

Every scene, every measure (rule 7). Better: Congo, North Atlantic and SE Pacific on size spectrum,
direction and cover; trades on size spectrum (0.32 to 0.12, now inside the photographs' spread). The North
Atlantic and SE Pacific are now inside the day-to-day spread on spectrum, direction and contrast.
**Worse, six items:**

| item | before to after (floor) | class |
|---|---|---|
| Amazon, size spectrum | 0.38 to 0.53 (0.39) | **TRUE.** Real dry-season Amazon sky is fine cumulus everywhere, a third of the variance at 4-8 km; the grain's pieces there are fewer, larger and brighter. The old noise happened to have the right sizes |
| Amazon, contrast | 0.001 to 0.054 (0.022) | **TRUE**, same cause |
| trades, contrast | 0.007 to 0.055 (0.031) | **TRUE**: the brightest tenth of the scene is 0.45 where VIIRS has 0.23 |
| trades, direction | 0.03 to 0.06 (0.03) | **TRUE**: cumulus no longer lines up along the wind; the grain has its own direction |
| trades, cover | 0.03 to 0.05 (0.04) | **TRUE**, small |
| Congo, contrast | 0.041 to 0.069 (0.038) | **PRE-EXISTING**: the scene carries 0.14 too much light in both states (ISCCP's April mean against three 2024 afternoons); resolved pieces show it where flat grey ones hid it |

The contrast baseline is re-set backwards with this table as its reason. Two attempts to fix the Amazon and
trades items were made and withdrawn because NASA EPIC said no: spreading cumulus evenly (EPIC's darkest
fifth of ocean came out 3 levels too bright) and spreading daytime land cloud evenly (disc contrast error
1.5 to 2.4).

**Three things found on the way, each fixed at its cause.**

- *How bright a piece of cloud is, was a guess.* Measured on 18 scenes of 2023 (not the audit's): the cloudy
  part of a broken field has a mean reflectance of 0.35 (sheets), 0.33 (cumulus), 0.45 (storm cloud), and a
  spread of 0.34-0.53 of that mean. So cloud covers a / m0 of the sky and brightens from edge to core as the
  rank does. The first cut drew flat white pieces at 1.6 times the mean and scored half again the
  photographs' contrast.
- *Sheet cloud was a third brighter than ISCCP says.* The shader had its own by-eye law for sheet light
  (0.37 off Peru where ISCCP's sheet light is 0.25). It is now ISCCP's: share times 0.50.
- *The Sun-side brightening and the slant term were applied to each resolved piece.* Both are statements
  about a field of cloud; applied per piece they weakened as detail appeared, so the same sky dimmed as
  it was drawn finer. The gain is now worked out on the far view's light and given to what is drawn.

**The EPIC audit's instrument was changed, and here are both steps.** `to_common()` shrank both pictures
2.3 times by reading single points and averaged display values; it now averages light over each common
pixel (selftest: fine stripes come out as the grey that sends back half the light). The same renders as the
last baseline, re-scored, then this round:

| whole disc (EPIC, eight frames) | last baseline | same renders, new instrument | this round |
|---|---|---|---|
| mean brightness | 2.47 | 2.63 | 2.66 |
| contrast | 1.59 | 1.68 | 1.54 |
| bright-white fraction | 0.018 | 0.021 | **0.027** |
| disc profile | 4.12 | 4.17 | 4.13 |
| limb ring | 0.107 | 0.105 | **0.118** |
| clear-ocean colour | 5.1 | 5.7 | 5.0 |
| clear-ground colour | 13.8 | 13.1 | 13.2 |
| halo | 0.09 | 0.20 | 0.20 |
| sun glint | 0.08 | 0.11 | 0.13 |

White fraction and limb ring are TRUE regressions, small: with sheet light at ISCCP's figure the two
December frames, already 2-6 points short of EPIC's white share (22%), are a point or two shorter. The old
excess was covering for a shortfall of bright cloud over the summer Southern Ocean, which is now open in B1.

**Honest answer on cloud close in: it reads as a satellite photograph of cloud now**, on the Mac's own GPU
as well as in the headless frames (pairs: `Research/figures/clouds/*_b6.jpg` before, `*_g8.jpg` after).
What it is not: the right cloud for the place. One real sheet stands in for every sheet and one real storm
for every storm, repeating every 2048 km in two arrangements; the Amazon and the trades are wrong in the
ways the table says; there are no towers, and no shadows thrown to one side.

**Labels (F1): two insets, the continents, and nothing under a panel.** Built by a subagent and checked
independently here (the label audit and its selftest re-run; frames read).

| whole-Earth sheet, 1440 x 900 | before | after |
|---|---|---|
| states named where a reader can see them | 106 of 176 in view | 125 of 177 (107 on the map, 18 only in an inset) |
| the old count (a name under a panel counts) | 129 of 198 | 107 on the map; 125 with the insets |
| Europe | 15 of 45 | 29 of 45 |
| names under panels, all 24 framings | 1222 (31 on the sheet) | 0 |
| overlapping, under 9 px, on the wrong country, wrong card | 0, 0, 0, 0 | 0, 0, 0, 0 |
| names lost on zooming in 10% | 5 | 4 |
| older labels failing the on-own-ground test | 18 | 3 |

**The release notes for 1.0 said 129 states named. Twenty-two of those were under the dashboard.** The count
now leaves out what cannot be read, and a state whose own ground is under a panel is `hidden`, not unnamed.
Old and new numbers do not compare; `audit_all.py` says so beside the baseline. State by state over the 24
framings: 109 gained a name, 10 lost one; nine of the ten sat within 4 px of a panel or in the sliver between
a panel and the window's edge (correct to drop), and the tenth is Benin on one globe framing, whose place
Togo took (RESOLUTION-LIMITED: one of the two fits).

- **An inset is a second view, not a picture**: the earth shader run through its own camera into its own
  target, borders and rivers through the same camera, names placed by the same `Labels` machinery, and clicks
  routed to it (`web/js/insets.js`, `main.js` `layoutInsets` / `viewAt`). Europe (13.6-26.9 E, 40.4-60 N) sits
  in the south-east Pacific at 3.0 times; the Lesser Antilles in the southern Indian Ocean at 3.2 times. Each
  takes whatever open sea is left between the panels and is not drawn if that is too little (at 1100 x 700,
  neither is). They fade out between 15.5 and 12.5 km a pixel, where the main map names 12 and then 18 of the
  Europe inset's states itself. Never on the globe.
- **Continent names**: wide quiet capitals, one rectangle a letter, placed last and painted under everything.
- **Panels**: their rectangles are read from the page every tick and are taken ground for names and insets.
- The audit counts inset names, finds the ground under each through the inset's own camera, clicks every
  inset name and a 7 x 7 grid of inset ground, and holds a fifth zero check, `under_panel`. 23 planted faults.

**Not done, and why.** Sixteen European states are still unnamed on the sheet (AND BEL BIH CHE DNK KOS LIE
LUX MCO MDA MKD MLT MNE SMR SVN VAT): the western Balkans need 6 km a pixel and the largest clear sea between
the panels gives 8.6. The Levant and the Caucasus have no inset: the frame would have to reach 50 E. The
Europe frame covers Easter Island (no sample point of its 2268 falls on land). Tracers and aircraft are not
drawn inside insets. "PACIFIC OCEAN" no longer appears at 1440 x 900 (both its positions are under panels).
ASIA lies across Arabia to India because Natural Earth files all of Russia under Europe. Not verified: the
fade on the Mac's own GPU, windows larger than 1440 x 900, dragging by hand.

---

## APPLIED (second build round, 2026-11-10)

Scope agreed for the round: cloud shape and place (B1), the zoom floor (A2), labels (F1).

**Clouds (B1).** A new reference, because EPIC resolves 10 km and cannot judge cloud at the 2 km floor:
fifteen VIIRS scenes at 2 km a pixel, five regimes by three days (`cloud_texture.py`). Each number below
is how far the atlas sits OUTSIDE the day-to-day spread of the photographs, summed over the five regimes;
0 would mean indistinguishable by that measure.

| measure, close in (2 km a pixel) | before | after | what changed |
|---|---|---|---|
| direction (how one-directional the 4-32 km structure is) | 0.453 | 0.052 | generated texture moved onto the sphere; flow cycle 30 h to 18 h |
| contrast (std of reflectance) | 0.078 | 0.026 | cloud light from ISCCP optical thickness, not from cloud amount |
| cover (share brighter than reflectance 0.30) | 0.558 | 0.423 | stratocumulus decks exist now; thin cloud drawn broken |
| variance by wavelength, 4-256 km in six octaves | 1.005 | 0.621 | sub-10 km structure generated; Amazon and SE Pacific inside the floor |
| mean reflectance at the five scenes, atlas minus VIIRS | +0.06 to +0.18 | 0.00 to +0.08 | **with no tuning**: ISCCP and VIIRS agree through the atlas |

| measure, whole disc (EPIC, eight frames) | before | after | |
|---|---|---|---|
| mean brightness | 1.94 | 2.47 | **worse by 0.5** |
| contrast | 1.98 | 1.59 | |
| bright-white fraction | 0.015 | 0.018 | worse by 0.003 |
| disc profile | 4.22 | 4.12 | |
| limb ring | 0.103 | 0.107 | worse by 0.004 |
| clear-ocean colour | 4.9 | 5.1 | worse by 0.2 |
| clear-ground colour, single days | 13.1 | 13.8 | **worse by 0.7** |
| sun glint | 0.17 | 0.08 | |
| cloud brightness over ocean, worst percentile | 5 | 7 | worse |

**The whole-disc regressions are accepted, and here is the trade.** Last round the cloud opacity curve was
fitted directly to EPIC's brightness distribution; it matched within 5 levels because it was made to. That
curve is gone. Cloud light now comes from a field that knows nothing of EPIC (ISCCP amount times the
reflectance of its optical thickness), checked by a second instrument that knows nothing of either (VIIRS),
with two fitted numbers left: how fast gaps close at a slant (0.5) and how much brighter broken cloud reads
from the Sun's side (0.50). EPIC agreement fell from "fitted" to "within 7 levels at every percentile, mean
brightness within 2.5". Classified TRUE regressions, small, exchanged for a cloud field that is right by two
independent measures at nadir. Baselines re-set with this note.

**What changed in the model.** Three kinds of cloud, each drawn its own way, each placed by ISCCP:
stratocumulus sheets as a generated pavement of closed and open cells (the SE Pacific, Namibian and
Californian decks were all but absent: the reanalysis cloud field had 16% bright cloud off Peru against
VIIRS's 45%); thin broken low cloud as generated clumps drawn out along the wind; and everything else as
the photograph, which now carries shape only (divided by its own 1200 km mean) while ISCCP carries amount.
Closer than 5 km a pixel, middling cloud is drawn as solid pieces with clear air between, not as a veil.
Zoom is conservative: the same ground returns the same light at 2 and at 8 km a pixel (0.00-0.01 apart
in all five scenes).

**Honest answer on cloud close in: better by every number, and it still reads as generated.** Read the
pairs (`Research/figures/clouds/*_b0.jpg` before, `*_b6.jpg` after). Decks are a pebbled mosaic, greyer
than the real thing; fronts have no fine structure (the North Atlantic scene is a lumpy field where VIIRS
shows one clean band and clear sea); there are no convective towers, no streets you would notice, no
river-breeze clearings. Three intermediate versions scored better than their predecessors and looked like
pepper, cracked mud and paint chips. Where a cloud is remains uncompared.

---

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
| A2 | — | **DELIVERED 2026-11-10.** Closer in than 5 km a pixel the page streams Blue Marble (NASA GIBS, 1-2 km) and terrain tiles (AWS Terrain Tiles, about 2 km) into a focus window (`detail.js`); the shader adds the picture's fine structure to the month's shipped colour and takes height and slope from the tiles on land. Measured: streamed land against shipped land, rms 10-25 m with no shift (0.01-0.03 km) in four mountain regions; a half-cell slide would read 109-172 m. 86-127 requests and 3-7 MB per window, 2-3.6 s to ready. Seen on the Mac's own GPU at the Himalaya: ridges, valleys, lakes and rivers resolve and stay registered. **Limits:** at 2 km a pixel the elevation texel is 1.7-2.3 km, coarser than the 1.6 km the rule asks (holding the whole globe view at the wanted level would take 135-150 tiles; the budget is 96), and at 3 km a pixel the finer fields cover only the middle of three of five test views; the tiles' sea floor is ETOPO1 and sits 1-4 km off the shipped ETOPO 2022, so it is not used; the streamed picture is August, so half-snowy pixels take August's pattern; nothing is streamed with a pole on screen; compositing runs on the main thread (up to 190 ms a window). **Before publishing:** the Terrain Tiles documentation carries the line "The S3 tiles are meant for efficient networking with EC2 resources only" (from Mapzen's hosted-service days; the bucket is in the AWS open-data registry today) and requires an eleven-line attribution, which is in About. The owner should read both before the page goes public | `web/js/detail.js`, shader focus-window block | SCOPE §2 |
| A3 | P3 | **APPLIED 2026-11-09, corrected 2026-11-10.** The field holds the mean wind VECTOR, slower than the mean wind speed, so the glint was too narrow; a 4.5 m/s spread is added in quadrature. After the cloud rework (less cloud over the specular point in the December Americas frame) all five frames are within 0.22 and the mean error is 0.08. The 4.5 is one number for the whole ocean | `earth.frag.glsl` water block | EPIC |
| A4 | P2 | Relief shading at regional zoom now uses real 2 km slopes on land where the detail layer is on (A2). Still open: no sub-grid detail grown from mechanism, and the sea floor shades from the shipped 5 km slope field | `Earth.reliefK`, shader | visual review |
| A5 | P2 | **The water mask is Blue Marble's ocean fill, and it is wrong in shallow or turbid water.** Seen 2026-11-10: a band up to 150 km wide along south-west Hudson Bay and James Bay is classed as land, drawn in Blue Marble's water colour, and never ices; the Bahamas banks render as land colour. Fix: sea from ETOPO (below sea level and connected to the ocean), lakes from a lake dataset. Also still true: Baikal, Great Bear, Victoria are not in OISST's mask and the Caspian and Azov carry no ice in it, so they never freeze; the Great Lakes and Ladoga do (C1) | `fields_surface.step_water` | visual review |
| A6 | P3 | The Atlas style's permanent-ice test is a brightness-and-latitude heuristic; mountain glaciers and seasonal snow can be misread | `earth.frag.glsl` atlas block | build notes |

| A7 | — | **RESOLVED 2026-11-10.** Cause established with a clear-sky composite of about a hundred EPIC frames (`epic_clearsky.py`): Blue Marble read as sRGB understated dark land threefold, and the display transform had been fitted around it. Now a nine-knot table per channel (`ALB_LUT`), fitted by `land_transfer.py`; held-out error 11.6 to 6.2; table above. **What the table is not:** surface reflectance. It is the albedo that reproduces EPIC's view, straight back along the sunlight, where rough ground hides its shadows. Dense forest sits at 0.07-0.09 in the red where field measurements say 0.03: the stable-pixel test passes few rainforest pixels (424 in the darkest bin), so the darkest end of the red curve rests on little | `earth.frag.glsl` `albedoOf()`, `shader_model.py` | EPIC |
| A8 | P3 | Snow and ice at a low Sun read grey. Partly better 2026-11-10: white Blue Marble pixels are now given snow's albedo (0.90) by rule, since the picture clips there, and Antarctica in December reads white. Sea ice and winter snow at high latitude are still grey: the surface model is Lambert (plus a Lommel-Seeliger share for land) and snow scatters forward. Seen, not measured: the composite excludes latitudes above 60 | shader | EPIC |
| A9 | P3 | **The outermost ring of the disc is 5-10 levels too bright and too green** (cos 0.1-0.2: atlas 85, 94, 100; EPIC 80, 84, 95). Rayleigh scattering saturates there in the model as in a plane atmosphere; the real loss is probably ozone, which EPIC's product does not show elsewhere on the disc, so it was not added. Would need a spherical-shell treatment of the last 2% of the radius | shader air block | EPIC |

## B. Atmosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| B1 | P2 | **Clouds: amount and brightness from observation; fine structure from real cloud since 2026-11-10 (third round).** Three kinds (photograph for fronts and storms, sheets, broken low cloud), amount and light from ISCCP (2007-2016), and closer than 10 km a pixel the shape is cut from three VIIRS scenes' ordering fields (`build/cloud_grain.py`), scored against fifteen other VIIRS scenes (`cloud_texture.py`; tables in APPLIED). Open, in order of what the pairs and the numbers show: (1) the Amazon in the dry season is fine cumulus everywhere and the atlas draws fewer, larger, brighter pieces (size spectrum 0.53 against a floor of 0.39); a fourth grain of continental cumulus would answer it, and there is no free texture channel (uClouds is R photograph + GBA grain; unit count is 16 of 16); (2) the trades' brightest tenth is 0.45 against 0.23, and cumulus no longer lines up along the wind; (3) Congo carries 0.14 too much light and twice the bright cover (0.47 against 0.22): ISCCP's April mean against three afternoons, and no daily cycle in the photograph regime; (4) bright cloud over the summer Southern Ocean is short in EPIC's December frames (white share 15-18% against 22%); (5) one scene stands for each kind everywhere and repeats every 2048 km; (6) no towers, no cloud shadows at an offset, no clearings along rivers and coasts; (7) sheet share under a fifth of the sky is not drawn; (8) positions are still one 2002 photograph carried on a monthly-mean wind; (9) the Sun-side brightening is pinned at two angles only; (10) between 4 and 11 km a pixel the grain fades into the 10 km photograph and the view is soft; (11) ISCCP shows a faint ring at the GOES-West sub-satellite point | `cloudAt()`, `pieces()`, `grainAt()`, `deckAt()`, `cumulusAt()`, `build/cloud_grain.py` | interview |
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
| F1 | P3 | **DELIVERED 2026-11-10 (placement, second round; insets, continents and panels, third round).** A real placement pass in `overlays.Labels`: exact collisions, names inside their state, beside it, abbreviated, or in open water on a leader; continent names in spaced capitals; nothing under a panel; and on the whole-Earth sheet a Europe inset and a Lesser Antilles inset, each a second rendered view with its own names and clicks (`web/js/insets.js`). On the sheet at 1440 x 900, **125 of the 177 states in view are named (106 before, counted the same way)**; Europe 29 of 45. Held by `audit_labels.py` on 24 framings and both insets, five checks at zero. Open: sixteen European states still unnamed on the sheet (the western Balkans need 6 km a pixel; the clear sea gives 8.6), no inset for the Levant and Caucasus, the Europe frame covers Easter Island, tracers are not drawn in insets, PACIFIC OCEAN is lost under the panels at 1440 x 900, ASIA sits too far south-west, Łódź is the one city in the Europe inset, 4 names drop when zooming in 10%, 3 older labels fail the on-own-ground test, the fade is unverified on a real GPU | `overlays.Labels`, `web/js/insets.js`, `main.js`, `data.labelItems` | SCOPE §8 |
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
| G2 | — | **DELIVERED 2026-11-10: published.** `build/build_site.py` builds `docs/` from `web/`: audits first, both stamps written before anything is copied, every module import and the stylesheet stamped (41 URLs), development-only files left out; checked booting under a sub-path with no unstamped script and no failed request. An in-app update log (`data/updatelog.json`, shown in About). Open: the AWS tile documentation line recorded under A2 was read and accepted by the owner for this release; attribution for GHSL, EDGAR, WRI, World Bank, GIBS and the terrain tiles is in About | `build/build_site.py`, `docs/` | SCOPE §11 |
| G3 | P2 | First-frame budget not measured. SCOPE says ≤ 6 MB and ≤ 1.5 s; the boot set is about 8 MB plus 23 MB of relief and elevation behind it | `fields.boot` | SCOPE §11 |
| G4 | P3 | Performance is unmeasured: full-screen shader at 2× device pixels, re-run on every camera move | `main.js` cache | build notes |
| G5 | P3 | **Mostly RESOLVED 2026-11-09.** Driven with real pointer and key events at 1440 x 900: drag turns the globe, wheel zooms both ways, G, A, space, N, / and Esc do what About says, a typed search flies to the place and opens its card (globe and sheet), both time sliders move the clock. One fault found and fixed (the fly-to clamp). **Still not done:** panel scrolling at small window sizes; satellites picked out by eye | `ui.js`, `main.js` | this session |
| G6 | P3 | Headless Chromium under software GL loses its first WebGL context at boot nearly every time. The app now reloads itself (three tries) and the second boot renders; cause not investigated. A frozen frame takes about 18 s there | `main.js` | this session |
| G7 | P2 | **The earth shader uses all 16 texture units WebGL2 guarantees.** A seventeenth linked under the audits' software GL (limit 32) and gave a black page on the Mac's own GPU; caught by the streaming work, fixed by folding the cloud-kind atlas into the atmoB array, guarded now by `check_shaders.py`. The next field that needs a sampler must share one. And the audit suite still never runs on a real GPU: a check through the browser pane or ANGLE Metal headless would close that | `fields.js` UNIT, `check_shaders.py` | this session |

---

**Count: 36 items; none open at P1** (B1 to P2 and F1 to P3 after the third round, 2026-11-10). In order:

1. **A5** - the water mask from bathymetry (south-west Hudson Bay is "land"), then lake ice.
2. **B1** - a continental-cumulus grain for the Amazon; bright cloud over the summer Southern Ocean; a daily cycle for convective cloud over land.
3. **G7** - run one audit on a real GPU.
4. **F2** - population by polygon.
5. **F1** - the sixteen European states the sheet still cannot name; an inset for the Levant and Caucasus.
