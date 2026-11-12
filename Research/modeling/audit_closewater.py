"""Close in, is the atlas's water where the water is? (registers A12, A15)

Inside the streamed window land or water is decided texel by texel. Since release 1.7 the answer is a RECORD: JRC
Global Surface Water (Landsat 30 m, 1984-2021), water where the place was water in at least half of it, read from
the record's map tiles (web/js/detail.js :: _occurrence). Polewards of the record the stand-in is release 1.6's
rule: NASA's 250 m MODIS mask sharpened by the picture's colour (web/js/water.js :: waterFlag).

Both are scored here at 23 places against a WITNESS neither is made from: ESA WorldCover 2021 v200 (10 m, from
Sentinel-1 and Sentinel-2; class 80, permanent water bodies), fetched by closewater_witness.py. Until release 1.7
the witness was JRC itself; a source cannot be its own witness.

    wrong_pct        texels the record's tiles get wrong against the witness (water called land or land called
                     water), mean over the 23 places at 19 m a texel, percent
    iou_short_pct    100 x (1 - intersection over union of the tiles' water and the witness's), mean over the 23
    worse_than_mask  places where the tiles are wrong on more texels than the MODIS mask alone (by over 0.4 points),
                     at 19 m or at any of four coarser texels (76, 152, 304, 494 m: pooled, as a wider view has it)
    manhattan_false_pct   land called water at Manhattan, where the MODIS mask holds most of the island as water;
                     the worst of the five texel sizes
    tiles_vs_file_pct     THE FRAME CHECK: texels where the tiles, taken onto the grid as the page takes them, differ
                     from the record's own 30 m file sampled directly; the worst place. A shifted or flipped frame
                     conversion shows here as tens of percent; resampling along shores is about one.
    rule_wrong_pct   the stand-in (the app's own waterFlag, run under node) against the same witness, mean of the 23
The MODIS mask alone and the shipped 5 km field are scored beside them, for scale.

WHAT THIS DOES NOT CHECK, AND WHAT THE WITNESS IS. The grids are built here (the tiles bilinear, pooled by averaging
for the coarser texels); the page builds its own from the same tiles by area-weighted taps, at the elevation's zoom.
The witness is one year, 2021, and stricter than "half the time": seasonally flooded ground is wetland in it
(Manaus, Santarem), a reservoir or a lake that fell is bare (Lake Mead, the Dead Sea), bridges, piers and ships at
berth are built-up, tidal flats are not water, and it calls a little false water in mountain shadow (Zermatt). The
record itself lies about one texel west of the picture across Europe and the north-eastern United States
(closewater_witness.py measured it): that is in every number here.

    ./venv/bin/python Research/modeling/closewater_fetch.py && ./venv/bin/python Research/modeling/closewater_fetch.py --jrc
    ./venv/bin/python Research/modeling/closewater_witness.py
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


def places():
    """The 23 places: {name: (the grids, the witness's water share, the tiles' occurrence share)}. Fails loudly if any part is missing."""
    names = sorted(f[:-4] for f in os.listdir(REF) if f.endswith(".npz") and "." not in f[:-4]) if os.path.isdir(REF) else []
    if len(names) < 23:
        raise SystemExit(f"audit_closewater: the reference set is not there ({len(names)} of 23 places in reference/closewater). Run Research/modeling/closewater_fetch.py")
    out = {}
    for n in names:
        for ext, tool in ((".wc.npz", "closewater_witness.py"), (".jrc.npz", "closewater_fetch.py --jrc")):
            if not os.path.exists(os.path.join(REF, n + ext)):
                raise SystemExit(f"audit_closewater: reference/closewater/{n}{ext} is missing. Run Research/modeling/{tool}")
        d = np.load(os.path.join(REF, f"{n}.npz")); wc = np.load(os.path.join(REF, f"{n}.wc.npz")); occ = np.load(os.path.join(REF, f"{n}.jrc.npz"))["occ"]
        if wc["water"].shape != d["truth"].shape or occ.shape != d["truth"].shape:
            raise SystemExit(f"audit_closewater: {n}: the witness or the tiles are not on the place's grid")
        if not wc["valid"].all():
            raise SystemExit(f"audit_closewater: {n}: the witness has no data over {100 * (1 - wc['valid'].mean()):.1f}% of the box")
        out[n] = (d, wc["water"], occ)
    return out


def audit():
    data = places(); names = list(data)
    jobs, truth, maskp, tiles = [], {}, {}, {}
    for n in names:
        d, wc, occ = data[n]; ship = shipped_water(d["lons"], d["lats"])
        for k in POOLS:
            key = f"{n}@{k}"
            m = pool(d["mask"].astype(np.float32), k) > 0.5
            truth[key] = pool(wc, k) >= 0.5; maskp[key] = m; tiles[key] = pool(occ, k) >= 0.5
            jobs.append(dict(name=key, rgb=np.clip(np.round(pool(d["s2"], k)), 0, 255).astype(np.uint8), elev=pool(d["elev"], k), mask=m, ship=pool(ship, k),
                             mx=float(d["mx"]) * k, my=float(d["my"]) * k, cell=max(1.0, 250.0 / (float(d["my"]) * k))))
    flags, done = run_rule(jobs)
    rows, worse = [], []
    for n in names:
        d, wc, occ = data[n]; key = f"{n}@1"
        rows.append(dict(name=n, water=float(truth[key].mean()), tiles=score(tiles[key], truth[key]), rule=score(flags[key], truth[key]), mask=score(maskp[key], truth[key]),
                         shipped=score(shipped_water(d["lons"], d["lats"]) > 0.5, truth[key]), frame=float(((occ >= 0.5) != d["truth"]).mean()), ms=done[key]["ms"]))
        for k in POOLS:
            kk = f"{n}@{k}"; a = score(tiles[kk], truth[kk]); b = score(maskp[kk], truth[kk])
            if 100 * (a[0] + a[1]) > 100 * (b[0] + b[1]) + MARGIN:
                worse.append(f"{n} at {19 * k} m: {100 * (a[0] + a[1]):.1f}% against {100 * (b[0] + b[1]):.1f}%")
    mean = lambda f: float(np.mean([f(r) for r in rows]))
    wrong = lambda r, w: r[w][0] + r[w][1]
    by_pool = {19 * k: 100 * float(np.mean([sum(score(tiles[f"{n}@{k}"], truth[f"{n}@{k}"])[:2]) for n in names])) for k in POOLS}
    man = max(100 * score(tiles[f"manhattan@{k}"], truth[f"manhattan@{k}"])[0] for k in POOLS)
    summary = dict(wrong_pct=round(100 * mean(lambda r: wrong(r, "tiles")), 2), iou_short_pct=round(100 * (1 - mean(lambda r: r["tiles"][2])), 1), worse_than_mask=len(worse),
                   manhattan_false_pct=round(man, 1), tiles_vs_file_pct=round(100 * max(r["frame"] for r in rows), 2), rule_wrong_pct=round(100 * mean(lambda r: wrong(r, "rule")), 2),
                   tiles_iou=round(mean(lambda r: r["tiles"][2]), 3), rule_iou=round(mean(lambda r: r["rule"][2]), 3),
                   mask_wrong_pct=round(100 * mean(lambda r: wrong(r, "mask")), 2), shipped_wrong_pct=round(100 * mean(lambda r: wrong(r, "shipped")), 2),
                   mask_iou=round(mean(lambda r: r["mask"][2]), 3), shipped_iou=round(mean(lambda r: r["shipped"][2]), 3),
                   false_water_pct=round(100 * mean(lambda r: r["tiles"][0]), 2), missed_water_pct=round(100 * mean(lambda r: r["tiles"][1]), 2),
                   by_texel_m={k: round(v, 2) for k, v in by_pool.items()}, slowest_ms=max(r["ms"] for r in rows))
    return summary, rows, worse


def register(summary, rows, worse):
    w = lambda r, k: 100 * (r[k][0] + r[k][1])
    L = ["# Close in: land or water (registers A12, A15)", "",
         "At 23 places, 19 m a texel, against ESA WorldCover 2021 (10 m; class 80, permanent water). **Tiles**: JRC Global Surface Water as the page reads it (water in at least half of 1984-2021), the page's source since release 1.7. **Rule**: NASA's MODIS mask sharpened by the picture (`water.js :: waterFlag`, run under node), release 1.6's source and the stand-in where the record has no tiles.",
         "Wrong = texels called water that are land, plus texels called land that are water, as a share of all texels in the box. Frame = texels where the tiles differ from the record's own 30 m file.", "",
         "| place | water | tiles: false | missed | IoU | rule: wrong | IoU | MODIS alone: wrong | IoU | shipped 5 km: wrong | frame |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {100 * r['water']:.1f}% | {100 * r['tiles'][0]:.1f}% | {100 * r['tiles'][1]:.1f}% | {r['tiles'][2]:.2f} | {w(r, 'rule'):.1f}% | {r['rule'][2]:.2f} | {w(r, 'mask'):.1f}% | {r['mask'][2]:.2f} | {w(r, 'shipped'):.1f}% | {100 * r['frame']:.2f}% |")
    L += [f"| **mean** | | {summary['false_water_pct']}% | {summary['missed_water_pct']}% | {summary['tiles_iou']:.2f} | {summary['rule_wrong_pct']}% | {summary['rule_iou']:.2f} | {summary['mask_wrong_pct']}% | {summary['mask_iou']:.2f} | {summary['shipped_wrong_pct']}% | worst {summary['tiles_vs_file_pct']}% |", "",
          "The tiles' wrong texels by texel size (pooled): " + ", ".join(f"{k} m {v}%" for k, v in summary["by_texel_m"].items()) + ".",
          f"Places where the tiles are worse than the MODIS mask alone at any texel size: {len(worse)}" + (": " + "; ".join(worse) if worse else "") + ".", "",
          "Places where the tiles are worse than release 1.6's rule by over 0.4 points, each a difference of DATE and not of place: " +
          ("; ".join(f"{r['name']} ({w(r, 'tiles'):.1f}% against {w(r, 'rule'):.1f}%)" for r in rows if w(r, "tiles") > w(r, "rule") + MARGIN) or "none") +
          ". The record's shore there is the 1984-2021 majority; the witness (2021) and the picture (2016) both have the water lower (Lake Mead, the Dead Sea) or the ground reworked (Cairo's canals). The rule followed the picture.", "",
          "Read the low rows for what they are. Manaus, Santarem: seasonally flooded forest, wetland to the witness and water to the record. Port Said: salt pans and basins flooded since. Venice, Chittagong: tidal flats. Zermatt: 0.3% of the box is water, and as much again is the witness's own false water in mountain shadow."]
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
            print(f"  {r['name']:11s} water {100 * r['water']:5.1f}%  tiles false {100 * r['tiles'][0]:4.1f}% missed {100 * r['tiles'][1]:4.1f}% IoU {r['tiles'][2]:.2f} | rule wrong {100 * (r['rule'][0] + r['rule'][1]):4.1f}% | MODIS wrong {100 * (r['mask'][0] + r['mask'][1]):4.1f}% | shipped wrong {100 * (r['shipped'][0] + r['shipped'][1]):4.1f}% | frame {100 * r['frame']:.2f}%")
        for wline in worse:
            print("  WORSE THAN THE MASK:", wline)
    print(json.dumps(summary))
