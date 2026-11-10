# Handoff — World Atlas

Paste this whole file as the first message of a new session.

---

## What you are working on

**World Atlas** — A living atlas of the present-day Earth: one year of the planet and its people, composed per pixel and anchored at now.

- Repo: `/Users/augustgweon/World Atlas` (never under `~/Desktop` or `~/Documents`: macOS TCC)`
- Live: not published. Local: `python3 build/serve.py 8150` -> http://localhost:8150. **Publishing is the owner's explicit decision; ask first.**
- **Read `README.md` first.** It documents the goals, the standing working rules (§2), every
  subsystem, the traps that have cost time (§7), and the known limits (§9).
- `SCOPE.md` is the contract: the claim, the layer table, the canonical frame, the evidence
  boundary, the card contract, the standard for done, the non-goals.

## The current task

Kickoff, the first build and one verify round are done. The contract is `SCOPE.md`; the open work is
`Research/MODEL-GAPS.md` (34 items, 4 open at P1). The Space register has now been scored against its
reference and the answer is **not yet**: colour, exposure, ocean, desert and the limb sit within a few
display levels of NASA's photographs; cloud and vegetated land do not. The next round is a **build round**
on those two (B1, A7) and on sea ice (C1).

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
  pairs to `Research/figures/epic/`. `epic_cloud_cdf.py <tag> [--land]` compares cloud brightness
  distributions. `_r0` is before this round, `_r7` after.
- **Use the time in EPIC's image name, not its `date` field.** They differ by about five minutes and the
  centroid longitude belongs to the image name: with `date`, the Sun sat 1.1 degrees off in every frame.
- `?frozen=1` gives a deterministic frame (`window.__FRAME_READY`). Six of them are baselines in
  `Research/baselines/frames/`; the manifest is `Research/baselines/frames.json`.
- `ATLAS.step(n)` runs frames without `requestAnimationFrame`; `await ATLAS.shot('x.jpg')` writes
  `scratchpad/x.jpg` at device resolution. Every state is a URL.

## State right now

- Last live deploy: **never deployed**
- Committed locally and not pushed: everything, three commits
- `data/` holds 2.6 GB of sources and caches (gitignored); `python build/fetch_sources.py` rebuilds it.
  `~/.claude/launch.json` has a `world-atlas` preview entry.
- `./venv/bin/python Research/modeling/audit_all.py` passes: nine checks, 2 min 19 s.

## What the verify round found

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

See `CLAUDE.md` - eight traps, each with what it cost.

Plus the standing ones:

- a process backgrounded with `&` inside a tool call dies when that call ends; `nohup` does not
  save it. The tell is a log that stops after one line.
- `pgrep -f <script>` matches the waiter's own command line. **Wait on a PID** —
  `until ! kill -0 "$PID"`.
- a static host can serve stale JSON after a successful push. Stamp the data version **before**
  copying the app file, and verify the live value.

## The work queue

1. **B1 + A7** - cloud that resolves below 10 km, a satellite cloud climatology for coverage, and why
   vegetated land reads dark (build a clear-sky EPIC composite first; do not tune to it blind).
2. **C1** - sea ice from NSIDC's yearly concentration grids (needs a polar-stereographic `frames` conversion).
3. **A2** - streamed elevation and imagery to reach the 2 km floor.
4. **F1** - label placement: 21 of 204 states today.
5. **F2** - population by polygon, not by the country raster.

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
