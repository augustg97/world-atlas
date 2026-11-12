"""Do the streets and buildings sit where the ground is? (register F15)

Closer than 120 m a pixel the page draws OpenStreetMap's roads and buildings (vector tiles from OpenFreeMap) over
Sentinel-2, through a decoder and a frame conversion of its own (web/js/streets.js: Web Mercator tile units to
longitude and latitude). A wrong frame there would slide every street off its photograph, and at 5 m a pixel a
slide of one tile unit in a hundred is a street's width. This checks the BUILDINGS against an independent map of
what is built: ESA WorldCover 2021, class 50 (built-up), 10 m, made from Sentinel-1 radar and Sentinel-2. It is the
witness the close-water audit uses (closewater_witness.py); it shares nothing with OpenStreetMap.

Read as the page reads them: the tiles go through the page's own decoder and frame (build/streets_dump.mjs runs
web/js/streets.js under node), and only then are drawn here, onto each place's grid, each tile inside its own square.

    off_m          how far the footprints must be slid to agree best with WorldCover's built-up ground, in metres:
                   the peak of their correlation over slides of up to 5 texels each way, the WORST place
    off_mean_m     the same, the mean over places
    built_miss_pct of footprint area, the share NOT on WorldCover's built-up class, the mean over places
                   (a house under trees is "tree cover" at 10 m: this is not 0 anywhere)
    on_water_pct   of footprint area, the share on WorldCover's water, the mean
    slid_drop_pct  how much the correlation falls when the footprints are slid 60 m east: the mean over places.
                   Says the instrument can see a slide of that size; a value near 0 would mean it cannot.

WHAT THIS DOES NOT CHECK. The roads (WorldCover has no road class; a road under trees is trees). The drawing
itself (the worker's canvas work: clipping, widths, shadows). The night's lamps. Places where OpenStreetMap has no
buildings. Heights. It needs reference/closewater (closewater_fetch.py, closewater_witness.py), and fetches about
120 tiles (20 MB) from OpenFreeMap into reference/streets/ the first time; the page's own host, asked as the page asks.

    ./venv/bin/python Research/modeling/audit_streets.py [--json]
    ./venv/bin/python Research/modeling/audit_streets.py --selftest
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = os.path.join(ROOT, "reference", "closewater")
TILES = os.path.join(ROOT, "reference", "streets")
PLACES = ("manhattan", "paris", "boston", "amsterdam", "rotterdam", "lyon", "sandiego", "albany")
Z = 14
HALF_KM = 2.6          # the middle of each place's box, this far each way: about sixteen tiles
SS = 4                 # footprints are drawn at this many samples a texel each way and averaged


def tile_xy(lon, lat, z=Z):
    n = 2 ** z
    return (lon / 360 + 0.5) * n, (0.5 - math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / (2 * math.pi)) * n


def fetch(tiles):
    """The tiles, as the page gets them: the address from the service's TileJSON. Cached; an empty file is an empty tile."""
    import requests
    os.makedirs(TILES, exist_ok=True)
    need = [t for t in tiles if not os.path.exists(os.path.join(TILES, f"{Z}_{t[0]}_{t[1]}.pbf"))]
    if not need:
        return
    S = requests.Session(); S.headers["User-Agent"] = "python-requests"
    tj = S.get("https://tiles.openfreemap.org/planet", timeout=60).json()
    tpl = tj["tiles"][0]
    if not tpl.startswith("https://tiles.openfreemap.org/"):
        raise RuntimeError("audit_streets: the TileJSON names another host")
    for x, y in need:
        r = S.get(tpl.replace("{z}", str(Z)).replace("{x}", str(x)).replace("{y}", str(y)), timeout=120)
        if r.status_code not in (200, 204, 404):
            raise RuntimeError(f"audit_streets: tile {Z}/{x}/{y}: HTTP {r.status_code}")
        with open(os.path.join(TILES, f"{Z}_{x}_{y}.pbf"), "wb") as fh:
            fh.write(r.content if r.status_code == 200 else b"")


def decode(tiles):
    """The page's own decoder and frame, under node: a list of {box, buildings: [{rings: [[lon, lat, ...]]}]}."""
    out = subprocess.run(["node", os.path.join(ROOT, "build", "streets_dump.mjs")] + [os.path.join(TILES, f"{Z}_{x}_{y}.pbf") for x, y in tiles],
                         capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise RuntimeError(f"audit_streets: streets_dump.mjs failed: {out.stderr[-600:]}")
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def draw(decoded, lons, lats):
    """Footprint cover (0..1) on a place's grid: each tile's buildings inside the tile's own square, as the page clips them."""
    from PIL import Image, ImageDraw
    H, W = len(lats), len(lons)
    dlon, dlat = (lons[-1] - lons[0]) / (W - 1), (lats[-1] - lats[0]) / (H - 1)
    fx = lambda lon: ((lon - lons[0]) / dlon + 0.5) * SS
    fy = lambda lat: ((lat - lats[0]) / dlat + 0.5) * SS
    acc = np.zeros((H * SS, W * SS), np.uint8)
    for t in decoded:
        im = Image.new("L", (W * SS, H * SS), 0)
        g = ImageDraw.Draw(im)
        for b in t["buildings"]:
            # outer rings fill, inner rings (opposite winding) cut: even-odd by XOR, ring by ring
            one = Image.new("1", (W * SS, H * SS), 0)
            for ring in b["rings"]:
                pts = [(fx(ring[i]), fy(ring[i + 1])) for i in range(0, len(ring), 2)]
                if len(pts) >= 3:
                    layer = Image.new("1", (W * SS, H * SS), 0)
                    ImageDraw.Draw(layer).polygon(pts, fill=1)
                    one = Image.fromarray(np.logical_xor(np.asarray(one), np.asarray(layer)))
            im.paste(255, mask=one)
        del g
        a = np.asarray(im)
        x0, y0, x1, y1 = fx(t["box"][0]), fy(t["box"][1]), fx(t["box"][2]), fy(t["box"][3])
        clip = np.zeros_like(a, bool)
        clip[max(0, int(round(min(y0, y1)))):max(0, int(round(max(y0, y1)))), max(0, int(round(min(x0, x1)))):max(0, int(round(max(x0, x1))))] = True
        acc = np.maximum(acc, np.where(clip, a, 0))
    return acc.reshape(H, SS, W, SS).mean((1, 3)) / 255


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / math.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


def best_slide(cover, built, reach=5):
    """Slide `cover` over `built` by whole texels up to `reach` each way: (dx, dy) of the best correlation, to a
    fraction of a texel by a parabola through the peak, positive = cover lies EAST / SOUTH of built; and the table."""
    H, W = cover.shape
    r = reach
    tab = np.zeros((2 * r + 1, 2 * r + 1))
    core = built[r:H - r, r:W - r]
    for j in range(-r, r + 1):
        for i in range(-r, r + 1):
            tab[j + r, i + r] = corr(cover[r + j:H - r + j, r + i:W - r + i], core)
    j, i = np.unravel_index(tab.argmax(), tab.shape)

    def sub(vm, v0, vp):
        d = vm - 2 * v0 + vp
        return 0.0 if abs(d) < 1e-12 else float(np.clip(0.5 * (vm - vp) / d, -0.5, 0.5))
    dx = (i - r) + (sub(tab[j, i - 1], tab[j, i], tab[j, i + 1]) if 0 < i < 2 * r else 0.0)
    dy = (j - r) + (sub(tab[j - 1, i], tab[j, i], tab[j + 1, i]) if 0 < j < 2 * r else 0.0)
    return dx, dy, tab


def audit():
    rows = []
    for n in PLACES:
        p, pw = os.path.join(REF, f"{n}.npz"), os.path.join(REF, f"{n}.wc.npz")
        if not (os.path.exists(p) and os.path.exists(pw)):
            raise SystemExit(f"audit_streets: reference/closewater/{n}.npz or its .wc.npz is missing. Run closewater_fetch.py and closewater_witness.py")
        d, w = np.load(p), np.load(pw)
        lons, lats, mx, my = d["lons"], d["lats"], float(d["mx"]), float(d["my"])
        H, W = len(lats), len(lons)
        hw, hh = int(HALF_KM * 1000 / mx), int(HALF_KM * 1000 / my)
        sl = (slice(max(0, H // 2 - hh), min(H, H // 2 + hh)), slice(max(0, W // 2 - hw), min(W, W // 2 + hw)))
        lo, la = lons[sl[1]], lats[sl[0]]
        (x0, y0), (x1, y1) = tile_xy(lo[0], la[0]), tile_xy(lo[-1], la[-1])
        tiles = [(x, y) for y in range(int(min(y0, y1)), int(max(y0, y1)) + 1) for x in range(int(min(x0, x1)), int(max(x0, x1)) + 1)]
        fetch(tiles)
        dec = decode(tiles)
        cover = draw(dec, lo, la)
        cls, valid = w["cls"][sl], w["valid"][sl]
        if cover.sum() < 200 or valid.mean() < 0.9:
            raise SystemExit(f"audit_streets: {n} has {cover.sum():.0f} texels of footprint and {100 * valid.mean():.0f}% of the witness")
        built = (cls == 50).astype(np.float64)
        dx, dy, tab = best_slide(cover, built)
        k60 = max(1, int(round(60 / mx)))
        here = tab[5, 5]
        rows.append(dict(name=n, tiles=len(tiles), buildings=sum(len(t["buildings"]) for t in dec), cover=float(cover.mean()),
                         off_x_m=dx * mx, off_y_m=dy * my, off_m=math.hypot(dx * mx, dy * my), corr=float(here),
                         miss=float((cover * (1 - built)).sum() / cover.sum()), water=float((cover * (cls == 80)).sum() / cover.sum()),
                         drop=float(1 - tab[5, min(10, 5 + k60)] / here) if here > 0 else 0.0))
    if float(np.mean([r["drop"] for r in rows])) < 0.10:
        raise SystemExit("audit_streets: sliding the footprints 60 m lowers the agreement by under a tenth: this instrument cannot see a slide")
    summary = dict(off_m=round(max(r["off_m"] for r in rows), 1), off_mean_m=round(float(np.mean([r["off_m"] for r in rows])), 1),
                   built_miss_pct=round(100 * float(np.mean([r["miss"] for r in rows])), 1), on_water_pct=round(100 * float(np.mean([r["water"] for r in rows])), 2),
                   slid_drop_pct=round(100 * float(np.mean([r["drop"] for r in rows])), 1), places=len(rows))
    return summary, rows


def register(summary, rows):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "REGISTER-streets.md"), "w") as fh:
        fh.write("# Streets and buildings against WorldCover's built-up ground\n\nWritten by `audit_streets.py`. OpenStreetMap's building footprints (OpenFreeMap, zoom 14), read by the page's own decoder and frame, "
                 "against ESA WorldCover 2021 class 50, over the middle 5 km of each place.\n\n| place | tiles | footprint share of the ground | slide for best agreement, east (m) | south (m) | footprint not on built-up | on water | correlation falls when slid 60 m |\n|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            fh.write(f"| {r['name']} | {r['tiles']} | {100 * r['cover']:.0f}% | {r['off_x_m']:+.0f} | {r['off_y_m']:+.0f} | {100 * r['miss']:.0f}% | {100 * r['water']:.1f}% | {100 * r['drop']:.0f}% |\n")
        fh.write(f"\nSummary: `{json.dumps(summary)}`\n")


def selftest():
    rng = np.random.default_rng(3)
    # a town of blocks, and the same town slid 2 texels east and 1 north: the slide is found, to a fraction of a texel
    truth = np.zeros((120, 160))
    for _ in range(140):
        y, x, h, w = rng.integers(8, 100), rng.integers(8, 140), rng.integers(2, 7), rng.integers(2, 9)
        truth[y:y + h, x:x + w] = 1
    cover = np.roll(np.roll(truth, 2, 1), -1, 0)
    dx, dy, tab = best_slide(cover, truth)
    assert abs(dx - 2) < 0.3 and abs(dy + 1) < 0.3, (dx, dy)
    dx, dy, _ = best_slide(truth, truth)
    assert abs(dx) < 0.05 and abs(dy) < 0.05
    # the frame: the Louvre's tile, as OpenStreetMap numbers it
    x, y = tile_xy(2.3376, 48.8606)
    assert (int(x), int(y)) == (8298, 5636), (x, y)
    # drawing: a square footprint of known size covers its share of the grid, and a tile's square clips it
    lons, lats = np.linspace(0, 0.01, 101), np.linspace(0.01, 0, 101)
    sq = dict(box=[0, 0.01, 0.01, 0], buildings=[dict(rings=[[0.002, 0.002, 0.006, 0.002, 0.006, 0.006, 0.002, 0.006, 0.002, 0.002]])])
    c = draw([sq], lons, lats)
    assert abs(c.sum() / c.size - 0.16) < 0.01, c.sum() / c.size
    half = dict(sq, box=[0, 0.01, 0.004, 0])
    c2 = draw([half], lons, lats)
    assert abs(c2.sum() / c.sum() - 0.5) < 0.05, c2.sum() / c.sum()
    hole = dict(box=[0, 0.01, 0.01, 0], buildings=[dict(rings=[[0.002, 0.002, 0.006, 0.002, 0.006, 0.006, 0.002, 0.006, 0.002, 0.002], [0.003, 0.003, 0.003, 0.005, 0.005, 0.005, 0.005, 0.003, 0.003, 0.003]])])
    c3 = draw([hole], lons, lats)
    assert abs(c3.sum() / c.sum() - 0.75) < 0.03, c3.sum() / c.sum()
    print("  ok   audit_streets selftest: a slide of two texels is found to a third of one; no slide reads none; the Louvre's tile; a footprint covers its share, is clipped to its tile, and a courtyard is a hole")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    summary, rows = audit()
    register(summary, rows)
    if "--json" not in sys.argv:
        for r in rows:
            print(f"  {r['name']:10s} {r['tiles']:3d} tiles, footprints {100 * r['cover']:4.1f}% of the ground; best agreement slid {r['off_x_m']:+5.0f} m east, {r['off_y_m']:+5.0f} m south; {100 * r['miss']:4.1f}% not on built-up, {100 * r['water']:4.2f}% on water; slid 60 m the correlation falls {100 * r['drop']:3.0f}% (from {r['corr']:.2f})")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
