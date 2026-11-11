"""The political units the atlas draws, names and identifies: Natural Earth's admin-0 countries, with the
parts that every map names on their own taken out of their sovereign state.

Natural Earth's 1:50m "countries" file holds France as ONE unit: the mainland, Corsica, and the five overseas
departments an ocean away. Placed by that geometry, the name on French Guiana was "France" (the owner, 2026-11-11:
"this should be labeled French Guiana"), and so it was on Martinique, Guadeloupe, Reunion and Mayotte. Natural
Earth's own "map units" file holds each as a unit with its own name, population and label rank; those five are
taken from it here and their polygons removed from France. The sheet the atlas started from names all five the
same way, with "(France)" under the name.

Everything that reads the country file reads it through `admin_units()`, because the unit's id on screen is its
index in ADM0_A3 order: vectors.step_political (the names and cards), fields_human.step_countries (the identity
raster) and Research/modeling/audit_labels.py must agree on the list.

Not split, and a decision for later: Svalbard and Jan Mayen (Norway), the Azores and Madeira (Portugal), the
Caribbean Netherlands, Alaska and Hawaii (which Natural Earth does not hold as map units at all).
"""
from __future__ import annotations

import copy
import json
import os

# sovereign state -> the map units (GU_A3) taken out of it
SPLIT = {"FRA": ["GUF", "GLP", "MTQ", "REU", "MYT"]}
NOTES = {"MYT": " Claimed by the Comoros."}


def _polys(g):
    return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]


def _bbox(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def admin_units(data_dir):
    """The admin-0 features, unsorted, with SPLIT applied. `data_dir` is the project's data/ folder."""
    co = json.load(open(os.path.join(data_dir, "ne", "ne_50m_admin_0_countries.geojson")))["features"]
    mu = {f["properties"]["GU_A3"]: f for f in json.load(open(os.path.join(data_dir, "ne", "ne_50m_admin_0_map_units.geojson")))["features"]}
    taken = {f["properties"]["ADM0_A3"] for f in co}
    out = []
    for f in co:
        a3 = f["properties"]["ADM0_A3"]
        if a3 not in SPLIT:
            out.append(f)
            continue
        f = copy.deepcopy(f)
        polys = _polys(f["geometry"])
        for gu in SPLIT[a3]:
            u = copy.deepcopy(mu[gu])
            assert u["properties"]["ADM0_A3"] == a3 and gu not in taken, gu
            boxes = [_bbox(p[0]) for p in _polys(u["geometry"])]
            x0, y0, x1, y1 = min(b[0] for b in boxes) - 0.05, min(b[1] for b in boxes) - 0.05, max(b[2] for b in boxes) + 0.05, max(b[3] for b in boxes) + 0.05

            def inside(p):
                b = _bbox(p[0])
                return b[0] >= x0 and b[1] >= y0 and b[2] <= x1 and b[3] <= y1
            gone = [p for p in polys if inside(p)]
            # the two files are one generalisation: the unit's polygons are the state's, ring for ring
            assert len(gone) == len(boxes), f"{gu}: {len(gone)} polygons of {a3} lie in it, the unit has {len(boxes)}"
            polys = [p for p in polys if not inside(p)]
            p = u["properties"]
            p.update(ADM0_A3=gu, TYPE="Overseas department of France", HOMEPART=0, NOTE_BRK=None,
                     NOTE_ADM0=f"An overseas department and region of {p['SOVEREIGNT']}, and part of it: {p['SOVEREIGNT']}'s own figures include it." + NOTES.get(gu, ""))
            out.append(u)
        f["geometry"] = {"type": "MultiPolygon", "coordinates": polys}
        out.append(f)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    fc = admin_units(os.path.join(here, "..", "data"))
    by = {f["properties"]["ADM0_A3"]: f for f in fc}
    assert len(by) == len(fc) == 242 + 5, len(fc)
    fra = [_bbox(p[0]) for p in _polys(by["FRA"]["geometry"])]
    assert len(fra) == 3 and all(-6 < b[0] and b[2] < 10 and 41 < b[1] and b[3] < 52 for b in fra), fra     # the mainland, Corsica, Oleron
    g = _bbox(_polys(by["GUF"]["geometry"])[0][0])
    assert -55 < g[0] and g[2] < -51 and 2 < g[1] and g[3] < 6 and by["GUF"]["properties"]["NAME_EN"] == "French Guiana", g
    assert by["GUF"]["properties"]["SOVEREIGNT"] == "France" and by["GUF"]["properties"]["HOMEPART"] != 1
    print(f"  ok   {len(fc)} units; France is {len(fra)} polygons in Europe; French Guiana, Guadeloupe, Martinique, Reunion and Mayotte are their own")
