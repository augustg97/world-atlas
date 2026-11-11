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

## APPLIED (seventh round, 2026-11-11)

Scope, the owner's: Sentinel-2 cloudless (EOX, CC BY 4.0) as a streamed source for ground finer than 0.5 km (A11).
The host was approved by the owner before any of it was written.

**The source.** `tiles.maps.eox.at`, WMTS layer `s2cloudless` (the 2016 mosaic: the one edition under CC BY 4.0;
2018 onward are non-commercial), tile matrix set `WGS84`: the atlas's own equirectangular frame, 256 px tiles,
level 13 = 9.5 m. CORS open. EOX asks for its attribution on the map: it is shown in the HUD, with a link,
whenever those tiles are on screen, and in About.

**The planner** (`detail.planDetail`). A wanted texel finer than 0.45 km goes to Sentinel-2 at the coarsest level
that meets it, within 120 tiles; if that does not fit, one level coarser; if its coarsest useful level (8,
0.31 km) does not fit, Blue Marble's last level. Terrain zoom to 12 (32 m). Tested at 0.4, 0.2, 0.1, 0.05 km a
pixel and at 62 N (`test_app_math.mjs`): levels 8, 9, 10, 11; 72 to 85 tiles.
**The zoom floor** went from 0.35 km to 20 m a pixel (10 m a device pixel at 2x: the mosaic's own). Looked at
there for wobble in the ray-cast (float32 resolves 2.4 m of longitude): none seen.

**Joining another camera's picture to the shipped month** took three tries, each looked at:
1. *Added*, as Blue Marble's fine structure is. Sentinel-2 has more contrast: beside the Nile delta its sand went
   past full scale and its fields below zero, and the clamp drew a lime desert and blue-black fields.
2. *By ratio at one coarse scale* (39 km). Hue kept, coast sharp, but one tint for a screen that holds two
   kinds of ground turned the desert olive.
3. *By ratio at the shipped 5 km inland, and coarser (10 to 39 km) only within reach of water* (the shipped water
   fraction), where it carries brightness only: the shipped sea is one dark navy fill, and a colour ratio across
   land and that fill turned Manhattan olive. The desert is the far view's tan, the delta green, the harbour's
   coast the picture's own. **Used.** Left over: a strip of coastal land tinted differently from the land behind
   it; a faint halo where very different grounds meet; a yellow cast on pale roofs near water (A12, A13).

**Three faults found by looking at the first frames, all older than this round or exposed by it:**
- *The terrain tiles carry bad heights*: one texel 1,895 m below Manhattan, 679 in one window along the piers.
  At 30 m a texel each was a black pit. `detail.despike` takes out any texel further than 40 m (at 30 m; more at
  coarser texels) from the median of its eight neighbours; a 45 degree ridge is untouched (tested). Slopes for
  shading are also taken over at least 90 m.
- *The planner could miss a view for good.* `viewBox` used the camera's cached basis, which after a camera
  change that no label pass had seen was the previous view's: a pole "on screen", the whole Earth as the box, no
  plan, and the planner plans once per view. It showed after a fast zoom to the new floor. `viewBox` now takes
  the basis itself. Present since the first streamed window; never seen because a wheel zoom relabels first.
- *A city's resolved light was a sepia photograph of the day*, rivers lit. The pattern is now the ground's
  relative brightness squared, with ordinary ground at under half: water and parks go dark.

**Three declared departures from the real view, all close in, all stated in their cards:**
- *Cloud thins and goes* between 0.7 and 0.15 km a device pixel. Its finest structure is 2 km; over streets drawn
  to 40 m it was a white slab.
- *Exposure rises*, up to 1.7 times, where the cloud is gone and the shipped ground is not itself bright. The
  whole-disc exposure leaves a city at a tenth of full scale. By eye.
- *City light takes the ground's pattern* below about 300 m a pixel: Black Marble's amount, times the daytime
  picture's brightness against its surroundings. This is what F11 lacked: a metropolis at night now has streets.
  The amount is measured; the pattern is MODELLED (a pale roof is not always a lit one).

**Not measured.** Nothing scores the close-in picture: there is no reference at that scale in the repository,
and the frozen frames do not reach it (it needs the network). Checked by eye at Los Angeles and its port, Paris,
Cairo (globe and sheet) and the Valais in January, by day and by night. Recorded as G8.

**Regression gate.** Fourteen checks pass; no baseline moved; the six frames are unchanged (the largest
difference 0.049% of pixels).

## APPLIED (sixth round, 2026-11-10)

Scope, the owner's: the real-GPU audit (G7), wide rivers (A10), finer ground and readable cities close in, the
box of tracers left behind by a quick zoom out, and quieter aircraft.

**Rivers (A10).** `fields_surface.rivers8`: NASA's MODIS land-water mask (MOD44W through GIBS, 610 m), taken only
where Natural Earth has land and only the connected bodies a Natural Earth 1:10m river centreline runs through.
`audit_water.py` gained a river check: nine reaches several kilometres wide, found by name on the centrelines,
walked every 2 km.

| reach | drawn as water, before | after |
|---|---|---|
| Amazon, Manaus to Almeirim | 4% | 99% |
| Negro, lower | 0% | 93% |
| Tapajos, lower | 0% | 99% |
| Congo, Mbandaka to Kinshasa | 0% | 71% |
| Ob, lower | 0% | 99% |
| Yenisei, lower | 0% | 95% |
| Lena, lower | 0% | 99% |
| Parana, lower | 0% | 50% |
| Brahmaputra, Assam | 0% | 75% |
| mean share NOT drawn (`rivers_undrawn`) | 0.996 | 0.131 |

Narrow rivers stay lines, as they should at 5 km: Mississippi 3%, Danube 2%, Yangtze above the estuary 14%.
The check shows the rivers arrived on screen; it is not independent of MODIS (no river-width dataset is in hand).
*Found on the way:* the lakes strung along river lines came with the rivers, 0.87 million km2 of inland water in
all, and that moved every region toward HydroLAKES's lake areas, which nothing had compared before:

| inland water, M km2 | before | after | HydroLAKES, lakes alone |
|---|---|---|---|
| Canada | 0.404 | 0.759 | 0.656 |
| Siberia | 0.117 | 0.249 | 0.192 |
| Scandinavia and Finland | 0.115 | 0.128 | 0.124 |
| United States | 0.301 | 0.342 | 0.347 |
| Amazon basin | 0.012 | 0.080 | 0.021 |
| Tibet | 0.022 | 0.024 | 0.032 |

Canada is now ABOVE the lake inventory by more than its rivers account for: the mask is the larger of three
sources cell by cell, which over-counts part-water cells. Open under A10.
Lake ice at the recorded lakes that are themselves water: 25 lakes (23), 11.6 days a year out (12.7). The Ob,
Yenisei and Lena freeze, by the lake model at 7 m (C5).
*Instrument fault found:* "water connected to the ocean" ran up the Amazon once it was water, and the audit scored
the whole river as land drawn as sea (0.568 -> 0.614). The audit's sea is now what connects without the rivers.

**Close in.** The window planner asked for nothing finer than 1 km; it now asks for 0.45 km, which is GIBS level
7 of Blue Marble (0.49 km) and terrain zoom 9 (0.25 to 0.3 km), from the zoom floor to 1.2 km a pixel.
Night lights are streamed on the same tiles (layer VIIRS_Black_Marble, the shipped field's own source at 500 m)
while part of the view is dark, and ride in the imagery texture's alpha: there is no seventeenth sampler.
*Measured:* the streamed value read back at `NIGHT_SHIPPED` agrees with the shipped rule to 0.6% in the mean and
0.02 on lit pixels over Los Angeles and its desert.
*Negative result:* the inside of a large city has no structure in any 500 m night product GIBS serves. Black
Marble 2016, VIIRS_Night_Lights and the gap-filled daily radiance are all at full scale across the Los Angeles
basin (median 255). The curve close in therefore tops out at pale gold, not white, so edges and names read (F11).
*Declared exaggeration:* nearer than about 5 km a pixel the night ground is lifted to about ten times moonlight
and shaded from the north-west. Stated in the Night lights card. Seen whole the night is unchanged
(the two night frames of the baseline did not move).

**Tracers.** A tracer is spread evenly over the screen at the scale it was spawned at. After a zoom out by r the
old view held r x r too many and they stayed, a dense box, until each died of age (up to 300 frames). Each now
remembers its scale: on a camera move, one off screen is respawned at once and all but one in r x r fade in
eight frames (`particles.FlowTracers._recast`). A still camera changes nothing, so frozen frames are the same.

**Aircraft.** Each plane was a 9 px cream streak at 70% opacity, strongest close in. Now a thread in four pieces
fading behind the head (62% to 5%, 0.5 px to hairline), shorter from far off, fainter close in. By eye; the
count aloft is the model's and unchanged.

**The real-GPU audit (G7).** `audit_gpu.py`, fourteenth check: headless Chromium reaches the Mac's GPU with
`--use-angle=metal` (16 texture units, against SwiftShader's 32). The six canonical frames drawn there against
the accepted software frames:

| frame | mean difference, levels of 255 | pixels more than 24 levels apart |
|---|---|---|
| globe-default | 0.18 | 0.03% |
| globe-night-asia | 0.14 | 0.04% |
| globe-motion-atlantic | 0.48 | 0.14% |
| region-himalaya | 0.28 | 0.20% |
| sheet-atlas | 0.73 | 0.59% |
| sheet-lens-temp | 0.33 | 0.05% |

and the lights-into-alpha write, which no frame reaches: worst error 0.4 of 255, colour untouched, GL state put
back. It cannot run without a GPU and exits 3 saying so.

**Regression gate.** Fourteen checks pass. Three frames re-accepted with reasons (tracers reshuffled by the
rebuilt lane field; rivers in two). Baselines tightened: water sea-as-land 0.309 -> 0.287, lake ice drawn
12.7 -> 11.6 days, cloud-texture sizes 0.152 -> 0.122 (rivers in the forest scenes; within that audit's known
layout noise). **One baseline re-set backwards, 0.7 -> 0.8: the clear-sky land bias. Class: the instrument's
population, not the picture.** That audit sorts pixels into land and water by the mask this round changed;
825 part-water pixels of 168,716 left its land set. The same renders scored with the old mask give 0.7.

## APPLIED (fifth round, 2026-11-10)

Scope agreed for the round: lake depth in the lake-ice model (C4), and the Amazon's cloud (B1).

**Lake depth.** Measured first: the fixed-lag model's error went with the logarithm of a lake's recorded mean
depth at r = 0.76 (102 lakes), and with its area at 0.23. Lakes under 6 m were iced 9 days too few, lakes over
25 m about 50 too many. The freeze-up lag is now 10 x depth^0.7 days, to 160 (`build/lakeice.py`; the two
numbers and the melt rate fitted on the 48 lakes of the fitting half whose depth is recorded; the 160 set on
the 8 lakes deeper than 25 m, both halves).

| lake ice against the lakes' own records | release 1.2 | now |
|---|---|---|
| the model on 83 lakes it was not fitted to, days a year | 10.9 | 9.8 |
| the same, the 54 of them whose depth is recorded | 10.3 | 9.0 |
| mean error by depth: under 6 m, 6-12, 12-25, over 25 m | -9, 0, +13, +50 | +4, +4, -1, -1 |
| what is DRAWN, at the 23 lakes that are themselves water in the mask | 17.2 | 12.7 |
| Lake Constance (record: 0 days) | 57 | 6 |
| Lake Vattern (13) | 55 | 13 |
| Baikal, southern station (102) | - | 106 |
| Lake Mjosa (50) | 150 | **135** |

Where the depth comes from, and three things that went wrong on the way:

- **HydroLAKES** (CC BY 4.0, a new build-time source: `fetch_sources.py hydrolakes`, 79 MB; nothing of it
  ships but the ice it helps compute; credited in About). Each body of inland water in the atlas's mask takes
  the depth of the HydroLAKES lake whose outlet lies on or near it and whose area is nearest its own.
  *The outlet is not on the lake as the mask draws it*: Superior's is 20 km past the last water pixel and
  Constance's is on the Untersee, 50 km from the main basin; matching within 10 km left Superior, Baikal,
  Great Slave and Onega without a depth. A second pass reaches 60-200 km for lakes over 50 km2.
- **Most HydroLAKES depths are predictions, not measurements** (its `Vol_src` 3: from the slope of the land).
  Against 60 recorded depths they correlate at 0.39 and run two to three times too deep in Finland; taken at
  face value they made the drawn lakes WORSE (17.2 to 18.7 days). Dropping them lost Mjosa, whose prediction
  is roughly right. They are used through their regression (ln depth = 0.94 + 0.46 ln predicted), which is
  how a noisy predictor should be used. Measured depths (every lake over 500 km2) are taken as they stand.
- **Great lakes take the floor itself.** Where ETOPO carries a lake's floor (the Caspian, Baikal, the Great
  Lakes, the Black Sea), depth is local: the north Caspian is 3 m and freezes 66 days, its middle 560 m and
  does not. The lake's surface is the 2nd percentile of the land touching it; two first tries (the lowest
  land near each cell; the lowest pixel touching the body) read hills as water at Issyk-Kul and put the
  Black Sea's shore at -230 m.
- **The audit was scoring the wrong lake.** "What the atlas draws" took every recorded lake in a cell with
  ice; but a cell's ice is the ice of whatever body the mask has there, and for a pond beside Lake Ontario
  that is Lake Ontario. With one lag for all lakes it did not matter. It now scores a lake only if the mask
  has a body within a pixel of it whose area is within a factor of four of the lake's own: 23 lakes. Earlier
  "drawn" numbers (16 days at 106 lakes) do not compare; on the 23, release 1.1 was 120 days out.

Still wrong: Mjosa 135 days against 50 (its depth is a prediction: 80 m, shrunk to 19; it is 153). Issyk-Kul,
which is not in the record and does not freeze, 53 days (the air it is given is 10 C below freezing in
January, colder than its shore, and it is salt). A great lake freezes whole or not at all, cell by cell.

**The Amazon's cloud.** Two changes, and the texture now holds two rows of grain tiles to carry them.

- *A fourth grain: cumulus over land* (`cloudgrain2.jpg`; a dry-season afternoon over the Rio Negro forest,
  27 August 2023; only what is white counts, so a silty river is not cloud). By itself it moved little: the
  Amazon scene's size spectrum 0.53 to 0.50.
- *The cause was the partition of light, not the grain.* VIIRS shows the Amazon at 13:30 as small cumulus and
  little else (0.11 of the light); ISCCP files 0.02 of it under cumulus and 0.09 under middle and high types;
  drawn through the cloud photograph, that 0.09 gathers into a few bright clusters. By day over warm, wet
  land a share of it is now drawn as cumulus fields (`LAND_CU_SHARE`). **The share is fitted: 0.2, to EPIC's
  clear-forest medians at four places. Half was tried first and overshot three of the four.**

| close in, against 15 VIIRS scenes | release 1.2 | now |
|---|---|---|
| sizes, 4-256 km | 0.226 | 0.152 |
| cover | 0.253 | 0.159 |
| contrast | 0.088 | 0.059 |
| direction | 0.032 | **0.078, worse** |
| Amazon: mean light, atlas / VIIRS | 0.186 / 0.171 | 0.167 / 0.171 |
| Amazon: size spectrum (floor 0.39) | 0.53 | 0.45 |
| Congo: excess of bright cover | 0.25 | 0.15 |

Every scene, every measure. Worse: trades direction 0.06 to 0.10 (floor 0.03) and size spectrum 0.12 to 0.18
(floor 0.15, now outside); SE Pacific size spectrum 0.34 to 0.41 and North Atlantic direction 0.01 to 0.05,
both still inside their floors. None of these scenes has land cumulus in it: what moved is WHICH PART of each
tile falls on each scene, because the tiles are laid in two rows now. Classified: the audit carries about
0.05 of layout noise per scene, which this exposed; the trades' lack of direction is TRUE and old (the
cumulus grain has 0.03-0.07 where VIIRS has 0.13). The direction baseline is re-set with this note.

| whole disc against EPIC | release 1.2 | now |
|---|---|---|
| clear-ground colour | 13.1 | 11.9 |
| contrast | 1.53 | **1.85, worse** |
| mean brightness | 2.62 | **2.67** |
| bright-white fraction | 0.026 | **0.028** |
| forest medians, atlas minus EPIC: Amazon Dec, Congo Mar, Amazon Mar, Congo Dec | -31, -13, -5, +10 | -13, +6, +9, **+22** |

Contrast is a TRUE regression, taken deliberately and written beside the baseline: light moved from bright
clusters into thin fields lowers the disc's contrast by up to a level in six of eight frames. The Congo in
December is a TRUE regression too: the fitted share helps three forests and hurts the fourth.

The mean light of the same ground at 2 and at 8 km a pixel now differs by 0.001 to 0.028 (Congo -0.028;
it was 0.005 to 0.022).

---

## APPLIED (fourth round, 2026-11-10)

Scope agreed for the round: the water mask, then lake ice (A5).

**The register had this wrong, and so did I for three rounds.** A5 said "a band up to 150 km wide along
south-west Hudson Bay is classed as land". Measured against a witness (`audit_water.py`: ETOPO 2022, every
cell below sea level that connects to the world ocean), it was **5.3 million km2 of sea classed as land**:
the East Siberian Sea (460 thousand km2 in one piece), the Kara, Chukchi and Barents shelves, the mouth of
the Amazon, the Yellow Sea, the Arafura Sea, Foxe Basin, the Bahama banks. Cause: the mask was "sea is
wherever Blue Marble is its flat ocean fill", and Blue Marble paints every shelf sea, bank and plume in a
colour of its own, the same in all twelve months. The dark ones were caught by the lake rule; the bright
ones became land. It went unseen because land drawn in the picture's water colour looks like water. It
never iced, never glinted, and answered a click as land.

| water mask against ETOPO 2022, north of 60 S | before | after |
|---|---|---|
| sea drawn as land, million km2 | 5.27 | 0.31 |
| largest single patch, thousand km2 | 460 | 12 |
| south-west Hudson Bay and James Bay, thousand km2 | 106 | 2 |
| Bahama banks | 110 | 4 |
| Yellow Sea and Bohai | 197 | 4 |
| mouth of the Amazon | 94 | 2 |
| land drawn as sea, million km2 | 0.11 | **0.57, worse** |

*Land drawn as sea went up fivefold and is classified RESOLUTION-LIMITED.* The old mask could not err that
way: anything not fill was land. A real coastline can, and 0.57 million km2 along 1.6 million km of coast is
a third of a kilometre of mean offset between Natural Earth's 1:10m coast and the zero contour of a 1.85 km
grid. The largest patch, 12 thousand km2, is Lake Maracaibo: Natural Earth calls it sea, and the witness
cannot follow a strait narrower than its own cell. `REGISTER-water.md` lists the forty largest.

**What the mask is now** (`fields_surface.step_water`): land is Natural Earth's 1:10m land and minor
islands; south of 60 S it is joined to whatever the picture shows as ice. Inland water is Natural Earth's
1:10m lakes plus the dark fresh water the picture shows; twelve salt lakes that are bright in the picture
(Eyre, Tuz, Assal...) stay dry. Land comes to 149.0 million km2 (the Earth: 148.9).

- *Antarctica's ice front was tried three ways* against the per-year check of the sea-ice conversion,
  which fails when the atlas draws sea in cells NSIDC holds as land: Natural Earth's shelves (worst year
  6.8%), ETOPO's front (5.9%), the picture's ice (4.0%, used). South of 60 S the mask and ETOPO differ by
  0.29 million km2, reported apart and not gated: fast ice and moved fronts.
- *The colour came back as water.* With the banks and plumes classed as water they turned plain sea-blue,
  which is less true than before. A new field (`fields/shoal.webp`, the blue channel of the water texture;
  24.7 million km2, the world's shelves and lakes) says where the water's own colour is the picture's: the
  Bahama banks are turquoise, the Amazon's mouth brown, the Yellow Sea silty, as water, with the Sun's
  glint on them. Seen on the Mac's own GPU.
- **Not done:** wide rivers. The Amazon's main stem is brown in the picture and a line in Natural Earth;
  neither source has ever made it water here (new item A10).

**Lake ice (was: "Baikal, Great Bear and the Caspian never freeze").** A model, because no gridded
observation in hand covers lakes: freeze-up when the air's 48-day mean falls below freezing, Stefan growth,
degree-day melt, run over five colder and warmer years so that the answer is how often a day is frozen
(`build/lakeice.py`). Two numbers are fitted (the 48 days and the melt rate) to half of the 174 usable lakes
in NSIDC's lake-ice phenology database (ten or more seasons since 1980, with dates for at least four fifths
of the seasons they froze); the other half is the test (`audit_lakeice.py`). Nothing from it is shipped.

| lake ice against the lakes' own records | before | after |
|---|---|---|
| lakes of the 174 the field has ice for | 18 | 106 (the other 68 are too small to be water at 5 km) |
| days iced a year, mean error at those lakes | 59 (all of it short) | 16 |
| share of each month iced, mean error | 0.241 | 0.058 |
| the model on the 83 lakes it was not fitted to | - | 11 days a year, 0.043 of a month |
| for scale: lakes that never freeze | 142 days, 0.392 | |

*The witness had a fault of its own, found when Lake Champlain scored "never freezes".* Seasons with a date
missing were dropped and open seasons kept, so a lake whose frozen seasons are mostly undated was averaged
over its open ones. Such lakes are left out now (203 lakes became 174), and the selftest holds it.

- OISST's lake ice is kept where it has the lake and any ice (the Great Lakes, Ladoga), with its floor taken
  off: it carried 7% "ice" on Lake Ontario in July. Where it has the water and no ice in any month (the
  Caspian, the Sea of Azov, the Black Sea) the model speaks: the north Caspian and the Azov freeze now.
- *Two faults of the model's input, each fixed at its cause.* The reanalysis's air over a large lake is
  warmed by the lake's own open water (January over the Azov: +1.2 C, the shore -2 to -4): lakes are fed
  the nearest LAND's air. And one figure for how much winters differ (2.5 C) put ice on Lake Titicaca,
  where July is +2 C every year: the spread now follows each place's seasonal range.
- **Known to be wrong, measured, not fixed:** the model knows no depth, and the largest errors in the record
  are all deep lakes iced too long: Mjosa 145 days against 50, Lake Superior's Bayfield shore 132 against 66,
  Lake Constance 54 against none, Baikal at its southern station 148 against 102. A great lake left to the
  model would freeze whole. New item C4.
- The valid channel of the ice field now says how each cell's ice is known (255 sea, 215 and 150 modelled
  lake, 200 observed lake); a click on a modelled lake says "frozen N % of the month, MODELLED".

**Sea ice, the side effect.** The mask is in the sea-ice build (which cells are sea, where the coast fill
goes). Extent still equals NSIDC's mean by construction (largest gap 0.16%, was under 0.1%). The per-year
check, which is the evidence: north 1.45% median and 1.81% worst, south 0.78% and 4.02% (it was 0.6% and
3.7% over both). Slightly worse in the north; classified TRUE, small: more coast cells borrow ice.
Area under NSIDC's improved, 15.5% to 15.3%.

**Whole disc (EPIC), per measure:** brightness 2.66 to 2.62, contrast 1.54 to 1.53, white fraction 0.027 to
0.026, clear ocean 5.0 to 4.7, clear ground 13.2 to 13.1; disc profile 4.13 to 4.16, limb ring 0.118 to
0.119 and glint 0.13 to 0.14 worse by a last digit (CANCELLATION: the mask is in the audit's own sorting of
pixels as well as in the scene; no change to the light model).

---

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
| A5 | — | **DELIVERED 2026-11-10 (fourth round).** The water mask is a coastline now (Natural Earth 1:10m land, islands, lakes; Antarctica's ice front from the picture), held by `audit_water.py` against ETOPO 2022: sea drawn as land 5.27 to 0.31 million km2 north of 60 S. The cause was not shallow turbid water in a few places, as this row used to say: Blue Marble paints every shelf sea in a colour of its own and the mask was 'sea is the fill'. The colour of shallow water stays the picture's (`shoal.webp`). Lakes freeze: observed on the Great Lakes and Ladoga, modelled everywhere else (`build/lakeice.py`, `audit_lakeice.py`: 11 days a year on unseen lakes). Table and what is still wrong in APPLIED; the open parts are A10 and C4 | `fields_surface.step_water`, `fields_climate.step_ocean`, `build/lakeice.py` | visual review |
| A6 | P3 | The Atlas style's permanent-ice test is a brightness-and-latitude heuristic; mountain glaciers and seasonal snow can be misread | `earth.frag.glsl` atlas block | build notes |

| A7 | — | **RESOLVED 2026-11-10.** Cause established with a clear-sky composite of about a hundred EPIC frames (`epic_clearsky.py`): Blue Marble read as sRGB understated dark land threefold, and the display transform had been fitted around it. Now a nine-knot table per channel (`ALB_LUT`), fitted by `land_transfer.py`; held-out error 11.6 to 6.2; table above. **What the table is not:** surface reflectance. It is the albedo that reproduces EPIC's view, straight back along the sunlight, where rough ground hides its shadows. Dense forest sits at 0.07-0.09 in the red where field measurements say 0.03: the stable-pixel test passes few rainforest pixels (424 in the darkest bin), so the darkest end of the red curve rests on little | `earth.frag.glsl` `albedoOf()`, `shader_model.py` | EPIC |
| A8 | P3 | Snow and ice at a low Sun read grey. Partly better 2026-11-10: white Blue Marble pixels are now given snow's albedo (0.90) by rule, since the picture clips there, and Antarctica in December reads white. Sea ice and winter snow at high latitude are still grey: the surface model is Lambert (plus a Lommel-Seeliger share for land) and snow scatters forward. Seen, not measured: the composite excludes latitudes above 60 | shader | EPIC |
| A9 | P3 | **The outermost ring of the disc is 5-10 levels too bright and too green** (cos 0.1-0.2: atlas 85, 94, 100; EPIC 80, 84, 95). Rayleigh scattering saturates there in the model as in a plane atmosphere; the real loss is probably ozone, which EPIC's product does not show elsewhere on the disc, so it was not added. Would need a spherical-shell treatment of the last 2% of the radius | shader air block | EPIC |
| A10 | P3 | **Mostly DELIVERED 2026-11-10 (sixth round): wide rivers are water.** MODIS water (MOD44W) along Natural Earth's 1:10m river lines; nine wide reaches are drawn for 87% of their length on average (under 1% before). **Open:** the Parana (50%) and the Congo (71%), whose channels between islands are narrower than half a cell; Canada's inland water is now above the lake inventory (0.76 against 0.66 M km2 in lakes), because the mask takes the larger of three sources cell by cell; the river check is not independent of MODIS, and a width dataset (GRWL, Allen & Pavelsky 2018, CC BY 4.0, a new host) would make it so | `fields_surface.rivers8`, `audit_water.reaches` | fourth round |
| A11 | — | **DELIVERED 2026-11-11 (seventh round).** Sentinel-2 cloudless 2016 (EOX, CC BY 4.0; the owner approved the host) is streamed where the view wants a texel finer than 0.45 km, down to 19 m, and the zoom floor is 20 m a pixel | `detail.js` S2, `camera.MIN_KM_PER_PX` | sixth round |
| A12 | P3 | **Close in, land and water are still the shipped 5 km field.** The colour is the picture's own, but within a few kilometres of a coast sea is partly shaded as land and land as sea; coastal land carries a different tint from the land behind it (the join goes coarse near water); lakes and rivers under 2.5 km are in the picture and are not water to the atlas. A fine water flag in the window (the terrain tiles' sign, guarded against polders and depressions) would answer most of it | `earth.frag.glsl` join, `detail.compositeElevation` | seventh round |
| A13 | P3 | **Sentinel-2's colours go through a table fitted to Blue Marble** (`ALB_LUT`), and the picture is 2016 in one season: winter snow close in is the shipped field's 5 km patches over summer ground, and the Alps in January look it. A second table, or EOX's later mosaics (non-commercial licence: the owner's call), would be the routes | `earth.frag.glsl` albedoOf | seventh round |
| A14 | P4 | Borders (Natural Earth 1:50m) and the coast outline are drawn for a view fifty times further out and are visibly coarse at 20 m a pixel; place names stop at Natural Earth's 1:10m populated places | `vectors.py`, `overlays.Labels` | seventh round |

## B. Atmosphere

| # | P | item | touches | from |
|---|---|---|---|---|
| B1 | P2 | **Clouds: amount and brightness from observation; fine structure from real cloud since 2026-11-10 (third round).** Three kinds (photograph for fronts and storms, sheets, broken low cloud), amount and light from ISCCP (2007-2016), and closer than 10 km a pixel the shape is cut from three VIIRS scenes' ordering fields (`build/cloud_grain.py`), scored against fifteen other VIIRS scenes (`cloud_texture.py`; tables in APPLIED). Open, in order of what the pairs and the numbers show: (1) the Amazon in the dry season is fine cumulus everywhere; since the fifth round the atlas has a land-cumulus grain and draws a fifth of wet-land cloud light as cumulus fields (`LAND_CU_SHARE`, fitted to four EPIC forest medians, one of which it makes worse), and still has too few small clouds and clusters too bright (size spectrum 0.45 against a floor of 0.39); the share should come from a cloud-type climatology that resolves small cumulus, not from one fitted number; two grain channels are spare (`cloudgrain2.jpg` G, B); (2) the trades' brightest tenth is 0.45 against 0.23, and cumulus does not line up along the wind (direction 0.03 against VIIRS's 0.13; the texture audit also carries about 0.05 of noise per scene from which part of a tile falls on it, and should average several layouts); (3) Congo carries 0.14 too much light and twice the bright cover (0.47 against 0.22): ISCCP's April mean against three afternoons, and no daily cycle in the photograph regime; (4) bright cloud over the summer Southern Ocean is short in EPIC's December frames (white share 15-18% against 22%); (5) one scene stands for each kind everywhere and repeats every 2048 km; (6) no towers, no cloud shadows at an offset, no clearings along rivers and coasts; (7) sheet share under a fifth of the sky is not drawn; (8) positions are still one 2002 photograph carried on a monthly-mean wind; (9) the Sun-side brightening is pinned at two angles only; (10) between 4 and 11 km a pixel the grain fades into the 10 km photograph and the view is soft; (11) ISCCP shows a faint ring at the GOES-West sub-satellite point | `cloudAt()`, `pieces()`, `grainAt()`, `deckAt()`, `cumulusAt()`, `build/cloud_grain.py` | interview |
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
| C4 | P3 | **Mostly DELIVERED 2026-11-10 (fifth round): lake ice knows depth.** Freeze-up lag 10 x depth^0.7 days to 160; depth from HydroLAKES (measured volumes as they stand, predicted ones through their regression) and from ETOPO's lake floors for the Caspian, Baikal, the Great Lakes and the Black Sea. 9.8 days a year on 83 unseen lakes; 12.7 at the 23 recorded lakes the mask itself draws (17.2 before). Open: lakes under 500 km2 mostly have only a predicted depth (Mjøsa: 135 days against 50); Issyk-Kul is iced 53 days and should not be (salt, and the reanalysis's air is too cold there); a great lake freezes whole or not, cell by cell (the Great Lakes stay on OISST for that, itself weak); the north-west Black Sea shelf is unchecked; the audit can score only 23 lakes as drawn, because the phenology database is mostly small lakes; solar melt on high lakes is not modelled (Nam Co, Qinghai unchecked) | `build/lakeice.py`, `fields_climate.lake_depth`, `audit_lakeice.py` | fourth round |
| C5 | P3 | **River ice is the lake model at 7 m.** Moving water freezes later than a lake under the same air and an ice run breaks it up sooner. NSIDC G01377 holds river records too; none has been scored | `fields_climate.lake_depth`, `audit_lakeice.py` | sixth round |

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
| F11 | P4 | **Mostly answered 2026-11-11 by modelling.** Every 500 m night product on GIBS is at full scale across a metropolis, so the light's street pattern is taken from the daytime picture below about 300 m a pixel (amount measured, pattern modelled, labelled so). Between 300 m and 2 km a pixel a large city is still one even field of gold. Radiance with range exists (VNP46A4) behind an Earthdata login | `earth.frag.glsl` nightTex, ramp | sixth round |
| F12 | P3 | Ship tracers run on lanes that are under ice in that month (the Kara Sea in February): the shipping field is one average year. Gate lane tracers on the month's ice | `particles.laneAccept`, `fields.climate` | sixth round |
| F13 | P4 | Aircraft and tracer styling is by eye; nothing measures clutter. The ocean-current streaks are long white arcs at 3 to 5 km a pixel (seen off the Amazon's mouth) and may want the same treatment the aircraft got | `main.buildTracers` | sixth round |

## G. Engine, delivery and verification

| # | P | item | touches | from |
|---|---|---|---|---|
| G1 | — | **DELIVERED 2026-11-09; ten checks since 2026-11-10** (`clear-sky` added: the ground alone against the EPIC composite, and the audit's numpy copy of the shader against the shader). `audit_all.py`: frame tests, app math (now with eight EPIC sun positions), shader compile, audit selftests, sea ice, population, label coverage, EPIC, and the visual ratchet over six frozen frames. 2 min 19 s. Two captures of the same code differ by 0.000% of pixels; a 9% exposure change fails the ratchet (0.8% of pixels) | `Research/modeling/`, `Research/baselines/` | `/model-verify` |
| G2 | — | **DELIVERED 2026-11-10: published.** `build/build_site.py` builds `docs/` from `web/`: audits first, both stamps written before anything is copied, every module import and the stylesheet stamped (41 URLs), development-only files left out; checked booting under a sub-path with no unstamped script and no failed request. An in-app update log (`data/updatelog.json`, shown in About). Open: the AWS tile documentation line recorded under A2 was read and accepted by the owner for this release; attribution for GHSL, EDGAR, WRI, World Bank, GIBS and the terrain tiles is in About | `build/build_site.py`, `docs/` | SCOPE §11 |
| G3 | P2 | First-frame budget not measured. SCOPE says ≤ 6 MB and ≤ 1.5 s; the boot set is about 8 MB plus 23 MB of relief and elevation behind it | `fields.boot` | SCOPE §11 |
| G4 | P3 | Performance is unmeasured: full-screen shader at 2× device pixels, re-run on every camera move | `main.js` cache | build notes |
| G5 | P3 | **Mostly RESOLVED 2026-11-09.** Driven with real pointer and key events at 1440 x 900: drag turns the globe, wheel zooms both ways, G, A, space, N, / and Esc do what About says, a typed search flies to the place and opens its card (globe and sheet), both time sliders move the clock. One fault found and fixed (the fly-to clamp). **Still not done:** panel scrolling at small window sizes; satellites picked out by eye | `ui.js`, `main.js` | this session |
| G6 | P3 | Headless Chromium under software GL loses its first WebGL context at boot nearly every time. The app now reloads itself (three tries) and the second boot renders; cause not investigated. A frozen frame takes about 18 s there **Seen again 2026-11-10 (fourth round):** one of about eight runs of the visual check timed out on `sheet-atlas` (the frame never reported ready in 240 s) inside `build_site.py`, and passed when run again at once with no change. The build refused, as it should; the cost is a five-minute re-run | `main.js` | this session |
| G7 | — | **DELIVERED 2026-11-10 (sixth round).** `audit_gpu.py`: the six canonical frames on the machine's GPU (ANGLE Metal, 16 texture units) against the accepted software frames, worst 0.73 levels; and the lights-into-alpha write. The earth shader still uses 16 of 16 units: the next field that needs a sampler must share one (the streamed lights went into the imagery texture's alpha for that reason). The audit runs only where there is a GPU | `audit_gpu.py`, `fields.js` UNIT, `check_shaders.py` | fifth round |
| G8 | P3 | The GPU audit covers the frozen frames and one GL path. The streamed window itself (tiles, fades, a failed fetch) is checked by hand on the live page, not by any audit: it needs the network | `audit_gpu.py`, `detail.js` | sixth round |

---

**Count: 46 items; none open at P1** (A11 delivered and F11 mostly answered in the seventh round, 2026-11-11; A12 to A14 added). In order:

1. **B1** - bright cloud over the summer Southern Ocean; cumulus that lines up along the wind; a daily cycle for convective cloud over land; average the texture audit over several tile layouts.
2. **A12** - a fine land/water flag inside the close-in window.
3. **F2** - population by polygon.
4. **A10** - what is left: the Parana and the Congo, Canada's part-water cells, an independent width dataset.
5. **A13** - a colour table for Sentinel-2; winter close in.
6. **F12** - no ships on ice-bound lanes. **F1** - the sixteen European states the sheet still cannot name.
