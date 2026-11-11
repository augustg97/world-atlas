# World Atlas — instructions for Claude sessions

A living atlas of the present-day Earth: one year of the planet and its people, composed per pixel and anchored at now.

**Read `README.md` first** — §1 (what this is trying to be), §2 (the working rules), §7 (traps),
§9 (known limits). Then `SCOPE.md` for the contract and `HANDOFF.md` for the live state.

The general protocol lives in `~/Modeling Studio`. Its skills apply here:
`/model-research`, `/model-build`, `/model-verify`, `/model-ship`.

---

## Standing rules — these override default behaviour

0. **The surface is the argument, and it must be a legible surface of the real thing.** Three
   requirements, all of them: (a) the substrate is **composed per pixel** — structure, texture,
   light, material, motion — never dots and symbols on flat ground; (b) it is a rendered surface of
   **the actual matter the subject is made of, at the scale the subject happens on** — which is not
   always a place. Seven families are admissible: **terrain, volume, body, section, machine,
   artefact, built scene.** The test is that every pixel is somewhere you could put a probe and the
   axes are physical. An abstract or semantic space is never the substrate, only a secondary view;
   (c) it is **legible** — a viewer can name concrete things off it without a legend.

   Every round, screenshot the full frame and answer in writing: *does this read as a rendered world
   rather than a chart*, *name three facts a viewer can read off it*, and *is the thing I am
   modelling visible here, or only where it is?* That last question catches **the subject demoted to
   its footprint** — rendering a map of where a machine, a body or a column of water is, instead of
   the thing itself. Rule 0 because it is the one the work is judged on. See
   `Modeling Studio/references/WORKING-RULES.md` §13 and `ARCHITECTURE-PATTERNS.md` §0, and SCOPE §3
   for this project's substrate family and stated bar.

1. **Always visually verify.** An update is not done when the data contains the value. It is done
   when it has been **rendered and looked at**. Render the frame, `Read` the image, confirm the
   change is on screen and is correct. "The field has the value" is not confirmation.

2. **Fix the system, not the instance.** When correcting an error, make the change at the level
   that fixes the whole **class** across the whole timeline. A patched instance leaves the same
   bug at every other time and place.

3. **Prefer structural, model-based changes over cosmetic ones.** Ask what the real-world object
   or process is, and model that. Let the appearance fall out of it. Parameter tuning produces
   "modest improvements" and never closes a gap.

4. **Measure before tuning.** Histogram it, spectrum it, or A/B each term behind a debug flag
   before changing a constant.

5. **Track every request each round and address all of them.** If something genuinely cannot be
   done, say so explicitly and say why — do not omit it.

6. **Always deploy, and verify the live artefact.** Every round ends with a build, a commit, a
   push, and a check of the live data-version stamp. Here that is `build/build_site.py` (it runs
   the audits and refuses on a regression), a commit, `git push`, and reading the stamp back from
   https://augustg97.github.io/world-atlas/version.json. In force since the owner published on 2026-11-10.

7. **Never ship on an average.** Score every item individually, before and after, and classify
   every regression.

8. **When an audit disagrees with the app, check the audit first.**

9. **Say what is contested**, in the data, as a field.

10. **"Unknown" is a legitimate return**, and where a fallback is unavoidable the UI labels it as
    a fallback.

11. **Every number on screen carries its evidence tier and its vintage** (`web/js/catalog.js`).
12. **Away from now, live layers go dark, never stale.**
13. **Modelled motion is labelled as modelled.** No vehicle on screen is a real vehicle.
14. **Borders follow who administers the ground; every dispute is dashed, hatched and carded.**
15. **A source goes through `build/frames.py` or it does not go in**, and each build step asserts real landmarks.
16. **Published since 2026-11-10** (the owner's decision, that day): public repo `augustg97/world-atlas`,
    Pages from `main:/docs`. Everything committed to `main` is public. Nothing that is not the project's own
    or freely licensed goes in the tree: `reference/` (the National Geographic sheet, EPIC and VIIRS frames),
    `data/` and `scratchpad/` stay ignored. A NEW outside host, a new data licence, or anything about the
    owner beyond what is already in the tree is the owner's call first. Hosts the page talks to, each approved:
    NASA GIBS, AWS Terrain Tiles, the live feeds, and since 2026-11-11 EOX (`tiles.maps.eox.at`, layer
    `s2cloudless` ONLY: the 2016 mosaic is CC BY 4.0; the later years are non-commercial and not approved).
    `storage.googleapis.com` (JRC Global Surface Water) is asked by `closewater_fetch.py` for the audit's witness
    only; the PAGE asking it for water tiles is register A15 and is not approved.

---

## The canonical frame

Equirectangular WGS84 rasters, pixel-centre registered, column 0 centred at -180 + half a cell, row 0 centred at +90 - half a cell (north first). One clock: UTC milliseconds. Climatology is addressed by fractional month with keyframes at mid-month, cyclic. Administrative key: Natural Earth `ADM0_A3`. Rendering treats latitude as spherical on a 6371.0088 km sphere.

Every source is converted into it. The conversions are in `build/frames.py` (tested by `build/test_frames.py`). **Never combine
two sources without checking they are in the same frame** — this is the most expensive class of
bug in this kind of project.

## The evidence boundary

**Now.** The model holds one typical year (1991-2020 means; surface imagery of 2004), not a history and not a forecast. Live feeds exist only within their own latency of the present. Every layer carries a tier badge - LIVE, OBSERVED, CLIMATOLOGY, STATIC or MODELLED - and when the clock leaves the present the live layers switch off and the clock reads *Typical year*.

Past it, the model is inference and the UI says so.

---

## Commands

```bash
# serve the app (no caching)          -> http://localhost:8150
python3 build/serve.py 8150

# tests and pre-flight - run before and after any change
./venv/bin/python build/test_frames.py          # every source layout -> canonical frame
node build/test_app_math.mjs                     # ephemeris vs almanac, projection, cameras
./venv/bin/python build/check_shaders.py        # compile every shader

# rebuild data (each step asserts landmarks and stamps web/version.json)
./venv/bin/python build/fetch_sources.py        # ~3.6 GB into data/ (gitignored); idempotent
./venv/bin/python build/fields_surface.py       # water albedo elev night clouds   (albedo:7 = one month). After `water` (needs fetch_sources.py modiswater ne): fields_climate.py ocean, fields_human.py ships lanes
./venv/bin/python build/cloud_grain.py          # cloudgrain.jpg, cloudgrain2.jpg: four VIIRS scenes as rank fields (fetch_sources.py cloudtex first; --preview to look)
./venv/bin/python build/fields_climate.py       # atmo ocean currents
./venv/bin/python build/fields_human.py         # pop ships lanes co2 countries
./venv/bin/python build/vectors.py              # political places physical plates quakes volcanoes power stats air
# the list of political units is build/units.py (France's overseas departments are their own): `political`, `places`
# and fields_human.py `countries` must be rebuilt TOGETHER when it changes, because a unit's id is its index

# the whole audit suite against its baselines (fifteen checks, about 6 min; --quick skips the browser checks)
./venv/bin/python Research/modeling/audit_all.py
# score against NASA EPIC by hand: render (headless), then compare
"$HOME/Modeling Studio/.venv/bin/python" Research/modeling/epic_render.py cur
./venv/bin/python Research/modeling/epic_compare.py --tag cur
# the light model, in this order: display transform at physical anchors, then the albedo table, then score
./venv/bin/python Research/modeling/epic_anchors.py
"$HOME/Modeling Studio/.venv/bin/python" Research/modeling/epic_render.py clr air,daylight,ice
./venv/bin/python Research/modeling/land_transfer.py --fit      # prints the ALB_LUT line for the shader
./venv/bin/python Research/modeling/epic_clearsky.py --tag clr  # needs --fetch once (300 MB)
# cloud close in, against VIIRS scenes at 2 km a pixel (needs --fetch once, 5 MB)
"$HOME/Modeling Studio/.venv/bin/python" Research/modeling/cloud_scenes_render.py cur
./venv/bin/python Research/modeling/cloud_texture.py --tag cur    # pairs land in Research/figures/clouds/
# the page on this machine's own GPU against the accepted software frames (needs the dev server; exit 3 = no GPU)
"$HOME/Modeling Studio/.venv/bin/python" Research/modeling/audit_gpu.py
# land or water close in: the app's own rule (web/js/water.js, under node) at 23 places against a 30 m witness
./venv/bin/python Research/modeling/closewater_fetch.py         # once: 23 places and eight witness tiles (520 MB, reference/)
./venv/bin/python Research/modeling/audit_closewater.py --register
# build the published site (audits first; stamps code and data; never pushes)
./venv/bin/python build/build_site.py
# the visual ratchet alone; accept a moved frame only with a reason
"$HOME/Modeling Studio/.venv/bin/python" "$HOME/Modeling Studio/tools/frame_baseline.py" check --project .

# look at a frame at full resolution (the browser pane may be hidden or scaled)
#   in the page:  ATLAS.step(200); await ATLAS.shot('name.jpg')   ->  scratchpad/name.jpg
```

## Traps that have each cost real time here

- **NASA's MODIS water mask holds most of Manhattan as water.** As a seed for learning a window's water colour it
  taught the rule that roofs are water. The mask is doubted wherever it has far more water than the shipped field
  over 8 km (`water.js`). Any new use of that mask needs the same doubt.
- **A mean hid the worst case.** Dropping local texture from the water rule improved the 23-place mean and put
  Manhattan back under water. `audit_closewater.py` gates `manhattan_false_pct` by name; read
  `REGISTER-closewater.md` by place before changing the rule.
- **A unit's id is its index in ADM0_A3 order**, in `political.json` and in `countries.png` alike. Adding five
  units (French Guiana and its like) moved every id after them: rebuild both from `build/units.py`, or a click
  on a country opens the card of another one.
- **The water rule's first run in a session takes 0.7 s** (cold code); it is in a worker. Anything else that
  walks the window's grid on the main thread will stall the view the same way.

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

- **EPIC carries two times per frame.** The centroid longitude goes with the time in the image NAME, about five
  minutes after `date`. With `date` the Sun sat 1.1 degrees off in every frame and looked like an ephemeris error.
- **A reference photograph's display values are not radiance.** EPIC's product fits exposure 0.43 and gamma 1.91
  in this shader's units, not sRGB. Fit the display transform to clear ocean, desert and bright cloud FIRST;
  every other comparison is meaningless until then.
- **A thresholded texture does not average to its coverage.** The first cumulus layer went to flat white slabs
  far away and blobs close in. Coverage must go to its mean when a pixel holds many cells.
- **Headless Chromium loses its first GL context under software GL**, and draws tracers at half a second a
  frame. The app reloads itself on context loss; the frozen frame steps tracers without drawing.
- **Any wording change in the dashboard moves all six baseline frames** (the panel is in the screenshot). Look at
  the diff image before accepting: it should be confined to the panel.
- **The kickoff sea-ice witness was four round numbers and was too kind.** Witness values come from the source's
  own files (`Research/modeling/witness/`), never from memory.
- **Blue Marble is a picture, not a reflectance map.** Read as sRGB it gave dark land a third of its brightness,
  and the display transform was then fitted around the error, and cumulus was sized to fill the gap. Three
  compensating errors, each of which scored well. Fit a display transform ONLY to targets whose reflectance
  is known without the atlas (`epic_anchors.py`), then fit the ground (`land_transfer.py --fit`), in that order.
- **One photograph cannot separate ground from cloud.** A composite of 16 days can: keep the third-darkest
  value per pixel, and trust only pixels where most days agree (`epic_clearsky.py`).
- **A match made by construction is not evidence.** Sea-ice extent is solved to NSIDC's mean, so its 0.0% is a
  regression guard. The evidence is the per-year check, which fits nothing.
- **A mean of vectors is not a mean of magnitudes.** Monthly-mean wind is slower than the mean wind speed; the
  median ice edge is not the mean extent; a mean concentration field cleared 15% in a fifth of the years.
- **A big offset eats a coordinate's digits.** Cloud drift was hundreds of turns added to uv; regional zoom
  showed vertical streaks. Keep the fraction of anything periodic before adding it to a texture coordinate.
- **`shader_model.py` is a second copy of the shader.** Its users check it against the shader's own render first.
  Change both together or the clear-sky audit's `instrument_bias` will say so.
- **The headless audits run on software GL, which is more generous than a real GPU.** A seventeenth texture
  sampler linked there (limit 32) and gave a black page on the Mac's own GPU (limit 16, the WebGL2 minimum).
  `check_shaders.py` now counts samplers; the earth shader uses all 16. Open the app in a real browser before
  calling anything done.
- **Cloud amount is not cloud brightness.** Driving the picture by cloud fraction made the Congo twice too bright
  (74% cloud, most of it optically thin). Drive it by reflectance: amount times the reflectance of its thickness.
- **Two references that disagree are telling you about geometry.** VIIRS and ISCCP (nadir, afternoon) and EPIC
  (from the Sun's side) differed by a third in cloud light. Neither was wrong. Check each instrument's absolute
  scale on a known target first (storm tops read 0.95-1.0 in the VIIRS conversion), then look for the physics.
- **Noise in longitude-latitude space is stretched by 1 / cos(latitude).** Generated cloud at 45 N came out four
  times too one-directional. Generate on the sphere (`clumps3`).
- **A threshold on noise gives the cover its quantile curve gives, not the one you asked for.** A straight-line
  rule gave 8% when asked for 20%. Measure the noise's distribution (or cut a rank field, which is uniform).
- **Statistics improving is not the picture improving.** Three cloud versions scored better and looked like pepper,
  cracked mud and paint chips. Read the pairs in `Research/figures/clouds/` every time.
- **Generated texture reads as generated; take shape from the real thing and amount from the model.** Three
  rounds of noise-built cloud never passed for cloud. A real scene reduced to RANKS (each pixel's place among its
  neighbours) answers "which pixels, at this amount?" exactly, and keeps every cell and ragged edge
  (`build/cloud_grain.py`). The exemplar must not be one of the scenes the audit scores against.
- **A resize that reads single points is not an average, and an average of display values is not an average of
  light.** The EPIC audit shrank both pictures 2.3 times that way for two rounds. Shrink by averaging, on
  linear values, and give the instrument a selftest with stripes.
- **A gain that describes a field must not be applied to its resolved pieces.** The Sun-side brightening is a
  concave function of cloud light; applied per pixel it gave less as detail appeared, and the same sky dimmed
  with zoom. Work field-level gains out on the far view's value.
- **A second witness can veto a fix the first one asked for.** VIIRS wanted cumulus spread more evenly; EPIC's
  clear ocean came out 3 levels too bright when it was. Score every change on every instrument before keeping it.
- **Channels of unrelated data in one colour image need full chroma resolution.** WebP's lossy coder halves it
  and cost the cloud grain 4.5% of its range; JPEG with `subsampling=0` costs 1.7%. And fetch sources as PNG:
  a JPEG source's 8 x 8 blocks showed in the atlas's cloud.
- **A mask made from a picture is a mask of the picture.** "Sea is wherever Blue Marble is its ocean fill" classed
  5.3 million km2 of shelf sea as land, because Blue Marble paints every shelf in a colour of its own. It was drawn
  in that colour, so it looked like water for three rounds; the register called it "a strip of Hudson Bay". The
  cache and the shipped file agreed with each other and were both wrong: two instruments from one source are one
  instrument. Measure a mask against a witness that needs no mask (`audit_water.py`: ETOPO below sea level and
  connected to the ocean).
- **I explained the mask's fault before looking, and was wrong.** I wrote that the July picture showed the Arctic
  shelf under ice. The picture's sea is the same in all twelve months. Sample the source's pixels before writing
  why (`fields_surface.step_water` docstring has the corrected account).
- **Fixing a class can take away something true that the error was carrying.** As "land", the Bahama banks were
  turquoise; as water they turned plain blue. Look at before and after side by side at the named places, not only
  at the audit, and carry the true part across (`shoal.webp`).
- **A reanalysis's air over a lake is the lake's own air.** January over the Sea of Azov is +1.2 C in the grid and
  -2 to -4 on its shore. A model of whether the lake freezes must be fed the land's air (`land_air_t0`).
- **A witness built from records must not average over the records it could not read.** Lake seasons with a date
  missing were dropped and open seasons kept; Lake Champlain came out as never freezing. The largest "error" of a
  new model is the first place to check the instrument.
- **A dataset's numbers are not all the same kind of number.** HydroLAKES gives a mean depth for 1.4 million
  lakes; 5700 are measured and the rest are predicted from the slope of the land (`Vol_src`). At face value the
  predicted ones made the drawn lakes worse. Read the provenance column; use a prediction through its regression
  against what you can check (`fields_climate.usable_depth`).
- **An audit that samples a coarse field scores whatever fills the cell.** "Ice at the recorded lake" was the ice
  of the biggest lake in that quarter-degree cell. It did not matter until lakes froze by their own depth; then it
  scored Lake Ontario against a pond's record. Check that the object under the probe is the object in the record.
- **A point in a table is not where the thing is on a coarse map.** A lake's HydroLAKES point is its outlet, up
  to 50 km from the lake as a 5 km mask draws it.
- **Before blaming the texture, check where the light is.** A land-cumulus grain barely moved the Amazon; the
  light had been filed under another kind of cloud and drawn as a few bright clusters. Partition first, then grain.
- **A change to the water mask is a change to everything downstream of it**: sea ice (rebuild `fields_climate.py
  ocean`), ships and lanes (`fields_human.py ships`), and the EPIC audits' own sorting of pixels.
- **A river joins a lake to the sea.** Once the Amazon was water, "water connected to the ocean" ran up it to Peru
  and the water audit scored the whole river as land drawn as sea. Anything that floods from the ocean must be told
  what is river (`data/_cache/river8.npy`, written beside the mask).
- **A product that looks finer may hold nothing more where you are looking.** Three 500 m night products were
  fetched for the inside of Los Angeles; all three are at full scale across the basin. Sample the place the user
  pointed at before designing the rendering around detail the data does not have.
- **A measure that gates is not a measure that ranks.** The shipped lights are Black Marble's warm excess, which
  tells light from moonlit desert but FALLS again where a city turns white. Used as brightness it drew city cores
  darker than suburbs. Close in the warm excess only gates and the green channel ranks (`detail.js nightLight`).
- **One random source for everything means any change reshuffles everything.** Rebuilding the lane field moved 7%
  of the tracer frame's pixels and nothing was wrong. Read the diff image before believing the number.
- **Driving the page by hand does not settle it.** `ATLAS.step()` in a tight loop never satisfies "the camera has
  been still for 350 ms", so the focus window never starts and looks broken. Call `detail.update(cam, true, true,
  sun)` directly and wait on `detail.busy`.
- **A second camera's picture cannot be added to the first's.** Sentinel-2's fine structure, added to the shipped
  Blue Marble month the way Blue Marble's own is, ran past full scale and below zero and the clamp drew a lime
  desert. Join by ratio; and choose the scale of the join by what is under it (5 km inland, coarse near water).
- **Shoot after the fade.** A streamed window fades in over 300 ms of real time; `ATLAS.step()` does not advance
  it. The new source "did not work" at first because the shot was taken at weight 0. Wait 450 ms after `detail.busy`.
- **Coordinates from memory are not landmarks.** Four river asserts and two audit sample points were placed by
  recollection and missed rivers that were there. Find a named feature by its NAME in the vector data.

Plus the standing ones: a process backgrounded with `&` inside a tool call dies when that call
ends; a waiter on a `pgrep` pattern can match itself — wait on a **PID**; a static host can serve
stale JSON after a successful push, so stamp the data version before copying the app file and
verify the live value.
