# Handoff — World Atlas

Paste this whole file as the first message of a new session.

---

## What you are working on

**World Atlas** — A living atlas of the present-day Earth: one year of the planet and its people, composed per pixel and anchored at now.

- Repo: `~/World Atlas` (never under `~/Desktop` or `~/Documents`: macOS TCC)`
- Live: **https://augustg97.github.io/world-atlas/** (public repo `augustg97/world-atlas`, Pages from `main:/docs`, first published 2026-11-10). Local: `python3 build/serve.py 8150` -> http://localhost:8150.
- **Read `README.md` first.** It documents the goals, the standing working rules (§2), every
  subsystem, the traps that have cost time (§7), and the known limits (§9).
- `SCOPE.md` is the contract: the claim, the layer table, the canonical frame, the evidence
  boundary, the card contract, the standard for done, the non-goals.

## The current task

Kickoff, the first build, a verify round and ten build rounds are done, and the atlas is published. The
contract is `SCOPE.md`; the open work is `Research/MODEL-GAPS.md` (57 items, none at P1). Against NASA's
photographs the Space register is **close, with named exceptions**. Cloud close in now takes its fine
structure from real cloud and reads as a satellite photograph; it is not the cloud of the place, and it is
wrong in measured ways over the Amazon, the trades and the Congo (B1). The whole-Earth sheet carries a Europe
inset and a Lesser Antilles inset and its continent names (F1). The water mask is a real coastline and lakes
freeze, by a model that knows the air and, since the fifth round, the lake's depth (A5 delivered; C4 mostly;
A10 mostly, since the sixth round: the wide rivers are water). Over warm wet land a fifth of the cloud's light
is drawn as small cumulus (B1). Close in, ground and night lights are streamed at 0.5 km and the night
landscape is lifted so it can be read (declared in the lights card). The suite has a real-GPU check (G7 delivered).
Since the seventh round the zoom floor is 20 m a pixel and the ground below 0.5 km is Sentinel-2 cloudless (EOX),
with three declared departures close in: cloud thins away, exposure rises, city light takes the streets' pattern.
Since the eighth round land and water close in are told apart texel by texel (A12 mostly delivered: 2.5% of
texels wrong at 23 places against a 30 m witness, 10.2% before), and French Guiana and France's four island
departments are units of their own.
Since the ninth round (release 1.7, the owner's three asks: "let's do the colors and then the JRC water host. And
let's find a way to improve the loading time when zooming in"): Sentinel-2 is read by its own table and a city
close in is grey (A13 delivered: 5% off grey where it was 48%); land and water close in are JRC Global Surface
Water's record, streamed (A15 delivered: 2.2% wrong against a NEW witness, ESA WorldCover); and a view arrives in
two passes, the first in 0.3-1.3 s, the full one painted in from the middle of the screen.
Since the tenth round (release 1.8, the owner's five asks: clouds, seasons, a description on every card, better
cities with roads and buildings, and a night that shows a city as it is): the zoom floor is 5 m a pixel with
OpenStreetMap's streets and buildings drawn over Sentinel-2 (F15); at night the measured light sits along the
streets as lamps (F11); the month's colour reaches the close view whole (A16: 0.4% short at 23 places, 39% before);
the Southern Ocean's sheets are weather and cumulus lies along the wind (B1, two parts); and every place's card
opens with its Wikipedia article's lead, fetched live, and the atlas's own year at the place (F8).

## Reference material and the measurement harness

The comparison is only meaningful at **matched scale**. All of this exists; reuse it.

- `reference/epic/` (gitignored): eight NASA EPIC natural-colour frames and `frames.json` (where the
  spacecraft and Sun were). Rebuild with `./venv/bin/python Research/modeling/epic_compare.py --fetch`.
  Public domain. The National Geographic sheet is the Atlas-register baseline: measured against, never
  reproduced or committed.
- `ATLAS.refView(lon, lat, distRadii, discFrac)` stands the camera where EPIC stood. `web/js/refshots.js`
  renders all eight (`await (await import('/js/refshots.js')).renderEpic('tag')`, 1024 x 1024 window);
  `Research/modeling/epic_render.py` does the same headless.
- `Research/modeling/epic_compare.py --tag <tag>` prints the per-frame table and writes side-by-side
  pairs to `Research/figures/epic/`. `epic_cloud_cdf.py <tag> [--land|--zonal]` compares cloud brightness
  distributions. `_r0` is the first build, `_r7` after the verify round, `_r8`, `_r9` and `_r10` after the three
  build rounds. **The instrument changed at `_r10`** (both pictures are now shrunk by averaging light); `_r9`'s score
  file was re-made on it, so `_r9` and `_r10` compare and earlier score files do not.
- `epic_clearsky.py` builds a cloud-free EPIC composite per frame (third-darkest of about 16 days) and
  scores the atlas with clouds off against it; pairs are `Research/figures/epic/clearsky_*`.
  `epic_anchors.py` fits the display transform; `land_transfer.py` fits and scores the albedo table.
  `epic_render.py <tag> air,daylight,ice` renders with clouds off.
- `cloud_texture.py` scores cloud at 2 km a pixel against VIIRS scenes in five regimes (`cloud_scenes_render.py`
  renders the atlas over the same ground); each number is the excess over the photographs' own day-to-day
  spread. Pairs: `Research/figures/clouds/*_b0`, `_b6`, `_g8` (first, second, third round). `build/cloud_grain.py
  --preview` shows each grain scene cut at three amounts of light. `audit_labels.py` places and tests names on 24
  framings and in the sheet's insets.
- **Use the time in EPIC's image name, not its `date` field.** They differ by about five minutes and the
  centroid longitude belongs to the image name: with `date`, the Sun sat 1.1 degrees off in every frame.
- `?frozen=1` gives a deterministic frame (`window.__FRAME_READY`). Six of them are baselines in
  `Research/baselines/frames/`; the manifest is `Research/baselines/frames.json`.
- `ATLAS.step(n)` runs frames without `requestAnimationFrame`; `await ATLAS.shot('x.jpg')` writes
  `scratchpad/x.jpg` at device resolution. Every state is a URL.

## State right now

- Last live deploy: **2026-11-11**, release 1.8 (streets and buildings to 5 m; night light along the streets; the season close in; clouds; a description on every card); the stamps are in `docs/version.json` and must match the live `version.json`
- Branch `main` is what is published; `verify-round` was merged into it at release 1.0
- `data/` holds about 3.6 GB of sources and caches (gitignored); `python build/fetch_sources.py` rebuilds it,
  including 438 MB of NSIDC grids and 581 MB of ISCCP. Three reference sets live under `reference/`
  (gitignored): `epic/` and `epic/clearsky/` (300 MB) and `gibs_clouds/` (5 MB); each has a `--fetch`.
  `data/cloudtex/` holds the three grain scenes (`fetch_sources.py cloudtex`); `data/lakeice/` the lake-ice
  records (`fetch_sources.py lakeice`); `data/hydrolakes/` lake depths (`fetch_sources.py hydrolakes`, then
  unzip it there); `data/ne/` now also Natural Earth's 1:10m land, lakes and river centrelines;
  `data/modiswater/` NASA's MODIS water mask in 128 pieces (`fetch_sources.py modiswater`, 20 MB).
- `./venv/bin/python Research/modeling/audit_all.py` passes: nineteen checks, about 10 min (`streets`, `cloud-light` and `card-text` are new; a second checkout runs it with `ATLAS_PORT`). `gpu` needs this
  machine's GPU and exits 3 without one. `close-water` needs `reference/closewater` (23 places) and `reference/gsw`
  (eight 10-degree files of JRC, 410 MB) from `closewater_fetch.py`, the record's TILES per place from
  `closewater_fetch.py --jrc`, and the witness from `closewater_witness.py` (ESA WorldCover by range requests,
  16 MB, cached in `reference/worldcover`). `close-colour` needs `reference/s2global` (`s2_transfer.py --fetch`, 8 MB).
- **The app now talks to two outside hosts when zoomed in** (NASA GIBS, AWS Terrain Tiles), by default, and
  says so in About. Read register A2 before publishing: one line of the tile documentation needs the owner's eye.
- **A FIFTH AND A SIXTH OUTSIDE HOST since the tenth round, both the owner's answers of 2026-11-11:**
  `tiles.openfreemap.org` (OpenStreetMap's streets and buildings, closer than 120 m a pixel; credited on the map)
  and `en.wikipedia.org` (the opening of a place's article, when its card opens; no Wikipedia text is in the tree).
- **The zoom floor is 5 m a pixel.** Below Sentinel-2's 10 m the photograph is magnified and the streets and
  buildings are what is sharp. `web/fields/albedo_ref.webp` (3 MB) is new: Blue Marble at the picture's own season.
- **The earth shader uses 16 of 16 texture units.** See G7. The streamed lights share the imagery texture; the
  window's water flag is the elevation texture's third channel.
- **A FOURTH OUTSIDE HOST since the ninth round, approved by the owner on 2026-11-11: `storage.googleapis.com`**
  (JRC Global Surface Water's occurrence tiles), one request per elevation tile, at the elevation's zoom. Said in
  the Finer ground card and in About. NASA's MODIS water mask (GIBS) is now fetched only polewards of the record
  (78 N, 59 S), where release 1.6's rule stands in.
- **A window arrives in two passes** (`quickPlan`): the same rectangle two levels coarser, whole; then the full
  layers, the imagery painted tile by tile from the middle. `detail.stats` has `firstMs`, `paintMs`, `albMs`,
  `elevMs`. A frozen frame takes one pass.
- **The app streams a third layer when zoomed in on the night side** (NASA GIBS, VIIRS_Black_Marble): same host
  as the imagery, said in the Night lights and Finer ground cards.
- **A third outside host since 2026-11-11, approved by the owner: `tiles.maps.eox.at`** (Sentinel-2 cloudless 2016,
  CC BY 4.0), asked only closer in than about 0.6 km a pixel. EOX's attribution is on the map while its tiles are.
  Only the 2016 layer (`s2cloudless`) is CC BY; the later years are non-commercial and were NOT approved.

## What the tenth round found (2026-11-11)

Streets, the night and the season (the lead's part; clouds and the cards follow below).

1. **OpenStreetMap is reachable as vector tiles with no key** (OpenFreeMap, OpenMapTiles schema, CORS open). A
   tile is mostly things the atlas does not draw (names in sixty languages, points of interest): central Paris is
   0.5 MB a tile unpacked, Raleigh 64 KB. The page reads the format itself (`streets.js`, 120 lines).
2. **The night was a photograph of the day because nothing said where light comes from.** With the street plan
   the measured amount goes onto streets as lamps and parks go dark. A band of even light along every road read
   as a map; pools of light under lamps set down by rule read as a city.
3. **One canvas path of 100,000 overlapping pieces hangs the rasteriser.** And tiles overlap at their edges: draw
   each inside its own square or the overlap is drawn twice (pale bands across Paris).
4. **"Unmapped" is a question about 10 km, not 600 m.** At 600 m every park glowed.
5. **Left as a glow under the main roads, seven tenths of the light is the slab of gold again.** A tenth at most.
6. **The season cannot be a ratio between two cameras.** Sentinel-2's blue over green is 2.5 times Blue Marble's
   for the same field; Blue Marble's month over its reference, multiplied in, made Iowa's April fields purple.
   It is a shift of colour in albedo now, at the texel's own brightness.
7. **Joined in scene light, the month's brightness brought the air with it.** Joined in albedo, the close view
   keeps 94 to 104% of Blue Marble's change of colour at every scored place; before, anything from 35 to 250%.
8. **The audit found both faults because it scored in the wrong space first.** In scene light a correct join
   looks erratic; the claim lives in albedo. Its own text now says why.
9. **A colour without its brightness is not a colour through a table that bends.** The reference is carried as
   albedo ratios; the page reads the table out of the shader's own text so there is one copy.
10. **Three bytes fit in one channel of a float texture.** That is how the sixteenth sampler still holds: the
    lights' amount and the season reference ride in the elevation texture's fourth channel.
11. **The far view's bare fields are mauve** (brown soil behind blue air), and the close view now matches it. Not
    this round's to fix; it is the far view's colour (A7, A19).
12. **Seen through the whole atmosphere, a city at 5 m a pixel is a grey sheet.** The air's veil is thinned close
    in and the contrast raised, by eye, declared (A19).
13. **The globe camera had a second floor** (1.004 radii) under the first.

Clouds (a helper session, branch `clouds-b1`, merged):

14. **The summer Southern Ocean was not short of light seen straight down.** It was drawn as a veil over
    everything. Given to the photograph's weather systems, the same light has EPIC's spread (31 to 38-41 levels).
15. **EPIC's light over the storm belts is level from the disc's centre to a view cosine of 0.5; over the tropics
    it doubles.** Layered cloud has no gaps to close at a slant. The slant law is for heaped cloud only now.
16. **Broken low cloud does run along the monthly-mean wind** (1 to 41 degrees off it in the audit's own scenes),
    whatever the wind's speed; fronts and sheets do not. The grains are read along it: 36.8 to 11.6 degrees.
17. **The number moved more than the picture.** The trades lean with the wind and are not streets: the grain's
    pieces are five times a street's cells. A real street scene in a spare grain channel is next.
18. **The audits hard-coded port 8150**, so a second checkout's audit would have rendered the first's page.
    They read `ATLAS_PORT` now.

Card text (a helper session in this checkout):

19. **Natural Earth's Wikidata ids are wrong often enough to need an audit**: 54 of them point somewhere else
    (San Lorenzo 10,481 km away; Pyongsan at Pyongyang). Distance from the item's own coordinate, scaled by the
    thing's size, catches them; 795 items have no coordinate and are checked by their article's.
20. **A match by name inside a big thing's limit can still be wrong.** The Sahel matched "Sahel, Tunisia", 2,300 km
    off and inside the Sahel's own 5,200 km. By-name matches are held to 350 km or the exact title.
21. **The description made the climate fields visible, and they are coarse.** Lima reads as steppe with 520 mm of
    rain. Nothing scores those fields (B2), and now every card prints them.
22. **Wikimedia holds a client with no contact address to ten requests a minute.** The title build is two hours
    cold and instant warm (`data/_cache/wiki`).

## What the ninth round found (2026-11-11)

1. **The yellow was not a tint to remove; it was the join.** Every texel took Blue Marble's 5 km colour, and Blue
   Marble's colour for a city is olive (New York by the table: blue albedo a third of red). A per-channel table
   for Sentinel-2 fitted to Blue Marble reproduced it. What worked: read the picture as SCENE LIGHT by ONE curve
   for the three channels, take the shader's own air out, and join in scene light.
2. **Blue Marble's land is warmer than Sentinel-2's everywhere** (13% more red, 13% less blue, the median of
   270,000 cells), and a city more so. Neither is a season, and nothing in the shader can tell either from one
   cell by cell: there is no sampler left for a reference month. So the month's colour is applied less the
   standing warmth, at HALF strength, by eye. Full strength turns New York green-grey; none loses the year.
3. **Two keys on saturation were tried and dropped.** By texel: a patchwork of grey and yellow roofs. By 5 km
   mean: Los Angeles and the Po valley's fields have the same saturation (0.23-0.26) and want opposite answers.
4. **The albedo table and the air are one system.** The Sentinel-2 table holds the shader's lighting and
   atmosphere at a standard Sun as two constants; `audit_closecolour.py` recomputes them from the shader's own
   constants and fails if they drift. Retune the air and it must be refitted (`s2_transfer.py`).
5. **JRC's tiles are the whole answer where they exist.** Sharpening them with the picture's colour (two ways)
   won at three places where the water has moved (Lake Mead, the Dead Sea, Cairo) and lost at four or five
   others; the means tied. The record is used as it is, and the three are recorded.
6. **JRC had been the witness; it needed replacing before it could be the source.** ESA WorldCover 2021, read by
   HTTP range requests with tifffile (no GDAL): 16 MB for 23 places. By it release 1.6's rule is 3.2% wrong, not 2.5%.
7. **JRC lies about one texel west of the picture** across Europe and the north-eastern United States, and not in
   California. WorldCover sits on the picture. Found by a sub-agent set to build the witness.
8. **The tile set stops at 78 N and 59 S** although the record is described as 80 N to 60 S. Asking beyond it is
   a console error per tile, so the plan is checked against the edge first.
9. **Loading was one host's queue.** 110 Sentinel-2 tiles eight at a time was 5.4 of 5.8 s. Sixteen at a time is
   about 45 tiles a second and more does not help: the server is the limit. What changed the experience is the
   order: a quick pass a sixteenth the size, then the middle of the screen first.
10. **A share makes a better shoreline than a flag.** The record's occurrence, filtered, crosses a half within a
    texel; as 0 or 1 a river three texels wide was a staircase.

## What the eighth round found (2026-11-11)

1. **No host the page may ask has a fine water map.** NASA's 250 m MODIS mask is the best there, and it holds
   most of Manhattan as water. GIBS's OSM layer is the sea only; the terrain tiles' flatness tells nothing.
2. **Colour alone cannot find a river** with one set of weights for the Earth (0.15 of the Seine). **Each window
   can learn its own water's colour** from the mask's water, and that works: 2.5% of texels wrong at 23 places.
3. **The mask must be doubted where it has far more water than the shipped field over 8 km.** That, and asking
   doubted water to be a body, is what makes Manhattan land. Texture and height were tried and dropped (measured).
4. **A rule can lose its worst case when a feature is dropped for a good reason.** Taking texture out improved
   the mean and put Manhattan back under water. The per-place table showed it; the mean did not.
5. **The self-test scene has to contain the mechanism.** Roofs are land to the rule only because it has seen
   roofs elsewhere; a made scene with one roof district failed, correctly.
6. **With water known, the coast needs no special join.** Take the sea out of both 5 km means (the fill's colour
   is one number; the window's water colour is counted) and the inland rule holds to the shore.
7. **The rule's first run in a session costs 0.7 s** (cold code). It runs in a worker.
8. **Natural Earth's countries hold France's overseas departments inside France.** Its map-units file holds them
   apart. `build/units.py` is now the one list of units; three readers share it because ids are indices.
9. **A white frame in my harness** came from the pane showing another tab while the shot was taken. Shoot again
   before believing a blank.

## What the seventh round found (2026-11-11)

1. **EOX serves Sentinel-2 cloudless in the atlas's own frame** (EPSG:4326, 256 px, level 13 = 9.5 m), with CORS.
   Compositing is a copy, as for GIBS.
2. **Another camera's picture cannot be ADDED to the shipped month.** More contrast: sand past full scale, fields
   below zero, and a clamp that drew a lime desert. Joined by ratio.
3. **One tint for the whole screen is wrong where the screen holds two kinds of ground**; a 5 km tint is wrong at
   a coast. The join is 5 km inland and coarse only near water. A coastal strip still carries the coarse tint.
4. **The whole-disc exposure is too dark to read a city by.** It rises close in, where cloud has thinned away and
   the ground is not itself bright. Declared.
5. **City light can borrow the ground's pattern.** Amount from Black Marble, pattern from the daytime picture,
   labelled modelled. F11's "no inside to a city" is answered below 300 m a pixel.
6. **Nothing measures the close-in picture.** No reference at that scale; the frames do not reach it.
7. **The terrain tiles have pits** (one 1,895 m deep under Manhattan). `detail.despike`, tested.
8. **`viewBox` read a stale camera basis** and the planner, which plans once per view, could miss a view for good
   after a fast programmatic zoom. Fixed in `viewBox`.
9. **My harness shot before the window had faded in**, and the feature looked broken. Wait 450 ms after
   `detail.busy` clears.

## What the sixth round found (2026-11-10)

1. **Wide rivers are water**: MODIS water along Natural Earth's river lines. Nine wide reaches drawn for 87% of
   their length on average, from under 1%. The Parana (50%) and the Congo (71%) are the rest.
2. **The lakes strung along rivers came too**, 0.87 M km2 of inland water, and every region moved toward
   HydroLAKES's lake areas. Canada is now above it (0.76 against 0.66 in lakes): the larger-of-three-sources rule
   over-counts part-water cells.
3. **The water audit flooded up the rivers** and called them land drawn as sea. Its sea now excludes rivers.
4. **The planner capped itself at 1 km.** At 0.45 km it reaches Blue Marble's last level (0.49 km) and terrain
   zoom 9. That is the end of the free pictures: finer needs a new source and the owner (A11).
5. **City lights at 500 m have no inside.** Three GIBS products, all at full scale across Los Angeles (F11).
   The curve close in tops out at gold so edges and names read.
6. **Warm excess gates light, it does not rank it**: it falls where a city turns white. Green ranks.
7. **Tracers remember their spawn scale** and are recast on a camera move; a still camera changes nothing.
8. **Headless Chromium reaches the GPU with `--use-angle=metal`.** The six frames agree with the software frames
   to under one level in 255. The lights-into-alpha write is tested there too.

## What the fifth round found (2026-11-10)

1. **The lake-ice model's error went with depth at r = 0.76** (and with area at 0.23). Lag = 10 x depth^0.7
   days, to 160. Constance 57 to 6 days (record 0), Vattern 55 to 13 (13).
2. **Most HydroLAKES depths are predictions** (`Vol_src` 3) and at face value made the drawn lakes worse.
   Used through their regression; measured ones (all lakes over 500 km2) as they stand.
3. **A lake's HydroLAKES point is its outlet**, up to 50 km from the lake as a 5 km mask draws it.
4. **The "drawn" lake-ice score was scoring whichever lake fills the cell.** It now takes only lakes that are
   themselves in the mask: 23. Old and new numbers do not compare.
5. **The Amazon's missing cumulus was a partition problem, not a texture problem.** A land grain alone moved
   the size spectrum 0.53 to 0.50; drawing a fifth of wet-land cloud light as cumulus fields moved it to 0.45
   and made the mean light match. The fifth is FITTED to four EPIC forest medians and hurts one of them.
6. **EPIC's contrast got worse for it (1.53 to 1.85)**, on purpose, written beside the baseline.
7. **The cloud-texture audit carries about 0.05 of layout noise per scene**: re-laying the tiles in two rows
   moved scenes with no land in them.
8. **The cloud texture has two spare channels** (`cloudgrain2.jpg` G and B) for a fifth and sixth grain.

## What the fourth round found (2026-11-10)

1. **5.3 million km2 of sea was classed as land**, not "a strip of Hudson Bay". Blue Marble paints every
   shelf sea in a colour of its own and the mask was "sea is the fill". Found by `audit_water.py` (ETOPO below
   sea level, connected to the ocean). Now Natural Earth's 1:10m coast: 5.27 to 0.31 million km2.
2. **My first account of the cause was wrong** (I said the July picture showed the shelf under ice; the
   picture's sea is the same in all twelve months). Sample the source before explaining it.
3. **The fix took the turquoise off the Bahama banks**, which the error had been carrying. `shoal.webp` (blue
   channel of the water texture) says where water takes the picture's own colour.
4. **Antarctica's ice front decides whether the sea-ice conversion passes**: Natural Earth's shelves 6.8%
   worst year, ETOPO's 5.9%, the picture's ice 4.0%.
5. **Lake ice is a model now** (`build/lakeice.py`): 11 days a year out on 83 lakes it never saw. It has no
   depth: Mjøsa 145 days against 50, Baikal 148 against 102.
6. **The reanalysis's air over a lake is warmed by the lake.** Lakes are fed the nearest land's air.
7. **The lake-ice witness scored Lake Champlain as never freezing**: undated frozen seasons were dropped and
   open ones kept. Fixed in the instrument (203 lakes became 174).
8. **A water-mask change moves everything downstream**: sea ice (per-year check 0.6% to 1.5% median in the
   north), ships, and the EPIC audit's own sorting of pixels.

## What the third round found (2026-11-10)

1. **Generated cloud never passed for cloud; real cloud's ranks do.** Three VIIRS scenes, each reduced to
   every pixel's rank among its neighbours, tell the shader WHICH pixels the cloud takes at a given amount.
   Size-spectrum error against fifteen held-out scenes 0.62 to 0.23 in one step; direction and cover better too.
2. **A piece of cloud is mostly thin.** Measured on 18 scenes: the cloudy part of a broken field averages a
   reflectance of 0.33-0.45 with a spread of 0.34-0.53 of that. Flat white pieces scored half again the
   photographs' contrast.
3. **Sheet cloud had a by-eye brightness law a third above ISCCP's.** Now ISCCP's (share times 0.50); the SE
   Pacific scene went from 0.13 to 0.06 above VIIRS.
4. **The Sun-side brightening was applied per resolved piece and weakened with zoom.** It is a property of a
   field; it is worked out on the far view's light now.
5. **The EPIC audit shrank pictures by point sampling, in display values.** Fixed, with a stripe selftest. The
   old baseline's renders were re-scored on the new instrument before anything was compared.
6. **EPIC vetoed two fixes VIIRS asked for** (cumulus spread evenly; daytime land cloud spread evenly). Both
   withdrawn; the comments in the shader say what each cost.
7. **Contrast close in went backwards (0.026 to 0.088) and is re-set with a written table**: Amazon and trades
   TRUE, Congo PRE-EXISTING. `audit_all.py` carries the reason.
8. **Release 1.0 said the sheet named 129 states; 22 of those names were under the dashboard.** Names are no
   longer placed under panels, and the count leaves out what cannot be read: 106 before, 125 now, of 177 in view.
9. **An inset is a second camera, not a picture**: the earth shader into its own target, names by the same
   placement code, clicks routed through `viewAt`. `web/js/insets.js` holds the geometry; they need open sea
   between the panels and vanish in a small window.

## What the second build round found (2026-11-10)

1. **Cloud amount is not cloud light.** ISCCP puts 74% cloud over the Congo in April and VIIRS shows a mean
   reflectance of 0.22 there: most of it is thin. The picture is now driven by amount times the reflectance
   of each kind's optical thickness, and with no tuning lands within 0.08 of VIIRS at five scenes.
2. **The reanalysis cloud field had no stratocumulus decks** (16% bright cloud off Peru; VIIRS 45%).
3. **VIIRS and ISCCP (looking down) and EPIC (looking from the Sun) differ by a third in cloud light.**
   Modelled as shadow hiding in broken cloud, pinned at those two angles only.
4. **Noise in longitude-latitude space is stretched at high latitude**; generated cloud now lives on the sphere.
5. **A straight-line threshold on noise gave 8% cover when asked for 20%.** Measured quantile curve now.
6. **Seventeen samplers linked in the audits and failed on the real GPU.** Guarded now; no real-GPU audit yet.
7. **The tiles' sea floor is a different product from the shipped one** (1-4 km apart). Land agrees to 25 m.
8. **The label audit's own state list was wrong** (no Kazakhstan, no Cuba). 198 now.
9. **Three cloud versions scored better than their predecessors and looked worse.** Read the pairs.

## What the build round found (2026-11-10)

1. **Blue Marble is not sRGB.** Its values are close to linear in reflectance with a different gain per
   channel. Read as sRGB, dark land came out at a third of its brightness. Found with a cloud-free composite
   of about a hundred EPIC frames; fixed with a measured table (`ALB_LUT`), held-out error 11.6 to 6.2.
2. **Last round's exposure was fitted around that error.** The display transform is now fitted only to
   targets of known reflectance (deep convective cloud, clear ocean). The Libya-4 calibration site, not in
   the fit, lands within 3 levels. Exposure 0.70, gamma 1.63.
3. **Cloud brightness over ocean matches EPIC within 5 levels at every percentile.** Over land it is within
   6 to the median and 8-20 dim above.
4. **Sea-ice extent matches NSIDC by construction; the evidence is the per-year check** (0.6% median, 3.7%
   worst over 720 grids). The median ice edge does NOT reproduce the mean extent (up to +13.8%).
5. **The mean wind vector is not the mean wind speed.** The glint was 1.4 times too strong; the old gamma hid it.
6. **EPIC's product shows no ozone tint.** Drawing ozone turned the limb lilac. Removed.
7. **A precision fault smeared cloud into vertical streaks** at regional zoom: the drift offset was hundreds
   of turns. Only its fraction is kept now.
8. **The water mask is wrong in shallow water** (south-west Hudson Bay is "land" for 150 km). Not fixed: A5.

## What the verify round found (2026-11-09)

All measured. Numbers are display values 0-255 over eight EPIC frames unless stated.

1. **The limb glow was twenty times too thick.** Its two scale heights were 57 km and 190 km; the air's is 8.
   EPIC shows nothing outside the disc. One Rayleigh model now serves the haze and the limb. Glow outside the
   limb: 73.9 to 0.15.
2. **The frame was 27 levels too bright and the ocean too blue.** Exposure and gamma fitted to clear ocean,
   desert and bright cloud. Ocean colour error 40 to 4.6; ground 51 to 16; mean brightness 27 to 7.
3. **EPIC's vegetated land is studded with daytime cumulus the atlas had no mechanism for.** Added, driven by
   rainfall and local solar time. Land is still 10-15 levels dim against EPIC at every percentile (A7, B1).
4. **Sea ice is worse than kickoff said.** Against NSIDC's twelve monthly means: Arctic +11 to +31%, Antarctic
   +16 to +94%. The cheap fix was tried and does not work; the excess is in the source field (C1).
5. **21 of 204 states are named** at the baseline sheet's framing (F1).
6. **Population by country:** total within 0.4% of the World Bank; 26 units off by more than 10% (F2).
7. **The app's Sun agrees with EPIC's own vectors** to 0.22 degrees of longitude and 0.005 of latitude in all
   eight frames. An independent witness: no sidereal-time formula of ours is in EPIC's numbers.
8. **Controls work**: drag, wheel, G, A, space, N, /, Esc, search, both sliders, by real input events. One
   fault found and fixed: fly-to could throw the sheet camera to 0,0.

The rule-0 check on `Research/baselines/frames/globe-default.png`: it reads as a lit planet (per-pixel
ground, Sun, air, cloud, city lights); a viewer can read off it that it is afternoon over Africa and night
over India, that the Sahara is bare and the Sahel under cloud, and where the cities of the Gulf and the
Ganges plain are; the subject itself is on screen; the scale bar is drawn and the relief exaggeration is
stated in About.

## Traps that have each cost real time

See `CLAUDE.md` - the traps, each with what it cost.

Plus the standing ones:

- a process backgrounded with `&` inside a tool call dies when that call ends; `nohup` does not
  save it. The tell is a log that stops after one line.
- `pgrep -f <script>` matches the waiter's own command line. **Wait on a PID** —
  `until ! kill -0 "$PID"`.
- a static host can serve stale JSON after a successful push. Stamp the data version **before**
  copying the app file, and verify the live value.

## The work queue

1. **B2** - a witness for the climate fields (station normals or ERA5 monthly means, measure-against only).
   Every location card now prints them month by month and classes the climate from them; Lima reads as steppe.
2. **B1** - what is left: a real cloud-street scene in a spare grain channel (the trades lean with the wind and
   are not streets); the Southern Ocean belt's level in December (5-12% under EPIC); a daily cycle for convective
   cloud over land; `LAND_CU_SHARE` from data (not refitted after the exact cross-fade).
3. **F16** - make the street lamps' light add up to Black Marble's amount in each 500 m; and the step in
   brightness between the street view and the gold field further out (F11).
4. **A19** - a measure for the thinned air and raised contrast close in, which are by eye. **A20** - unequal
   texels, so the close grid is 2.4 m at high latitude too. **A21** - look at the 5 m floor in motion.
5. **A17** - water that has moved: Lake Mead, the Dead Sea. JRC's `seasonality` or `transitions` tiles would say
   where the record itself is in doubt; there the picture could decide. **A12**'s remainder with it.
6. **F7** - whether Wikipedia's opening belongs on dispute cards is the owner's call (asked in the tenth round's
   report). **F8** - 855 cards without an article; a click on a river line.
7. **C4, C5** - small lakes' depths, part-frozen great lakes, Issyk-Kul; river ice scored against river records.
8. **F2** - population by polygon. **A10** - the Parana and the Congo. **F12**, **F1**, **F14** as before.

**If you touch the light model** (`earth.frag.glsl`, Space branch): the order is `epic_anchors.py` (refit
exposure and gamma), then `land_transfer.py --fit` (refit the albedo table, paste the printed line), then
render and score. The table depends on the transform; fitting them the other way round is what went wrong
in the verify round. `shader_model.py` must be changed in step with the shader: its instrument check
(`land_transfer.py`, first line of output) says in display levels whether it has drifted.

When a baseline frame moves, look at `Research/baselines/_diff/`, then
`frame_baseline.py accept --frame <name> --reason "..."`. When an audit number improves, tighten it in
`audit_all.py` in the same commit.

## Commands

```bash
See `CLAUDE.md` -> Commands.
```

## How the user wants this done

Read the working rules in `README.md` §2 — each came from a specific failure. The ones that
matter most:

- **Visually verify.** Render it and look. Statistics are not confirmation.
- **Fix the system, not the instance.**
- **Measure before tuning.**
- **Address every item raised**, and say so explicitly when something cannot be done.
- **Be honest in the assessment** — the user has asked for a truthful yes/no against the
  reference, not an optimistic one.
