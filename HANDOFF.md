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

Kickoff, the first build, a verify round and two build rounds are done. The contract is `SCOPE.md`; the open
work is `Research/MODEL-GAPS.md` (36 items, 1 open at P1). Against NASA's photographs the Space register is
**close, with named exceptions**. The zoom floor is now met by streamed fields, the sheet names 129 of 198
states, and cloud amount and brightness come from a satellite climatology. What is left at P1 is cloud close
in: it is statistically nearer real cloud than it was and still reads as generated (B1).

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
  distributions. `_r0` is the first build, `_r7` after the verify round, `_r8` and `_r9` after the two build rounds.
- `epic_clearsky.py` builds a cloud-free EPIC composite per frame (third-darkest of about 16 days) and
  scores the atlas with clouds off against it; pairs are `Research/figures/epic/clearsky_*`.
  `epic_anchors.py` fits the display transform; `land_transfer.py` fits and scores the albedo table.
  `epic_render.py <tag> air,daylight,ice` renders with clouds off.
- `cloud_texture.py` scores cloud at 2 km a pixel against VIIRS scenes in five regimes (`cloud_scenes_render.py`
  renders the atlas over the same ground); each number is the excess over the photographs' own day-to-day
  spread. `audit_labels.py` places and tests names on 24 framings.
- **Use the time in EPIC's image name, not its `date` field.** They differ by about five minutes and the
  centroid longitude belongs to the image name: with `date`, the Sun sat 1.1 degrees off in every frame.
- `?frozen=1` gives a deterministic frame (`window.__FRAME_READY`). Six of them are baselines in
  `Research/baselines/frames/`; the manifest is `Research/baselines/frames.json`.
- `ATLAS.step(n)` runs frames without `requestAnimationFrame`; `await ATLAS.shot('x.jpg')` writes
  `scratchpad/x.jpg` at device resolution. Every state is a URL.

## State right now

- Last live deploy: **2026-11-10**, release 1.0; the stamps are in `docs/version.json` and must match the live `version.json`
- Branch `main` is what is published; `verify-round` was merged into it at release 1.0
- `data/` holds about 3.6 GB of sources and caches (gitignored); `python build/fetch_sources.py` rebuilds it,
  including 438 MB of NSIDC grids and 581 MB of ISCCP. Three reference sets live under `reference/`
  (gitignored): `epic/` and `epic/clearsky/` (300 MB) and `gibs_clouds/` (5 MB); each has a `--fetch`.
- `./venv/bin/python Research/modeling/audit_all.py` passes: eleven checks, about 3 min 50 s.
- **The app now talks to two outside hosts when zoomed in** (NASA GIBS, AWS Terrain Tiles), by default, and
  says so in About. Read register A2 before publishing: one line of the tile documentation needs the owner's eye.
- **The earth shader uses 16 of 16 texture units.** See G7.

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

1. **B1** - cloud close in. The instruments exist (`cloud_texture.py`, fifteen VIIRS scenes); the pairs in
   `Research/figures/clouds/` show what is wrong better than the numbers do.
2. **F1** - insets or a key for Europe and the Lesser Antilles; continent names; panels.
3. **A5** - the water mask from bathymetry, then lake ice.
4. **G7** - one audit on a real GPU.
5. **F2** - population by polygon, not by the country raster.

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
