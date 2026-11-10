"""Run every validator against its recorded baseline and refuse to regress.

    ./venv/bin/python Research/modeling/audit_all.py            # all eleven (about three and a half minutes)
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
    ("selftests", [[PY, "-W", "ignore", M("epic_compare.py"), "--selftest"], [PY, "-W", "ignore", M("epic_clearsky.py"), "--selftest"], [PY, "-W", "ignore", M("cloud_texture.py"), "--selftest"],
                   [PY, M("audit_ice.py"), "--selftest"], [PY, M("audit_population.py"), "--selftest"], [PY, "-W", "ignore", B("cloud_grain.py"), "--selftest"]],
     {"failures": 0}, False, "an audit that has stopped measuring what it says it measures"),
    # Rebuilt from NSIDC's 720 monthly grids (register C1). The edge is PLACED so the extent matches NSIDC's
    # mean, so these three are a regression guard, not evidence; the evidence is the per-year check the
    # build asserts (fields_climate.step_ocean) and audit_ice.py --peryear. Ice AREA is not solved for:
    # mean concentration inside the edge is diluted by open years, up to 15.5% under in Antarctic February.
    ("sea-ice", [[PY, M("audit_ice.py"), "--json"]],
     {"arctic_max_over_pct": 0.1, "antarctic_max_over_pct": 0.0, "mean_abs_pct": 0.0, "area_max_under_pct": 15.5}, False,
     "sea-ice extent or area drifting from the NSIDC Sea Ice Index"),
    # 26 units differ by more than 10% (vintage, small islands, city states); register F2 lists them.
    ("population", [[PY, M("audit_population.py"), "--json"]], {"units_off_10pct": 26, "total_err_pct": 0.37}, False,
     "the population field against World Bank national totals"),
    # Names of states, as the label layer actually placed them, on 24 framings and in the sheet's two insets
    # (register F1). The count of states is 198 (193 UN members plus Vatican, Taiwan, Kosovo, N. Cyprus,
    # Somaliland). overlaps, under_9px, misplaced (a name mostly on another country, tested against geometry),
    # hit_wrong and under_panel must stay ZERO: coverage bought with any of them is not coverage.
    # THE COUNT CHANGED MEANING on 2026-11-10 (third round), and the numbers before it do not compare. Names
    # are no longer placed under the panels, and a state whose own ground is under a panel is counted `hidden`,
    # not unnamed. By the old count the whole-Earth sheet named 129, 22 of them under the dashboard where no
    # one could read them. By the new one it named 106 of 176 in view and now names 125 of 177 (107 on the map,
    # 18 more in the insets). Of all 198: 73 unnamed, 21 of those hidden.
    ("labels", [[SPY, M("audit_labels.py"), "--selftest"], [SPY, M("audit_labels.py"), "--json"]],
     {"sheet_states198_unnamed": 52, "globe_states198_unnamed": 59, "regional12_states198_unnamed": 300, "regional6_states198_unnamed": 38,
      "overlaps": 0, "under_9px": 0, "misplaced": 0, "hit_wrong": 0, "under_panel": 0, "sheet_drag_flips": 0, "sheet_zoom_in_losses": 4}, True,
     "states losing their names, or names overlapping, shrinking below 9 px or landing on the wrong country"),
    # Eight NASA EPIC frames, software GL. Register A1 holds the per-frame table and what each number means.
    # limb_err rose from 0.063 to 0.103 in the build round and that is a CANCELLATION, recorded in A1: the old
    # frame matched the ring-to-centre ratio because the whole outer disc was 5-15 levels dim. disc_err is the
    # measure that sees it (9.3 before, on the same renders).
    ("epic", [[SPY, M("epic_render.py"), "cur"], [PY, "-W", "ignore", M("epic_compare.py"), "--tag", "cur", "--json", "--no-figures"]],
     # RE-SET 2026-11-10 (second build round), five of them BACKWARDS, on purpose and written down in MODEL-GAPS
     # (APPLIED, second build round): lum_err 1.94 -> 2.47, white_err 0.015 -> 0.018, limb_err 0.103 -> 0.107,
     # ocean_rgb_err 4.9 -> 5.1, land_rgb_err 13.1 -> 13.8. The old values came from a cloud opacity curve fitted
     # to these very photographs. Cloud light now comes from ISCCP and is confirmed by VIIRS; EPIC is no longer
     # what it is tuned to.
     # RE-SET AGAIN 2026-11-10 (third round), in two steps, both in MODEL-GAPS (APPLIED, third round).
     # 1. THE INSTRUMENT. to_common() shrank both pictures 2.3 times by reading single points, and averaged in
     #    display values; it now averages light over each common pixel. The SAME renders as the last baseline
     #    (tag r9) score on it: 2.63, 1.68, 0.021, 4.17, 0.105, 5.7, 13.1, halo 0.20, glint 0.11.
     # 2. THE MODEL (cloud grain; sheet light from ISCCP). Against those: contrast 1.68 -> 1.54, disc 4.17 -> 4.13
     #    and ocean 5.7 -> 5.0 better; lum 2.63 -> 2.66, white 0.021 -> 0.027, limb 0.105 -> 0.118, land 13.1 -> 13.2
     #    and glint 0.11 -> 0.13 WORSE. Classified TRUE, small: sheet cloud was a third brighter than ISCCP says
     #    (and 0.12 brighter than VIIRS off Peru); at ISCCP's figure the two December frames, already 2-6 points
     #    short of EPIC's white share, are a point or two shorter. The old excess was covering for that.
     {"lum_err": 2.66, "contrast_err": 1.54, "white_err": 0.027, "disc_err": 4.13, "limb_err": 0.118, "ocean_rgb_err": 5.0,
      "land_rgb_err": 13.2, "halo_err": 0.2, "glint_err": 0.13, "epic_shift_px": 2}, True,
     "the lit globe moving away from the photograph: exposure, contrast, cloud, the disc profile, ocean, ground, glint"),
    # The ground alone: clouds off, against a cloud-free composite of about a hundred EPIC frames (register A7).
    # Needs reference/epic/clearsky (epic_clearsky.py --fetch, 300 MB). instrument_bias is the numpy copy of the
    # shader against the shader's own render: if it grows, shader_model.py has drifted and nothing here means anything.
    ("clear-sky", [[SPY, M("epic_render.py"), "clr", "air,daylight,ice"], [PY, "-W", "ignore", M("land_transfer.py"), "--json"]],
     {"instrument_bias": 1.1, "clearsky_land_abs": 5.0, "clearsky_land_bias": 0.7}, True,
     "the cloud-free ground moving away from EPIC's, or the audit's copy of the shader drifting from the shader"),
    # Cloud at the zoom floor: five regimes at 2 km a pixel against three VIIRS days each (register B1). Each
    # number is how far the atlas sits OUTSIDE the day-to-day spread of the photographs, summed over the
    # regimes: 0 would mean indistinguishable by that measure. Needs reference/gibs_clouds (cloud_texture.py
    # --fetch, 5 MB). Before the cloud-kinds round these were 1.005, 0.453, 0.558, 0.078; after it 0.621, 0.052,
    # 0.423, 0.026. Third round (cloud grain from real scenes): three better, and CONTRAST BACKWARDS, 0.026 -> 0.088,
    # re-set on purpose. By scene: North Atlantic and SE Pacific now inside the photographs' spread; Amazon, Congo
    # and trades outside it by 0.02-0.03 each. Congo is PRE-EXISTING (0.14 too much light there in both states;
    # resolved pieces show it where flat grey ones hid it). Amazon and trades are TRUE: fewer, larger, brighter
    # pieces than the real fine cumulus. Amazon's size spectrum also went backwards (bands 0.38 -> 0.53). In B1.
    ("cloud-texture", [[SPY, M("cloud_scenes_render.py"), "cur"], [PY, "-W", "ignore", M("cloud_texture.py"), "--tag", "cur", "--json"]],
     {"texture_bands_excess": 0.226, "texture_aniso_excess": 0.032, "texture_cover_excess": 0.254, "texture_contrast_excess": 0.088}, True,
     "close-in cloud drifting from real cloud's grain, direction, cover or contrast"),
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
