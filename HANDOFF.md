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

Kickoff is complete and the first build exists. The contract is `SCOPE.md`; the open work is
`Research/MODEL-GAPS.md` (31 items, 6 at P1). The next round is a **verify round**, not a feature round:
the app renders and reads as a planet, and nothing has yet been scored against its reference standard.

<!-- If the user set an explicit loop, state it verbatim and state its stopping condition,
     because a loop overrides the standing "always deploy every round" rule:

> "keep going and making improvements until <condition>. After making updates, compare against
>  <reference>, then assess honestly. If yes, deploy; if no, continue and repeat."
-->

## Reference material and the measurement harness

The comparison is only meaningful at **matched scale**, and getting there takes a while — reuse
this rather than rebuilding it.

- `reference/` (gitignored) is empty. The National Geographic sheet the owner supplied is the Atlas-register baseline:
  measure against it, never reproduce or commit it. NASA EPIC frames for the Space register have not been fetched (A1).

- `ATLAS.step(n)` runs n frames without `requestAnimationFrame`; `await ATLAS.shot('x.jpg', [x,y,w,h])` posts the
  composited frame to `build/serve.py`, which writes `scratchpad/x.jpg` at device resolution. Every state is a URL:
  `#t=2026-07-10T05:30Z&v=globe&s=space&ll=80,22&km=4&lens=temp&on=clouds,air,labels`.
- `build/test_frames.py`, `build/test_app_math.mjs`, `build/check_shaders.py`, and landmark asserts inside every build step.

## State right now

- Last live deploy: **never deployed** (commit `n/a`)
- Committed and not deployed: everything. One local commit ("World Atlas: kickoff and first build")
- Uncommitted: nothing at the time of writing
- `data/` holds 2.6 GB of sources and caches (gitignored); `python build/fetch_sources.py` rebuilds it. `~/.claude/launch.json` has a `world-atlas` preview entry.

## What this round found

All measured, none guessed.

1. **The witness earned its place on day one.** NOAA's long-term-mean sea ice is conditional on ice being present;
   the NSIDC comparison caught a fourfold error that looked plausible on screen. Corrected, with a stated residual (C1).
2. **A population-only gravity model ranks Dhaka above Atlanta.** Air traffic follows catchment income; and catchments
   must be nearest-airport, or Philadelphia inherits New York.
3. **A sea lane is a coherent ridge, not a density.** Tracers on smoothed density swirl over open ocean.
4. **BMNG's ocean is one exact fill colour (2,5,20)**, which gives a water mask registered to the imagery by construction.
5. **The shipping-density lens is the most legible single frame in the atlas**; the default view should perhaps lead with it less shyly.
6. **Verified by looking, at device resolution:** globe and sheet in both registers; the terminator, limb and night lights;
   12-month surface; clouds; wind, current and ship tracers; aircraft; labels; the probe (Agra, July: 30.2 C at 10:40 solar
   time, mean 32.0, 740 people/km2); the dashboard (7.1 bn people in daylight at 09:00 UTC in July; mean July air
   temperature 15.9 C against an observed ~16); the temperature, population and shipping lenses; Today's Earth from GIBS;
   live earthquakes. **Not exercised in a visible browser:** aurora, satellites, search, the About panel, the time console's
   play modes, the country, city, dispute, quake, volcano, plant and airport cards (register G5)

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

Ranked by how much of the remaining gap each closes.

1. **A1** - EPIC side-by-side; this defines "done" for the Space register.
2. **G1** - audit suite + visual ratchet (`/model-verify`).
3. **G5** - click through every card type, the search, About and the play modes in a visible browser; fix what breaks.
4. **C1** - sea ice per year + `audit_ice.py`.
5. **B1** - a real cloud climatology.
6. **A2** - streamed elevation and imagery to reach the 2 km floor.
7. **F1** - label coverage against the baseline sheet

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
