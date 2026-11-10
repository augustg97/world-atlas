"""{{ONE_LINE_PURPOSE}}

A runnable model of one system in this project's subject. Where a research finding could
have been a hand-written table, it is a function with a selftest — so a new input produces
a defensible answer without new authoring.

Design rules (from Modeling Studio/references/RESEARCH-METHOD.md):

  1. STDLIB ONLY, so build/ can import this later without a new dependency.
  2. _selftest() asserts internal consistency and IS the contract. Break one and the
     module tells you.
  3. Confidence is a FIELD, not a footnote: 'good' | 'moderate' | 'contested'.
  4. "Unknown" is a legitimate return — confidence 'none' plus a named fallback band,
     never an invention.
  5. The figures read from this module, so a corrected value propagates automatically.

Run it:

    python {{MODULE_NAME}}.py
"""

from __future__ import annotations


CONFIDENCE = ("good", "moderate", "contested", "none")


# ---------------------------------------------------------------------------
# the catalogue
# ---------------------------------------------------------------------------
# Every entry carries its source and its confidence. An entry whose source is
# "general literature" is a flag, not a citation — put it in the register.

ENTRIES = [
    # {{EXAMPLE}}
    # {"name": "...", "start": 0.0, "end": 0.0, "confidence": "good",
    #  "source": "Author (year), Journal vol, pages",
    #  "note": "what is contested about it, if anything"},
]


# ---------------------------------------------------------------------------
# the interface the app would consume
# ---------------------------------------------------------------------------

def at(t):
    """Return the entry covering time `t`, or an explicit unknown.

    Returning None or a confidence-'none' record is CORRECT where nothing is
    established. Silent fabrication is the failure mode this whole folder exists
    to avoid.
    """
    for e in ENTRIES:
        if e["start"] <= t <= e["end"]:
            return e
    return {"name": None, "confidence": "none",
            "note": f"no established entry at {t}"}


def query(**kwargs):
    """The richer lookup the app actually wants. Keep the signature small and the
    return shape stable — this is a seam the build will depend on."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# selftest — the contract
# ---------------------------------------------------------------------------

def _selftest():
    assert ENTRIES, "catalogue is empty"

    names = [e["name"] for e in ENTRIES]
    assert len(names) == len(set(names)), \
        f"duplicate names: {sorted(n for n in set(names) if names.count(n) > 1)}"

    for e in ENTRIES:
        assert e["confidence"] in CONFIDENCE, f"{e['name']}: bad confidence {e['confidence']!r}"
        assert e.get("source"), f"{e['name']}: no source"
        assert e["start"] <= e["end"], f"{e['name']}: zero or negative span"

    # Tiling: no gaps and no overlaps, if this catalogue is meant to tile time.
    ordered = sorted(ENTRIES, key=lambda e: e["start"])
    for a, b in zip(ordered, ordered[1:]):
        assert a["end"] <= b["start"], f"overlap: {a['name']} / {b['name']}"
        # assert a["end"] == b["start"], f"gap: {a['name']} -> {b['name']}"

    # Cross-catalogue consistency: every member of a group is a known entity,
    # no entity is referenced outside its own window, every enumerated value is valid.
    # These are the assertions that have caught real errors — write them.

    print(f"selftest OK — {len(ENTRIES)} entries")


if __name__ == "__main__":
    _selftest()
    # A worked demonstration: print something that shows the model doing its job,
    # so running the module is itself a check that the answers look sane.
    for t in ():
        print(t, at(t))
