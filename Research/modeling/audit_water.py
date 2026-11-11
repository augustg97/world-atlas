"""Is the atlas's water where the water is? (register A5)

The shipped water mask (web/fields/water.webp) against a witness it is not built from: ETOPO 2022 at one
arc-minute. The witness's sea is every cell below sea level that connects to the world ocean; that needs
no coastline from anyone. Compared as fractions of each 5 km cell, so a coast that crosses a cell counts
for what it is.

    sea_as_land    sea by the witness that the atlas draws as land, million km2, north of 60 S
    land_as_sea    ocean-connected atlas water where the witness has land, million km2, north of 60 S
    worst_patch    the largest single connected patch of either kind, thousand km2

South of 60 S the two disagree by definition as well as by error: the mask takes Antarctica's coast from
the ice the picture shows, fast ice included, and ETOPO calls fast ice sea. That part is reported apart
(`south60`) and is not a fault of either.

The witness is wrong in its own ways and the register lists where: land below sea level that touches the
coast (the Dutch polders, the Po and Nile deltas' edges) reads as sea, and ETOPO's shoreline is the
zero contour of a 1.85 km grid. A patch is a FINDING only after it has been looked at.

Rivers (register A10). The widest rivers fill a 5 km cell and should be water, not a line on land. There is no
river-width dataset in hand to score against, so the check is a list: nine reaches that are several kilometres
wide by any account (the Amazon below Manaus, the lower Negro and Tapajos, the Congo above Kinshasa, the lower
Ob, Yenisei and Lena, the Parana, the Brahmaputra in Assam). Each is found by NAME on Natural Earth's 1:10m
centrelines inside a box, walked every 2 km, and the share of its length that the atlas draws as water (within
one cell) is reported. `rivers_undrawn` is the mean share NOT drawn over the nine. The mask's rivers are MODIS
water found along these same centrelines, so this checks that they arrived on screen, not that MODIS is right;
four narrow rivers are listed beside them as the expected other case. Inland water by region is set against
HydroLAKES's lake areas (lakes only: where the atlas has more, rivers are part of the reason).

Lakes have a second, weaker witness, reported and not gated: open fresh water as Blue Marble shows it
(dark, not red pixels of the July picture), which is what the mask was built from until 2026-11-10.

    ./venv/bin/python Research/modeling/audit_water.py [--json] [--register]
    ./venv/bin/python Research/modeling/audit_water.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "build"))
import frames as F  # noqa: E402

W, H = 8192, 4096
CACHE = os.path.join(ROOT, "data", "_cache")
Image.MAX_IMAGE_PIXELS = None
# where the eye goes: (name, lon0, lat0, lon1, lat1)
BOXES = [("SW Hudson Bay and James Bay", -95, 51, -78, 60), ("Bahamas banks", -80, 21, -73, 28), ("Netherlands and Wadden Sea", 3, 51, 9, 54.5),
         ("Gulf of Ob and Kara coast", 66, 64, 82, 74), ("Yellow Sea and Bohai", 117, 30, 127, 41), ("Amazon mouth", -52, -2, -46, 3),
         ("Gulf of Carpentaria", 135, -18, 142, -10), ("Persian Gulf head", 47, 28, 52, 31), ("Patagonian fjords", -76, -55, -70, -45),
         ("Great Barrier Reef", 142, -24, 153, -10)]


from fields_surface import ocean_connected, etopo_sea8 as etopo_sea  # noqa: E402  (the witness's sea; shared so that there is one definition of it)


def shipped():
    return np.asarray(Image.open(os.path.join(ROOT, "web", "fields", "water.webp")).convert("L"), dtype=np.float32) / 255.0


def river_added():
    """What the river step added to the mask (build/fields_surface.py writes it beside the mask), or None."""
    p = os.path.join(CACHE, "river8.npy")
    return np.load(p).astype(np.float32) if os.path.exists(p) else None


def compare(water, sea_w, river=None):
    """water: the atlas's water fraction (H, W). sea_w: the witness's sea fraction. Areas in million km2.
    river: the part of `water` that is river. A river is joined to the sea at its mouth, so "water connected to the
    ocean" runs up the Amazon to Peru, and all of it would be scored as land drawn as sea (the witness's sea stops
    at sea level). The atlas's SEA is what is connected to the ocean without the rivers."""
    area = F.cell_area_km2(W, H) * np.ones((1, W), dtype=np.float32) / 1e6
    still = water if river is None else np.clip(water - river, 0, 1)
    atlas_sea = np.where(ocean_connected(still > 0.5), still, 0.0)          # lakes and rivers are not this part's subject
    # each kind is the part of the disagreement in its direction; a coast cell at 0.4 against 0.5 counts 0.1
    sea_as_land = np.clip(sea_w - np.where(ocean_connected(water > 0.5) | (water <= 0.5), water, 1.0), 0, 1)   # water of any kind satisfies "sea"
    land_as_sea = np.clip(atlas_sea - sea_w, 0, 1)
    s60 = (F.canon_lat(H) < -60.0)[:, None]
    out = dict(sea_as_land=float((sea_as_land * area * ~s60).sum()), land_as_sea=float((land_as_sea * area * ~s60).sum()),
               south60=(float((sea_as_land * area * s60).sum()), float((land_as_sea * area * s60).sum())))
    sea_as_land = np.where(s60, 0.0, sea_as_land); land_as_sea = np.where(s60, 0.0, land_as_sea)      # patches and boxes: the evidence only
    patches = []
    for kind, d in (("sea drawn as land", sea_as_land), ("land drawn as sea", land_as_sea)):
        lab, n = ndimage.label(d > 0.5)
        if n == 0:
            continue
        idx = np.arange(1, n + 1)
        a = ndimage.sum(d * area, lab, idx) * 1e3                           # thousand km2
        cy, cx = np.array(ndimage.center_of_mass(d, lab, idx)).T
        for i in np.argsort(-a)[:25]:
            patches.append(dict(kind=kind, area_kkm2=float(a[i]), lon=float(-180 + (cx[i] + 0.5) * 360 / W), lat=float(90 - (cy[i] + 0.5) * 180 / H)))
    patches.sort(key=lambda p: -p["area_kkm2"])
    out["worst_patch"] = patches[0]["area_kkm2"] if patches else 0.0
    boxes = {}
    lon = -180 + (np.arange(W) + 0.5) * 360 / W; lat = 90 - (np.arange(H) + 0.5) * 180 / H
    for name, x0, y0, x1, y1 in BOXES:
        m = np.outer((lat >= y0) & (lat <= y1), (lon >= x0) & (lon <= x1))
        boxes[name] = dict(sea_as_land_kkm2=float((sea_as_land * area * m).sum() * 1e3), land_as_sea_kkm2=float((land_as_sea * area * m).sum() * 1e3))
    return out, patches, boxes


def lakes_vs_picture(water):
    """Inland water against Blue Marble's dark fresh water (the old source; cached by fields_surface)."""
    p = os.path.join(CACHE, "bmng_lake8.npy")
    if not os.path.exists(p):
        return None
    area = F.cell_area_km2(W, H) * np.ones((1, W), dtype=np.float32) / 1e6
    sea = ocean_connected(water > 0.5)
    inland = np.where(sea, 0.0, water)
    # the picture's dark water, away from the atlas's sea and its shore (dark coastal water is not a lake)
    bm = np.where(ndimage.binary_dilation(sea, iterations=3), 0.0, np.load(p).astype(np.float32))
    return dict(atlas_inland_Mkm2=float((inland * area).sum()), picture_inland_Mkm2=float((bm * area).sum()),
                picture_only_Mkm2=float((np.clip(bm - water, 0, 1) * area).sum()), atlas_only_Mkm2=float((np.clip(inland - bm, 0, 1) * area).sum()))


# (label, the name on Natural Earth's centreline, lon0, lat0, lon1, lat1, gated)
REACHES = [("Amazon, Manaus to Almeirim", "Amazonas", -60.0, -4.0, -52.5, -1.0, True), ("Negro, lower", "Negro", -63.0, -3.4, -60.0, 0.0, True),
           ("Tapajos, lower", "Tapaj\u00f3s", -56.5, -4.3, -54.5, -2.3, True), ("Congo, Mbandaka to Kinshasa", "Congo", 15.0, -4.5, 19.0, 0.5, True),
           ("Ob, lower", "Ob", 64.0, 62.0, 72.0, 66.6, True), ("Yenisei, lower", "Yenisey", 80.0, 62.0, 92.0, 70.0, True),
           ("Lena, lower", "Lena", 120.0, 62.0, 131.0, 70.5, True), ("Parana, lower", "Paran\u00e1", -61.5, -34.0, -57.0, -27.0, True),
           ("Brahmaputra, Assam", "Brahmaputra", 89.5, 24.0, 95.5, 28.0, True),
           ("Mississippi (about 1 km wide)", "Mississippi", -92.5, 30.0, -89.0, 37.0, False), ("Yangtze above the estuary (1 to 2 km)", "Chang Jiang", 111.0, 29.0, 119.0, 32.5, False),
           ("Danube (under 1 km)", "Danube", 16.0, 43.5, 28.0, 48.5, False), ("Nile (under 1 km)", "Nile", 30.0, 18.0, 34.0, 30.0, False)]


def reaches(water):
    """The share of each reach's centreline that lies on drawn water (water > 0.5 within one cell). None: not found."""
    path = os.path.join(ROOT, "data", "ne", "ne_10m_rivers_lake_centerlines.geojson")
    if not os.path.exists(path):
        return None
    wet = ndimage.maximum_filter(water, size=3, mode=("nearest", "wrap")) > 0.5
    feats = json.load(open(path))["features"]
    out = []
    for label, name, x0, y0, x1, y1, gated in REACHES:
        on = tot = 0.0
        for f in feats:
            p, g = f["properties"], f["geometry"]
            if not g or name not in (p.get("name"), p.get("name_en")):
                continue
            for line in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
                for a, b in zip(line, line[1:]):
                    km = float(np.hypot((b[0] - a[0]) * np.cos(np.radians(a[1])), b[1] - a[1]) * 111.2)
                    for t in (np.arange(max(1, int(km / 2.0))) + 0.5) / max(1, int(km / 2.0)):
                        lo, la = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                        if not (x0 <= lo <= x1 and y0 <= la <= y1):
                            continue
                        step = km / max(1, int(km / 2.0))
                        tot += step
                        on += step * bool(wet[min(H - 1, int((90 - la) / 180 * H)), int((lo + 180) / 360 * W) % W])
        out.append(dict(reach=label, gated=gated, km=round(tot), drawn=(on / tot if tot else None)))
    return out


# inland water by region against HydroLAKES's lake areas (million km2; reported, not gated)
REGIONS = [("Canada", -140, 48, -55, 72), ("Siberia", 60, 50, 180, 75), ("Scandinavia and Finland", 5, 55, 35, 71), ("Amazon basin", -75, -12, -48, 4),
           ("United States", -125, 25, -67, 48), ("Tibet", 78, 28, 100, 37)]


def regions(water):
    p = os.path.join(CACHE, "hydrolakes_all.npz")
    if not os.path.exists(p):
        return None
    z = np.load(p)
    area = F.cell_area_km2(W, H) * np.ones((1, W), dtype=np.float32) / 1e6
    inland = np.where(ocean_connected(water > 0.5), 0.0, water)
    lon = -180 + (np.arange(W) + 0.5) * 360 / W; lat = 90 - (np.arange(H) + 0.5) * 180 / H
    out = []
    for name, x0, y0, x1, y1 in REGIONS:
        m = np.outer((lat >= y0) & (lat <= y1), (lon >= x0) & (lon <= x1))
        hm = (z["lon"] >= x0) & (z["lon"] <= x1) & (z["lat"] >= y0) & (z["lat"] <= y1)
        out.append(dict(region=name, atlas=float((inland * area * m).sum()), hydrolakes=float(z["area"][hm].sum() / 1e6)))
    return out


def run(as_json=False, register=False):
    water, sea_w = shipped(), etopo_sea()
    out, patches, boxes = compare(water, sea_w, river_added())
    lk = lakes_vs_picture(water)
    rv, rg = reaches(water), regions(water)
    summary = dict(sea_as_land_Mkm2=round(out["sea_as_land"], 3), land_as_sea_Mkm2=round(out["land_as_sea"], 3), worst_patch_kkm2=round(out["worst_patch"], 1))
    if rv:
        gated = [r for r in rv if r["gated"]]
        missing = [r["reach"] for r in gated if r["drawn"] is None]
        if missing:
            raise SystemExit(f"audit_water: no centreline found for {missing}; the reach list is out of step with Natural Earth")
        summary["rivers_undrawn"] = round(float(np.mean([1.0 - r["drawn"] for r in gated])), 3)
    if not as_json:
        print("the shipped water mask against ETOPO 2022's ocean-connected sea, 5 km cells")
        print(f"  north of 60 S:  sea the atlas draws as land  {out['sea_as_land']:.3f} M km2      land the atlas draws as sea  {out['land_as_sea']:.3f} M km2")
        print(f"  south of 60 S (ice front against sea floor, not gated):  {out['south60'][0]:.3f} and {out['south60'][1]:.3f}")
        print("  where the eye goes (thousand km2: sea as land, land as sea)")
        for name, b in boxes.items():
            print(f"    {name:30} {b['sea_as_land_kkm2']:7.1f} {b['land_as_sea_kkm2']:7.1f}")
        print("  largest patches")
        for p in patches[:14]:
            print(f"    {p['area_kkm2']:7.1f}  {p['kind']:18} {p['lat']:7.2f}, {p['lon']:8.2f}")
        if lk:
            print(f"  inland water: atlas {lk['atlas_inland_Mkm2']:.3f} M km2, Blue Marble's dark water {lk['picture_inland_Mkm2']:.3f}; in the picture only {lk['picture_only_Mkm2']:.3f}, in the atlas only {lk['atlas_only_Mkm2']:.3f}")
    if not as_json and rv:
        print("  wide rivers: share of the centreline drawn as water")
        for r in rv:
            print(f"    {r['reach']:40} {r['km']:5d} km   " + ("not found" if r["drawn"] is None else f"{100 * r['drawn']:5.1f}%") + ("" if r["gated"] else "   (narrow: not gated)"))
    if not as_json and rg:
        print("  inland water by region, M km2: atlas, and HydroLAKES's lakes alone")
        for r in rg:
            print(f"    {r['region']:26} {r['atlas']:.3f}  {r['hydrolakes']:.3f}")
    if register:
        with open(os.path.join(HERE, "REGISTER-water.md"), "w") as fh:
            fh.write("# Water mask against ETOPO 2022 (audit_water.py)\n\n")
            fh.write(f"Sea drawn as land {out['sea_as_land']:.3f} M km2; land drawn as sea {out['land_as_sea']:.3f} M km2.\n\n| thousand km2 | kind | lat | lon |\n|---|---|---|---|\n")
            for p in patches[:40]:
                fh.write(f"| {p['area_kkm2']:.1f} | {p['kind']} | {p['lat']:.2f} | {p['lon']:.2f} |\n")
            if rv:
                fh.write("\n| reach | km | drawn as water |\n|---|---|---|\n")
                for r in rv:
                    fh.write(f"| {r['reach']}{'' if r['gated'] else ' (not gated)'} | {r['km']} | {'not found' if r['drawn'] is None else str(round(100 * r['drawn'], 1)) + '%'} |\n")
            if rg:
                fh.write("\n| region | atlas inland water, M km2 | HydroLAKES lakes, M km2 |\n|---|---|---|\n")
                for r in rg:
                    fh.write(f"| {r['region']} | {r['atlas']:.3f} | {r['hydrolakes']:.3f} |\n")
            fh.write("\n| box | sea as land | land as sea |\n|---|---|---|\n")
            for name, b in boxes.items():
                fh.write(f"| {name} | {b['sea_as_land_kkm2']:.1f} | {b['land_as_sea_kkm2']:.1f} |\n")
    print(json.dumps(summary))
    return summary


def selftest():
    # 1. ocean_connected: a lake is not the sea, and the sea is one piece across the antimeridian
    m = np.zeros((40, 80), bool); m[5:35, :10] = True; m[5:35, 70:] = True; m[18:22, 38:42] = True
    oc = ocean_connected(m)
    assert oc[20, 2] and oc[20, 78] and not oc[20, 40], "the two halves of the sea join across the seam; the lake stays out"
    # 2. compare: plant a strip of sea drawn as land and a strip of land drawn as sea; both are found, at their areas
    sea = np.zeros((H, W), np.float32); sea[:, : W // 2] = 1.0                   # the witness: western hemisphere is sea
    water = sea.copy()
    r0, r1 = H // 2 - 50, H // 2 + 50
    water[r0:r1, W // 2 - 40: W // 2] = 0.0                                       # sea drawn as land
    water[r0 + 400:r1 + 400, W // 2: W // 2 + 20] = 1.0                           # land drawn as sea, further south, touching the sea
    out, patches, _ = compare(water, sea)
    cell = F.cell_area_km2(W, H)[r0:r1, 0].sum() / 1e6
    cell2 = F.cell_area_km2(W, H)[r0 + 400:r1 + 400, 0].sum() / 1e6
    assert abs(out["sea_as_land"] - 40 * cell) < 0.02 * 40 * cell and abs(out["land_as_sea"] - 20 * cell2) < 0.02 * 20 * cell2, (out, 40 * cell, 20 * cell2)
    assert patches[0]["kind"] == "sea drawn as land" and abs(patches[0]["lat"]) < 0.5 and abs(patches[0]["lon"] + 0.9) < 0.5, patches[0]
    # 3. a lake over the witness's land is not "land drawn as sea"
    water2 = sea.copy(); water2[1000:1100, 6000:6100] = 1.0
    out2, _, _ = compare(water2, sea)
    assert out2["land_as_sea"] < 1e-6 and out2["sea_as_land"] < 1e-6, out2
    # 3b. a river that reaches the sea is "land drawn as sea" if nobody says it is a river, and is not when told
    water3 = sea.copy(); riv = np.zeros_like(sea); riv[2000:2004, W // 2: W // 2 + 600] = 1.0; water3 += riv
    assert compare(water3, sea)[0]["land_as_sea"] > 0.02 and compare(water3, sea, riv)[0]["land_as_sea"] < 1e-6
    # 4. reaches(): a mask that is all land draws no river; one that is all water draws every one
    r0, r1 = reaches(np.zeros((H, W), np.float32)), reaches(np.ones((H, W), np.float32))
    if r0 is not None:
        assert all(r["drawn"] in (0.0, None) for r in r0) and all(r["drawn"] in (1.0, None) for r in r1), (r0, r1)
        assert sum(r["drawn"] is not None and r["km"] > 150 for r in r1 if r["gated"]) == sum(r["gated"] for r in r1), [(r["reach"], r["km"]) for r in r1]
    print("audit_water selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true"); ap.add_argument("--register", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        run(a.json, a.register)
