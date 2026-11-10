"""Audit {{WHAT}} against {{THE_STANDARD}}.

READ-ONLY. It imports the app's own data, checks it against the catalogues and models
in this folder, and writes a discrepancy register. It changes nothing.

    python {{MODULE_NAME}}.py                 # print the register
    python {{MODULE_NAME}}.py --md out.md     # write markdown
    python {{MODULE_NAME}}.py --selftest      # run on synthetic input

Rules this file must keep (Modeling Studio/references/AUDIT-PATTERNS.md):

  * READ THE ARTIFACT THE PIPELINE READS. An audit that independently rebuilds the
    thing it audits will miss the last transformation. This has happened twice, both
    times to an audit whose own docstring said it existed to avoid exactly that.
  * NO BARE except. A try/except around a guard INVERTS it: the failure mode of a
    check that throws is silence, and silence reads as "passed". If a guard cannot
    run, raise.
  * EARN EACH CHECK. A check that fires on things that are fine trains everyone to
    ignore the whole audit.
  * MEASURE WHAT IS DRAWN, not what is input. A parameter table is a claim about the
    output; check the output.

Severity: HIGH = factually wrong or misleading · MED = incomplete or over-confident
· LOW = polish.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
sys.path.insert(0, BUILD)


# ---------------------------------------------------------------------------
# load the app's own data — never a copy, or the audit passes while the app is wrong
# ---------------------------------------------------------------------------

def load_subject():
    """Return exactly what the app ships, from where the app ships it."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------

def check_coverage(subject, findings):
    """A catalogued thing that nothing in the app mentions."""


def check_dates(subject, findings):
    """A window that disagrees with the catalogue."""


def check_contested(subject, findings):
    """A genuinely open question stated flatly."""


def check_anachronism(subject, findings):
    """Vocabulary that postdates its own window.

    A table of (term, not_before, not_after). This catches the single most common
    class of error in a historical model: a word from the wrong century.
    """


CHECKS = [check_coverage, check_dates, check_contested, check_anachronism]


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run():
    subject = load_subject()
    findings = []
    for check in CHECKS:
        check(subject, findings)          # NOT wrapped in try/except — see the docstring
    return findings


def _selftest():
    """Run every check on synthetic input with a known answer.

    Two of the prior project's audits found their own bugs here before they ever ran
    on real data. This function is not optional.
    """
    print("selftest OK")


def _report(findings):
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: order.get(f.get("severity", "LOW"), 9))
    for f in findings:
        print(f"{f['severity']:4}  {f['check']:12}  {f['what']}\n      {f['detail']}")
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("HIGH", "MED", "LOW")}
    print(f"\n{len(findings)} findings — "
          f"{counts['HIGH']} HIGH / {counts['MED']} MED / {counts['LOW']} LOW")
    return counts


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        _selftest()
        counts = _report(run())
        # Non-zero exit on a HIGH so this can gate a build.
        sys.exit(1 if counts["HIGH"] else 0)
