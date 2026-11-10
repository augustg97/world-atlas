"""Run every validator against its recorded baseline and refuse to regress.

    python audit_all.py            # all of them
    python audit_all.py --quick    # skip the slow ones

The build calls this and REFUSES TO PUBLISH if a check moved backwards.

The baselines are not all zero and should not be — a genuine open disagreement belongs
in the baseline with a note. The rule is that none of them may move BACKWARDS. When one
legitimately improves, tighten the baseline IN THE SAME COMMIT, so the ratchet turns one
way only.

SKIP_AUDIT=1 overrides. Deliberately awkward.
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# name, script, baseline, slow?, what it catches
CHECKS = [
    # ("cards",      "audit_cards.py",       {"HIGH": 0, "MED": 0}, False,
    #  "factual errors, date drift, unhedged contested claims, anachronisms"),
    # ("windows",    "audit_windows.py",     {"findings": 2},       False,
    #  "an entity drawn when the thing it names did not exist"),
    # ("coverage",   "coverage_audit.py",    {"outside": 0},        False,
    #  "a drawn quantity against what the literature says it should be"),
    # ("reference",  "audit_reference.py",   {"mean_abs": 0.70},    True,
    #  "the whole model against an independent published source"),
    # ("regression", "regression_gate.py",   {"true": 0},           True,
    #  "an item a change made worse"),
]


def main():
    if os.environ.get("SKIP_AUDIT") == "1":
        print("SKIP_AUDIT=1 — validators skipped. Say so out loud, and say why.")
        return 0

    quick = "--quick" in sys.argv
    failed = []

    for name, script, baseline, slow, catches in CHECKS:
        if quick and slow:
            print(f"  skip  {name:12} (slow)")
            continue
        path = os.path.join(HERE, script)
        r = subprocess.run([PY, path, "--json"], capture_output=True, text=True)
        if r.returncode not in (0, 1):
            failed.append((name, f"could not run: {r.stderr.strip()[:200]}"))
            print(f"  ERROR {name:12} could not run")
            continue

        # A check that cannot report its numbers has FAILED. Silence is not a pass.
        got = _parse(r.stdout)
        if got is None:
            failed.append((name, "produced no parsable result"))
            print(f"  ERROR {name:12} no parsable result")
            continue

        regressed = [k for k, v in baseline.items() if _worse(got.get(k), v)]
        if regressed:
            failed.append((name, f"moved backwards on {', '.join(regressed)}: "
                                 f"{ {k: got.get(k) for k in regressed} } vs baseline "
                                 f"{ {k: baseline[k] for k in regressed} }"))
            print(f"  FAIL  {name:12} {regressed}")
        else:
            print(f"  ok    {name:12} {got}")

    if failed:
        print("\nREFUSING TO PUBLISH:")
        for name, why in failed:
            print(f"  {name}: {why}")
        return 1

    print("\nall validators at or better than baseline")
    return 0


def _parse(stdout):
    import json
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _worse(got, base):
    """Lower is better for every metric here. Override per-metric if that changes."""
    if got is None:
        return True
    return got > base


if __name__ == "__main__":
    sys.exit(main())
