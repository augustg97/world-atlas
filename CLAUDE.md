# World Atlas — instructions for Claude sessions

A living atlas of the present-day Earth: one year of the planet and its people, composed per pixel and anchored at now.

**Read `README.md` first** — §1 (what this is trying to be), §2 (the working rules), §7 (traps),
§9 (known limits). Then `SCOPE.md` for the contract and `HANDOFF.md` for the live state.

The general protocol lives in `/Users/augustgweon/Modeling Studio`. Its skills apply here:
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
   push, and a check of the live data-version stamp. *(Suspended here by rule 16 until the owner
   decides to publish: rounds end with `audit_all.py` green and a local commit.)*

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
16. **Do not publish.** `docs/` and GitHub Pages are the owner's explicit decision; ask before any push.

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
./venv/bin/python build/fields_surface.py       # water albedo elev night clouds   (albedo:7 = one month)
./venv/bin/python build/fields_climate.py       # atmo ocean currents
./venv/bin/python build/fields_human.py         # pop ships lanes co2 countries
./venv/bin/python build/vectors.py              # political places physical plates quakes volcanoes power stats air

# the whole audit suite against its baselines (eleven checks, 3-4 min; --quick skips the browser checks)
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
# the visual ratchet alone; accept a moved frame only with a reason
"$HOME/Modeling Studio/.venv/bin/python" "$HOME/Modeling Studio/tools/frame_baseline.py" check --project .

# look at a frame at full resolution (the browser pane may be hidden or scaled)
#   in the page:  ATLAS.step(200); await ATLAS.shot('name.jpg')   ->  scratchpad/name.jpg
```

## Traps that have each cost real time here

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
  rule gave 8% when asked for 20%. Measure the noise's distribution (`cutFor`).
- **Statistics improving is not the picture improving.** Three cloud versions scored better and looked like pepper,
  cracked mud and paint chips. Read the pairs in `Research/figures/clouds/` every time.
- **`water4.npy` and `water.webp` say south-west Hudson Bay is land.** They agree with each other and are both
  wrong (register A5). Two instruments from one source are one instrument.

Plus the standing ones: a process backgrounded with `&` inside a tool call dies when that call
ends; a waiter on a `pgrep` pattern can match itself — wait on a **PID**; a static host can serve
stale JSON after a successful push, so stamp the data version before copying the app file and
verify the live value.
