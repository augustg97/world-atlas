"""Run every validator against its recorded baseline and refuse to regress.

    ./venv/bin/python Research/modeling/audit_all.py            # all of them (about four minutes)
    ./venv/bin/python Research/modeling/audit_all.py --quick    # skip the ones that need a browser

A build or a publish calls this and stops if a check moved backwards.

The baselines are not all zero and should not be: a known, stated disagreement belongs in the
baseline with a note. The rule is that none may move BACKWARDS. When one legitimately improves,
tighten the baseline IN THE SAME COMMIT, so the ratchet turns one way only.

The browser checks drive headless Chromium through Playwright, which lives in the Modeling Studio
venv; they need the dev server, which this script starts if nothing is listening on 8150.

SKIP_AUDIT=1 overrides. Deliberately awkward.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PY = os.path.join(ROOT, "venv", "bin", "python")
STUDIO = os.path.expanduser("~/Modeling Studio")
SPY = os.path.join(STUDIO, ".venv", "bin", "python")
PORT = 8150
M = lambda f: os.path.join(HERE, f)
B = lambda f: os.path.join(ROOT, "build", f)

# name, commands (each run in order; the LAST one reports), baseline, needs a browser?, what it catches.
# A baseline of {"failures": 0} means "the command must exit 0". Every other metric: lower is better.
CHECKS = [
    ("frames", [[PY, B("test_frames.py")]], {"failures": 0}, False,
     "a source converted into the canonical frame shifted, flipped or mis-registered"),
    ("app-math", [["node", B("test_app_math.mjs")]], {"failures": 0}, False,
     "Sun and Moon against the almanac and against NASA EPIC's own vectors; projection and camera round trips"),
    ("shaders", [[PY, B("check_shaders.py")]], {"failures": 0}, False,
     "a shader that does not compile (the black canvas with working panels)"),
    ("selftests", [[PY, M("epic_compare.py"), "--selftest"], [PY, M("audit_ice.py"), "--selftest"], [PY, M("audit_population.py"), "--selftest"]],
     {"failures": 0}, False, "an audit that has stopped measuring what it says it measures"),
    # Known overshoot, register C1: the 1991-2020 mean concentration field against NSIDC's mean extent.
    ("sea-ice", [[PY, M("audit_ice.py"), "--json"]],
     {"arctic_max_over_pct": 31.5, "antarctic_max_over_pct": 93.5, "mean_abs_pct": 29.3}, False,
     "sea-ice extent drifting further from the NSIDC Sea Ice Index"),
    # 26 units differ by more than 10% (vintage, small islands, city states); register F2 lists them.
    ("population", [[PY, M("audit_population.py"), "--json"]], {"units_off_10pct": 26, "total_err_pct": 0.37}, False,
     "the population field against World Bank national totals"),
    # 21 of 204 states are named at the whole-Earth sheet framing; the baseline sheet names all. Register F1.
    ("labels", [[SPY, M("audit_labels.py"), "--json"]], {"sheet_states_unnamed": 183}, True,
     "label coverage at the whole-Earth framing falling further below the baseline sheet"),
    # Eight NASA EPIC frames, software GL. Register A1 holds the per-frame table and what each number means.
    ("epic", [[SPY, M("epic_render.py"), "cur"], [PY, "-W", "ignore", M("epic_compare.py"), "--tag", "cur", "--json", "--no-figures"]],
     {"lum_err": 6.96, "contrast_err": 3.47, "white_err": 0.042, "limb_err": 0.063, "ocean_rgb_err": 4.6,
      "land_rgb_err": 15.9, "halo_err": 0.15, "glint_err": 0.17, "epic_shift_px": 2}, True,
     "the lit globe moving away from the photograph: exposure, contrast, cloud, limb, ocean, ground, glint"),
    ("visual", [[SPY, os.path.join(STUDIO, "tools", "frame_baseline.py"), "check", "--project", ROOT]], {"failures": 0}, True,
     "any of the six canonical frames changing without a recorded reason (Research/baselines/FRAME-LOG.md)"),
]
TOL = 1e-9


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    if os.environ.get("SKIP_AUDIT") == "1":
        print("SKIP_AUDIT=1 - validators skipped. Say so out loud, and say why.")
        return 0

    quick = "--quick" in sys.argv
    failed, server = [], None
    if not quick and not listening(PORT):
        server = subprocess.Popen(["/usr/bin/python3", B("serve.py"), str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if listening(PORT):
                break
            time.sleep(0.1)
        else:
            print("  ERROR could not start the dev server; the browser checks cannot run")
            return 1
    try:
        for name, cmds, baseline, browser, catches in CHECKS:
            if quick and browser:
                print(f"  skip  {name:11} (needs a browser)")
                continue
            t0 = time.time()
            r = None
            for cmd in cmds:
                r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                if r.returncode != 0:
                    break
            if list(baseline) == ["failures"]:
                got = {"failures": 0 if r.returncode == 0 else 1}
                if r.returncode != 0:
                    tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
                    failed.append((name, "failed:\n      " + "\n      ".join(tail)))
                    print(f"  FAIL  {name:11} exit {r.returncode}")
                    continue
            else:
                # A check that cannot report its numbers has FAILED. Silence is not a pass.
                got = _parse(r.stdout) if r.returncode == 0 else None
                if got is None:
                    failed.append((name, f"could not run or produced no parsable result: {(r.stderr or r.stdout).strip()[-400:]}"))
                    print(f"  ERROR {name:11} no result")
                    continue
            regressed = [k for k, v in baseline.items() if _worse(got.get(k), v)]
            better = [k for k, v in baseline.items() if got.get(k) is not None and got[k] < v - TOL]
            if regressed:
                failed.append((name, "moved backwards on " + ", ".join(f"{k}: {got.get(k)} (baseline {baseline[k]})" for k in regressed)))
                print(f"  FAIL  {name:11} {regressed}")
            else:
                shown = {k: got.get(k) for k in baseline}
                note = f"   <- improved on {better}: tighten the baseline in this commit" if better else ""
                print(f"  ok    {name:11} {shown}  ({time.time() - t0:.0f}s){note}")
    finally:
        if server:
            server.terminate()

    if failed:
        print("\nREFUSING TO PUBLISH:")
        for name, why in failed:
            print(f"  {name}: {why}")
        return 1
    print("\nall validators at or better than baseline")
    return 0


def _parse(stdout):
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _worse(got, base):
    """Lower is better for every metric here."""
    if got is None:
        return True
    return got > base + TOL


if __name__ == "__main__":
    sys.exit(main())
