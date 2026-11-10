# Research — present-day Earth systems knowledge base for World Atlas

**Started 2026-11-09.** A standing research programme and expert system covering the six systems the atlas tracks: Sun and orbit, atmosphere, ocean, solid Earth, biosphere and humanity.

**This folder does not change the model.** Nothing here is imported by `build/`. Its output is
*evidence and models* that inform continuous updates to the app — so that when a number, a
boundary, a label or a card changes, the change has a citation and a mechanism behind it rather
than a guess.

---

## How it is organised

```
Research/
├── SOURCE-SURVEY.md              what data exists, in what frame, under what licence
├── MODEL-GAPS.md                 the register that ties research to app defects
├── research/                     evidence: dossiers per domain, with sources and caution flags
│   ├── 01-atmosphere/
│   └── 09-source-documents/      fetched primary material, kept verbatim
├── research reports/             illustrated white papers, each ending in actions
│   └── STAGED-CHANGES.md         the handover surface
├── modeling/                     runnable models + read-only audits
└── figures/
    ├── authored/                 generated FROM the models, so they cannot drift
    └── collected/                third-party + MANIFEST.json (licence + review verdict)
```

---

## The models

All runnable, all self-testing. Each prints a worked demonstration.

```bash
cd Research/modeling && python audit_all.py
```

| module | what it is | current state |
|---|---|---|
| | | selftest passes |

## The audits

Read-only; they change nothing.

| script | catches | current result |
|---|---|---|
| | | |

## The dossiers

| file | covers |
|---|---|
| | |

## The white papers

| paper | thesis |
|---|---|
| | |

---

## Working method

1. **Verify, don't reconstruct from memory.** Every claim traces to a named source; where a
   fetched source is internally inconsistent, the dossier says so rather than propagating it.
2. **Say what is contested.** A card that states an open question flatly misrepresents how well
   it is known.
3. **Prefer a model to a table.** Every finding that could be a hand-written row is written as a
   function with a selftest, so a new input produces a defensible answer without new authoring.
4. **Figures are generated, not drawn.** They read from the same modules, so a corrected value
   propagates automatically.
5. **Every white paper ends in actions**, and every action lands in `MODEL-GAPS.md`.

---

## Status

**Round 0 (kickoff), 2026-11-09.**

*Round 0* — `SOURCE-SURVEY.md` (every source fetched, its frame and licence, what was refused and why) and `MODEL-GAPS.md` (31 open items). No dossiers, white papers or audits exist yet; the build's own tests (`build/test_frames.py`, `build/test_app_math.mjs`) are the only instruments.

All selftests pass. See [`MODEL-GAPS.md`](MODEL-GAPS.md) for the **0 open items**,
6 at P1.

**Next round, in priority order:** 
1. **A1** - fetch NASA EPIC reference frames into `reference/` and score the lit globe against them, side by side.
2. **G1** - turn the checks that exist into `audit_all.py` and add the visual ratchet (`tools/frame_baseline.py`).
3. **C1** - rebuild sea ice from yearly files and write `audit_ice.py` against the NSIDC Sea Ice Index.
4. **B1** - find a shippable satellite cloud climatology; white paper on what the cloud layer can honestly claim.
5. **F2, F3** - population and air-traffic witnesses.
