"""Close in, is the atlas's water where the water is? (register A12)

Inside the streamed window the app decides land or water texel by texel (web/js/detail.js :: waterFlag): NASA's
MODIS mask says roughly where, the streamed picture's colour says exactly where. This scores that rule, THE
APP'S OWN FUNCTION run under node, at 23 places against a witness none of its inputs come from: JRC Global
Surface Water (Landsat, 30 m, 1984-2021; water = water at least half the time). Fetch the set once with
closewater_fetch.py.

    wrong_pct        texels the rule gets wrong (water called land or land called water), mean over the 23, percent
    iou_short_pct    100 x (1 - intersection over union of the rule's water and the witness's), mean over the 23
    worse_than_mask  places where the rule is wrong on more texels than the MODIS mask alone (by over 0.4 points),
                     at 19 m or at any of four coarser texels (76, 152, 304, 494 m: the picture pooled, as a
                     wider view streams it)
    manhattan_false_pct   land the rule calls water at Manhattan, where the mask holds most of the island as water
                     (15% of the box); the worst of the five texel sizes
The MODIS mask alone and the shipped 5 km field are scored beside it, for scale.

WHAT THIS DOES NOT CHECK. The weights of the rule's first guess were fitted to these 23 places (the fit, with
each half scored by the other half's weights, gave 2.80% wrong against 2.77% with all: the fit is not what the
number rests on). The grids are built here (nearest terrain texel, the mask's nearest cell); the app builds its
own from the same tiles (elevation area-averaged and despiked, the picture drawn down by the browser). The
Blue Marble windows (0.5 km and coarser) are not scored at all: the pooled grids here are Sentinel-2's colours.
And the witness is a 38-year record against one 2016 picture: a reservoir that fell (Lake Mead) and tidal flats
(Venice, Chittagong) are counted against the rule where it follows the picture.

    ./venv/bin/python Research/modeling/audit_closewater.py [--json] [--register]
    ./venv/bin/python Research/modeling/audit_closewater.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "reference", "closewater")
POOLS = (1, 4, 8, 16, 26)                 # 19, 76, 152, 304, 494 m
MARGIN = 0.4                              # points of texels: under this the rule and the mask are a tie


def pool(a, k):
    if k == 1:
        return a
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:h, :w].reshape(h // k, k, w // k, k, *a.shape[2:]).astype(np.float32).mean(axis=(1, 3))


def run_rule(jobs):
    """jobs: [{name, rgb (h, w, 3 uint8), elev (h, w), mask (h, w bool), mx, my, cell, noPicture?}] -> {name: flag (h, w bool)}, through node."""
    with tempfile.TemporaryDirectory() as d:
        meta = []
        for j in jobs:
            h, w = j["mask"].shape
            rgba = np.dstack([j["rgb"], np.full((h, w), 255, np.uint8)]).astype(np.uint8)
            rgba.tofile(os.path.join(d, f"{j['name']}.rgba")); j["elev"].astype("<f4").tofile(os.path.join(d, f"{j['name']}.elev")); j["mask"].astype(np.uint8).tofile(os.path.join(d, f"{j['name']}.mask"))
            if j.get("ship") is not None:
                j["ship"].astype("<f4").tofile(os.path.join(d, f"{j['name']}.ship"))
            meta.append(dict(name=j["name"], w=w, h=h, mx=float(j["mx"]), my=float(j["my"]), cell=float(j["cell"]), noPicture=bool(j.get("noPicture")), ship=j.get("ship") is not None))
        json.dump(meta, open(os.path.join(d, "jobs.json"), "w"))
        r = subprocess.run(["node", os.path.join(ROOT, "build", "closewater_flags.mjs"), d], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"the app's rule did not run: {(r.stderr or r.stdout).strip()[-600:]}")
        done = {m["name"]: m for m in json.load(open(os.path.join(d, "done.json")))}
        return {m["name"]: np.fromfile(os.path.join(d, f"{m['name']}.flag"), np.uint8).reshape(m["h"], m["w"]).astype(bool) for m in meta}, done


def score(flag, truth):
    fw = float((flag & ~truth).mean()); mw = float((~flag & truth).mean())
    return fw, mw, float((flag & truth).sum() / max(1, (flag | truth).sum()))


_SHIP = None


def shipped_water(lons, lats):
    """The shipped water fraction (web/fields/water.webp, 5 km), bilinear, 0..1: what the app's own sampler returns."""
    global _SHIP
    from scipy import ndimage as nd
    if _SHIP is None:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        _SHIP = np.asarray(Image.open(os.path.join(ROOT, "web", "fields", "water.webp")).convert("RGB"))[..., 0].astype(np.float32)
    H, W = _SHIP.shape
    X, Y = np.meshgrid((lons + 180) / 360 * W - 0.5, (90 - lats) / 180 * H - 0.5)
    return nd.map_coordinates(_SHIP, [Y, X], order=1, mode="nearest") / 255


def audit():
    names = sorted(f[:-4] for f in os.listdir(REF) if f.endswith(".npz")) if os.path.isdir(REF) else []
    if len(names) < 23:
        raise SystemExit(f"audit_closewater: the reference set is not there ({len(names)} of 23 places in reference/closewater). Run Research/modeling/closewater_fetch.py")
    data = {n: np.load(os.path.join(REF, f"{n}.npz")) for n in names}
    jobs, truth, maskp = [], {}, {}
    for n in names:
        d = data[n]; ship = shipped_water(d["lons"], d["lats"])
        for k in POOLS:
            key = f"{n}@{k}"
            m = pool(d["mask"].astype(np.float32), k) > 0.5
            truth[key] = pool(d["truth"].astype(np.float32), k) > 0.5; maskp[key] = m
            jobs.append(dict(name=key, rgb=np.clip(np.round(pool(d["s2"], k)), 0, 255).astype(np.uint8), elev=pool(d["elev"], k), mask=m, ship=pool(ship, k),
                             mx=float(d["mx"]) * k, my=float(d["my"]) * k, cell=max(1.0, 250.0 / (float(d["my"]) * k))))
    flags, done = run_rule(jobs)
    rows, worse = [], []
    for n in names:
        d = data[n]; key = f"{n}@1"
        r = score(flags[key], truth[key]); m = score(maskp[key], truth[key]); s = score(shipped_water(d["lons"], d["lats"]) > 0.5, truth[key])
        rows.append(dict(name=n, water=float(truth[key].mean()), rule=r, mask=m, shipped=s, ms=done[key]["ms"], seeds=done[key].get("seedWater")))
        for k in POOLS:
            kk = f"{n}@{k}"; a = score(flags[kk], truth[kk]); b = score(maskp[kk], truth[kk])
            if 100 * (a[0] + a[1]) > 100 * (b[0] + b[1]) + MARGIN:
                worse.append(f"{n} at {19 * k} m: {100 * (a[0] + a[1]):.1f}% against {100 * (b[0] + b[1]):.1f}%")
    mean = lambda f: float(np.mean([f(r) for r in rows]))
    by_pool = {19 * k: 100 * float(np.mean([sum(score(flags[f"{n}@{k}"], truth[f"{n}@{k}"])[:2]) for n in names])) for k in POOLS}
    man = max(100 * score(flags[f"manhattan@{k}"], truth[f"manhattan@{k}"])[0] for k in POOLS)
    summary = dict(manhattan_false_pct=round(man, 1), wrong_pct=round(100 * mean(lambda r: r["rule"][0] + r["rule"][1]), 2), iou_short_pct=round(100 * (1 - mean(lambda r: r["rule"][2])), 1), worse_than_mask=len(worse),
                   mask_wrong_pct=round(100 * mean(lambda r: r["mask"][0] + r["mask"][1]), 2), shipped_wrong_pct=round(100 * mean(lambda r: r["shipped"][0] + r["shipped"][1]), 2),
                   mask_iou=round(mean(lambda r: r["mask"][2]), 3), shipped_iou=round(mean(lambda r: r["shipped"][2]), 3), rule_iou=round(mean(lambda r: r["rule"][2]), 3),
                   false_water_pct=round(100 * mean(lambda r: r["rule"][0]), 2), missed_water_pct=round(100 * mean(lambda r: r["rule"][1]), 2),
                   by_texel_m={k: round(v, 2) for k, v in by_pool.items()}, slowest_ms=max(r["ms"] for r in rows))
    return summary, rows, worse


def register(summary, rows, worse):
    L = ["# Close in: land or water (register A12)", "",
         "The app's rule (`web/js/detail.js :: waterFlag`, run under node) at 23 places, 19 m a texel, against JRC Global Surface Water (30 m, water at least half of 1984-2021).",
         "Wrong = texels called water that are land, plus texels called land that are water, as a share of all texels in the box.", "",
         "| place | water | rule: false | missed | IoU | MODIS alone: wrong | IoU | shipped 5 km: wrong | IoU |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {100 * r['water']:.1f}% | {100 * r['rule'][0]:.1f}% | {100 * r['rule'][1]:.1f}% | {r['rule'][2]:.2f} | {100 * (r['mask'][0] + r['mask'][1]):.1f}% | {r['mask'][2]:.2f} | {100 * (r['shipped'][0] + r['shipped'][1]):.1f}% | {r['shipped'][2]:.2f} |")
    L += [f"| **mean** | | {summary['false_water_pct']}% | {summary['missed_water_pct']}% | {summary['rule_iou']:.2f} | {summary['mask_wrong_pct']}% | {summary['mask_iou']:.2f} | {summary['shipped_wrong_pct']}% | {summary['shipped_iou']:.2f} |", "",
          "Wrong texels by texel size (the picture pooled): " + ", ".join(f"{k} m {v}%" for k, v in summary["by_texel_m"].items()) + ".",
          f"Places where the rule is worse than the mask alone at any texel size: {len(worse)}" + (": " + "; ".join(worse) if worse else "") + ".",
          f"Slowest place: {summary['slowest_ms']} ms for about a million texels.", "",
          "Read the low rows for what they are. Paris, Lyon, Cremona, Dhaka, Zermatt: rivers and tarns MODIS has little or none of; the rule adds no water there by design. Manhattan: MODIS holds most of the island as water and the rule takes it back. Port Said, Venice, Chittagong, Lake Mead: salt pans, tidal flats and a fallen reservoir, where a 38-year record and one 2016 picture are different things."]
    open(os.path.join(os.path.dirname(__file__), "REGISTER-closewater.md"), "w").write("\n".join(L) + "\n")


def selftest():
    """A made scene with a known answer, through the same node path: sea west of a coast the mask places 8 texels
    too far east, a block of roofs the mask calls water, a lake of the sea's colour the mask does not have,
    and a pond of a colour no water the mask knows has."""
    rng = np.random.default_rng(3)
    h, w = 300, 400
    roofs = lambda a, b: np.array([150, 145, 140]) + rng.normal(0, 30, (a, b, 1)) + rng.normal(0, 6, (a, b, 3))
    truth = np.zeros((h, w), bool); truth[:, :120] = True
    lake = np.zeros((h, w), bool); lake[20:60, 170:220] = True
    rgb = np.zeros((h, w, 3), np.float32)
    rgb[...] = np.array([120, 125, 90]) + rng.normal(0, 14, (h, w, 3))               # fields
    rgb[30:70, 300:350] = roofs(40, 50)                                               # roofs the mask calls water
    # the rest of the town, on ground the mask leaves alone. The rule knows roofs are land only because it has
    # seen more roofs there than under the mask: a wrong patch of the mask whose colours are nowhere else stays water.
    rgb[110:290, 230:390] = roofs(180, 160)
    rgb[truth | lake] = np.array([22, 40, 62]) + rng.normal(0, 4, (int((truth | lake).sum()), 3))
    rgb[250:280, 150:200] = np.array([96, 88, 60]) + rng.normal(0, 4, (30, 50, 3))    # a silt-brown pond
    mask = np.zeros((h, w), bool); mask[:, :128] = True; mask[30:70, 300:350] = True
    elev = np.where(truth, 0.0, 12.0 + rng.normal(0, 1.5, (h, w))).astype(np.float32)
    job = dict(rgb=np.clip(rgb, 0, 255).astype(np.uint8), elev=elev, mask=mask, mx=19.0, my=19.0, cell=13.0)
    # the same scene with the mask flooding the whole town and its colours nowhere else: only the shipped field,
    # which calls that district dry, can say the mask is wrong there
    flood = mask.copy(); flood[100:300, 220:400] = True
    dry = np.where(np.arange(w)[None, :] < 124, 1.0, 0.0).astype(np.float32) * np.ones((h, w), np.float32)
    big = dict(job, mask=flood, mx=60.0, my=60.0, cell=4.0)
    flags, _ = run_rule([dict(job, name="made"), dict(job, name="nopic", noPicture=True), dict(big, name="flood"), dict(big, name="flooddry", ship=dry)])
    f = flags["made"]
    edge = np.abs(f[:, 100:140].sum(1) - 20)                                           # the coast is at column 120
    ok = [("the coast is where the picture has it, not where the mask has it", float(edge.max()) <= 2),
          ("roofs the mask calls water are land", f[30:70, 300:350].mean() < 0.02),
          ("a lake of the sea's colour is found though the mask has none there", f[20:60, 170:220].mean() > 0.98),
          ("a pond of a colour the mask's water never has stays land", f[250:280, 150:200].mean() < 0.02),
          ("the town stays land", f[110:290, 230:390].mean() < 0.005),
          ("a town the mask floods whole stays water when nothing says otherwise", flags["flood"][110:290, 230:390].mean() > 0.9),
          ("and is land when the shipped field calls the district dry, the sea staying sea", flags["flooddry"][110:290, 230:390].mean() < 0.05 and flags["flooddry"][:, :110].mean() > 0.98),
          ("no picture: the mask is the answer", bool((flags["nopic"] == mask).all())),
          ("the score counts both kinds of error", score(mask, truth)[0] > 0.01 and abs(score(~truth, truth)[1] - truth.mean()) < 1e-9 and score(truth, truth) == (0.0, 0.0, 1.0))]
    for name, good in ok:
        print(f"  {'ok  ' if good else 'FAIL'} {name}")
    return 0 if all(g for _, g in ok) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true"); ap.add_argument("--register", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    summary, rows, worse = audit()
    if a.register:
        register(summary, rows, worse)
    if not a.json:
        for r in rows:
            print(f"  {r['name']:11s} water {100 * r['water']:5.1f}%  rule false {100 * r['rule'][0]:4.1f}% missed {100 * r['rule'][1]:4.1f}% IoU {r['rule'][2]:.2f} | MODIS wrong {100 * (r['mask'][0] + r['mask'][1]):4.1f}% IoU {r['mask'][2]:.2f} | shipped wrong {100 * (r['shipped'][0] + r['shipped'][1]):4.1f}% IoU {r['shipped'][2]:.2f} | {r['ms']} ms")
        for wline in worse:
            print("  WORSE THAN THE MASK:", wline)
    print(json.dumps(summary))
