"""Audit the cards' Wikipedia articles: is each card matched to the article about THAT place?

READ-ONLY. A location card shows the lead of one English Wikipedia article, fetched by the page when the card
opens (web/js/wiki.js). Which article is decided at build time and shipped as web/data/wiki.json
(build/wiki_titles.py). This audit reads that file and the data files the cards are made from, exactly as the
page does, and checks every mapping against two records the build keeps beside its cache
(data/_cache/wiki/report.json): the mapped Wikidata item's OWN coordinate (P625) and, where the item has none, the
coordinates the English article itself carries; and what en.wikipedia.org answered for the title (exists,
redirect, disambiguation page).

    ./venv/bin/python Research/modeling/audit_cardtext.py              # print the findings, write the register
    ./venv/bin/python Research/modeling/audit_cardtext.py --json       # one line of metrics for audit_all.py
    ./venv/bin/python Research/modeling/audit_cardtext.py --selftest   # synthetic input with a known answer
    ./venv/bin/python Research/modeling/audit_cardtext.py --live       # ask en.wikipedia.org again about every title

What it checks, and what each catches:

  coverage      cards of each kind with no article. Not an error (the card says so), but it must not grow.
  place         the item's coordinate lies within a limit of the card's position, scaled by the size of the thing
                (LIMITS below), or within WIDE times the limit when the article's title is the card's own name.
                This is what catches a wrong id: Natural Earth has some, and a name search finds namesakes. The
                build refuses a mapping by the same rule; this is a second copy of the rule, on what was actually
                shipped, so the two cannot drift apart silently.
  article       no shipped title is a disambiguation page; every shipped title exists.
  keys          every key in wiki.json is the key of a card the page can open (a stale file after a data rebuild),
                and the counts the file states are the counts found here.
  shared        one article on two cards of a kind (a duplicate id; usually a twin entry in the source).

Rules this file keeps (Modeling Studio/references/AUDIT-PATTERNS.md): it reads the artifact the page reads; no
bare except; a record it needs and cannot find is a failure, never a pass.

Severity: HIGH = a card would show the wrong place's article, or none could load. MED = fewer cards described
than before. LOW = worth knowing.
"""

from __future__ import annotations

import json
import math
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WEB = os.path.join(ROOT, "web", "data")
REPORT = os.path.join(ROOT, "data", "_cache", "wiki", "report.json")
KINDS = ["city", "country", "dispute", "feature", "peak", "river", "volcano"]
R_KM = 6371.0088
STALE_DAYS = 180                 # the title check is the build's; older than this the register says to run it again

# The place limits, km. The nearest of the item's coordinates must lie this close to the card's position.
LIMITS = {
    "city": "20 km + 0.012 km x sqrt(population): 20 km for a village, 58 km for a city of ten million",
    "volcano": "30 km",
    "peak": "30 km",
    "country": "inside the unit, or within half the diagonal of the box round all its parts (at least 100 km) of a point of its outline",
    "dispute": "inside the area, or within half the diagonal of the box round all its parts (at least 100 km) of a point of its outline",
    "feature": "2.5 x the side of a square of the feature's drawn area (at least 150 km) from its label point",
    "river": "the drawn length of the reaches of that name (at least 60 km) from the nearest drawn point of any of them: a river's coordinate is its mouth or its source",
}
NAME_KM = 350.0   # a mapping the build found BY NAME (not by an id) under another title must lie this close, whatever the limit
WIDE = 3.0        # a mapping whose article title IS the card's name may lie this many limits away (wide_km: a feature and a state differ)


# ---------------------------------------------------------------------------
# load the app's own data — never a copy, or the audit passes while the app is wrong
# ---------------------------------------------------------------------------

def load_subject():
    """Exactly what the page ships, from where it ships it, and the build's two records."""
    rd = lambda f: json.load(open(os.path.join(WEB, f)))
    places, pol, phys, volc = rd("places.json"), rd("political.json"), rd("physical.json"), rd("volcanoes.json")
    cards = {
        "city": places["rows"], "country": pol["countries"], "dispute": pol["disputes"], "feature": phys["features"],
        "peak": [p for p in phys["peaks"] if p["name"]],
        "river": [r for r in phys["rivers"] if r["name"] and r["lines"] and r["lines"][0]],
        "volcano": volc["rows"],
    }
    if not os.path.exists(REPORT):
        raise SystemExit("data/_cache/wiki/report.json is missing: run build/wiki_titles.py (it writes the items' coordinates "
                         "and the titles' status there). Without it nothing here can be checked, and that is a failure.")
    rep = json.load(open(REPORT))
    return {"wiki": rd("wiki.json"), "cards": cards, "coords": rep["coords"], "enwiki": rep["enwiki"], "checked": rep.get("checked"),
            "build": rep.get("kinds", {}), "by_name": {k: {w["key"] for w in v.get("found", []) if w["route"] == "name"} for k, v in rep.get("kinds", {}).items()}}


# ---------------------------------------------------------------------------
# geometry, and the key rule (the page's is wikiKey() in web/js/wiki.js; build/test_app_math.mjs holds that one
# to the counts in wiki.json, and check_keys below holds this one to them)
# ---------------------------------------------------------------------------

def n3(v):
    s = f"{v:.3f}"
    return "0.000" if s == "-0.000" else s


def card_key(kind, c):
    if kind in ("city", "volcano"):
        return f"{c[0]}|{n3(c[1])}|{n3(c[2])}"
    if kind == "country":
        return c["a3"]
    if kind == "dispute":
        return f"{c['name']}|{c['note']}"
    if kind == "feature":
        return f"{c['name']}|{c['kind']}|{n3(c['lon'])}|{n3(c['lat'])}"
    if kind == "peak":
        return f"{c['name']}|{n3(c['lon'])}|{n3(c['lat'])}"
    if kind == "river":
        return f"{c['name']}|{c['lines'][0][0]}|{c['lines'][0][1]}"
    raise ValueError(kind)


def card_name(kind, c):
    return c[0] if kind in ("city", "volcano") else c["name"]


def km(lon1, lat1, lon2, lat2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_KM * math.asin(min(1.0, math.sqrt(a)))


def nearest_km(lon, lat, flat):
    """To the nearest of the points in a flat [lon*100, lat*100, ...] list."""
    return min(km(lon, lat, flat[i] / 100.0, flat[i + 1] / 100.0) for i in range(0, len(flat) - 1, 2))


def inside(lon, lat, polys):
    x, y = lon * 100.0, lat * 100.0
    for poly in polys:
        hit = False
        for ring in poly:
            j = len(ring) - 2
            for i in range(0, len(ring), 2):
                xi, yi, xj, yj = ring[i], ring[i + 1], ring[j], ring[j + 1]
                if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    hit = not hit
                j = i
        if hit:
            return True
    return False


def extent_km(polys, lon0):
    """The diagonal of the box round all the parts of a unit, longitudes taken round lon0 (the date line)."""
    xs = [((v / 100.0 - lon0 + 180.0) % 360.0) - 180.0 + lon0 for poly in polys for v in poly[0][0::2]]
    ys = [v / 100.0 for poly in polys for v in poly[0][1::2]]
    return km(min(xs), min(ys), max(xs), max(ys))


def line_km(lines):
    return sum(km(l[i] / 100.0, l[i + 1] / 100.0, l[i + 2] / 100.0, l[i + 3] / 100.0) for l in lines for i in range(0, len(l) - 3, 2))


def fold(name):
    """A name for comparing: no accents, no case, letters and digits only."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", name or "") if ch.isalnum() and not unicodedata.combining(ch)).casefold()


def offset(kind, c, pts, rivers):
    """(distance, limit) in km between a card and the nearest of its item's coordinates. The rule LIMITS states in words."""
    def one(lon, lat):
        if kind in ("city", "volcano"):
            return km(lon, lat, c[1], c[2])
        if kind in ("peak", "feature"):
            return km(lon, lat, c["lon"], c["lat"])
        if kind in ("country", "dispute"):
            return 0.0 if inside(lon, lat, c["polys"]) else min(nearest_km(lon, lat, poly[0]) for poly in c["polys"])
        return nearest_km(lon, lat, rivers[c["name"]][0])
    d = min(one(lon, lat) for lon, lat in pts)
    if kind == "city":
        return d, 20 + 0.012 * math.sqrt(max(c[3], 0))
    if kind in ("volcano", "peak"):
        return d, 30.0
    if kind in ("country", "dispute"):
        return d, max(100.0, 0.5 * extent_km(c["polys"], c["lon"]))
    if kind == "feature":
        return d, max(150.0, 2.5 * c["size"] * 111.2)
    return d, max(60.0, rivers[c["name"]][1])


def wide_km(kind, lim):
    """The wider limit, for a mapping whose article title is the card's name: WIDE limits; a feature 1000 km where its
    own limit is less, and no more; a state at least 1000 km."""
    return max(lim, 1000.0) if kind == "feature" else max(WIDE * lim, 1000.0) if kind == "country" else WIDE * lim


def passes(kind, name, title, d, lim):
    """'near', 'named' (further off, but the article's title is the card's name), or None."""
    if d <= lim:
        return "near"
    if d <= wide_km(kind, lim) and fold(title) == fold(name):
        return "named"
    return None


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------

def add(findings, sev, check, what, detail=""):
    findings.append({"severity": sev, "check": check, "what": what, "detail": detail})


def check_keys(S, findings, M):
    """A key that opens no card; counts in the file that are not the counts found."""
    M["orphan_keys"] = 0
    for k in KINDS:
        keys = {card_key(k, c) for c in S["cards"][k]}
        table = S["wiki"].get(k, {})
        for key in table:
            if key not in keys:
                M["orphan_keys"] += 1
                add(findings, "HIGH", "keys", f"{k}: '{key}' is in wiki.json and is no card's key", "the data files were rebuilt without build/wiki_titles.py")
        mapped = sum(1 for c in S["cards"][k] if card_key(k, c) in table)
        stated = S["wiki"].get("counts", {}).get(k)
        if stated != [mapped, len(S["cards"][k])]:
            M["orphan_keys"] += 1
            add(findings, "HIGH", "keys", f"{k}: wiki.json states {stated}, the shipped files give {[mapped, len(S['cards'][k])]}")


def check_coverage(S, findings, M):
    """Cards with no article, kind by kind."""
    for k in KINDS:
        table = S["wiki"].get(k, {})
        without = [c for c in S["cards"][k] if card_key(k, c) not in table]
        M[f"uncovered_{k}"] = len(without)
        if without:
            add(findings, "MED", "coverage", f"{k}: {len(without)} of {len(S['cards'][k])} cards have no article",
                ", ".join(str(card_name(k, c)) for c in without[:12]) + (" ..." if len(without) > 12 else ""))


def check_place(S, findings, M):
    """An item whose own coordinate is not where the card is."""
    M["misplaced"] = M["by_name"] = M["by_article_coord"] = 0
    M["unchecked"] = M.get("unchecked", 0)
    rivers = {}                                    # name -> [every drawn point, the drawn length]
    for r in S["cards"]["river"]:
        e = rivers.setdefault(r["name"], [[], 0.0])
        e[0].extend(v for line in r["lines"] for v in line)
        e[1] += line_km(r["lines"])
    S["offsets"] = {k: [] for k in KINDS}
    S["named"] = []
    for k in KINDS:
        table = S["wiki"].get(k, {})
        for c in S["cards"][k]:
            hit = table.get(card_key(k, c))
            if not hit:
                continue
            title, q = hit
            rec = S["coords"].get(q) or {}
            pts = [rec["item"]] if rec.get("item") else rec.get("article") or []
            if not pts:
                M["unchecked"] += 1
                add(findings, "HIGH", "place", f"{k} '{card_name(k, c)}' -> {title} ({q}): no coordinate on record, so the match is unchecked")
                continue
            if not rec.get("item"):
                M["by_article_coord"] += 1
            d, lim = offset(k, c, pts, rivers)
            how = passes(k, card_name(k, c), title, d, lim)
            if card_key(k, c) in S.get("by_name", {}).get(k, ()):          # found by name: a namesake fits inside a big thing's limit
                how = "near" if d <= min(lim, NAME_KM) or (d <= lim and fold(title) == fold(card_name(k, c))) else None
            S["offsets"][k].append(d / lim)
            if how == "named":
                M["by_name"] += 1
                S["named"].append(f"{k} '{card_name(k, c)}' -> {title}: {d:.0f} km (limit {lim:.0f} km)")
            elif not how:
                M["misplaced"] += 1
                add(findings, "HIGH", "place", f"{k} '{card_name(k, c)}' -> {title} ({q}) lies {d:.0f} km from the card", f"limit {lim:.0f} km")


def check_article(S, findings, M):
    """A title that is a disambiguation page, or is not there."""
    M["disambiguation"] = M["dead_titles"] = M["redirects"] = 0
    M["unchecked"] = M.get("unchecked", 0)
    for k in KINDS:
        for key, hit in S["wiki"].get(k, {}).items():
            title, q = hit
            if not isinstance(title, str) or not title.strip() or "|" in title or "#" in title or not (isinstance(q, str) and q[:1] == "Q" and q[1:].isdigit()):
                M["dead_titles"] += 1
                add(findings, "HIGH", "article", f"{k} '{key}': not a title and an id: {hit!r}")
                continue
            st = S["enwiki"].get(title)
            if st is None:
                M["unchecked"] += 1
                add(findings, "HIGH", "article", f"{k} '{key}' -> {title}: the title was never checked on en.wikipedia.org")
            elif st["missing"]:
                M["dead_titles"] += 1
                add(findings, "HIGH", "article", f"{k} '{key}' -> {title}: no such article")
            elif st["disambig"]:
                M["disambiguation"] += 1
                add(findings, "HIGH", "article", f"{k} '{key}' -> {title}: a disambiguation page")
            elif st["to"] != title:
                M["redirects"] += 1
    if M["redirects"]:
        add(findings, "LOW", "article", f"{M['redirects']} shipped titles are redirects", "the page follows them and credits the article it lands on")


def check_shared(S, findings, M):
    """One article on two different cards of a kind."""
    M["shared_articles"] = 0
    for k in KINDS:
        seen = {}
        for c in S["cards"][k]:
            hit = S["wiki"].get(k, {}).get(card_key(k, c))
            if hit:
                seen.setdefault(hit[1], set()).add(card_key(k, c) if k != "river" else c["name"])
        for q, keys in seen.items():
            if len(keys) > 1:
                M["shared_articles"] += 1
                add(findings, "LOW", "shared", f"{k}: {q} is the article of {len(keys)} cards", "; ".join(sorted(keys))[:300])


CHECKS = [check_keys, check_coverage, check_place, check_article, check_shared]


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run(subject=None):
    S = subject or load_subject()
    findings, M = [], {}
    for check in CHECKS:
        check(S, findings, M)          # NOT wrapped in try/except: a check that cannot run must stop the audit
    return S, findings, M


def live(S):
    """Ask en.wikipedia.org again about every shipped title (titles and page properties only). Returns the new record."""
    sys.path.insert(0, os.path.join(ROOT, "build"))
    import wiki_titles
    titles = sorted({hit[0] for k in KINDS for hit in S["wiki"].get(k, {}).values()})
    return {t: {k: v[k] for k in ("missing", "disambig", "to")} for t, v in wiki_titles.enwiki_info(titles, fresh=True).items()}


def _selftest():
    """Every check on a small world whose faults are known."""
    sq = lambda x, y, s: [[[int((x - s) * 100), int((y - s) * 100), int((x + s) * 100), int((y - s) * 100), int((x + s) * 100), int((y + s) * 100), int((x - s) * 100), int((y + s) * 100)]]]
    city = lambda name, lon, lat, pop: [name, lon, lat, pop, 0, 0, "AAA", "", "", 0]
    cards = {
        "city": [city("Right", 10.0, 50.0, 1000000), city("Namesake", 20.0, 40.0, 50000), city("Disambig", 30.0, 30.0, 1000), city("Dead", -0.0001, 10.0, 1000),
                 city("None", 5.0, 5.0, 1000), city("Twin A", 60.0, 60.0, 1000), city("Twin B", 60.05, 60.0, 1000), city("Edge", 0.0, 0.0, 0), city("Wïde", 0.0, 20.0, 0)],
        "country": [{"a3": "AAA", "name": "Aland", "lon": 10.0, "polys": sq(10, 50, 2)}, {"a3": "BBB", "name": "Bland", "lon": 100.0, "polys": sq(100, 0, 1)},
                    {"a3": "CCC", "name": "Isles", "lon": 179.0, "polys": sq(178, 0, 0.2) + sq(-178, 0, 0.2)}],
        "dispute": [{"name": "D", "note": "n", "lon": 0.0, "polys": sq(0, 0, 0.5)}],
        "feature": [{"name": "Sea", "kind": "sea", "lon": -30.0, "lat": 0.0, "size": 10.0}, {"name": "Hills", "kind": "Range/mtn", "lon": 5.0, "lat": 5.0, "size": 0.5},
                    {"name": "Strait", "kind": "strait", "lon": 120.0, "lat": 20.0, "size": 0.0}, {"name": "Twice", "kind": "Range/mtn", "lon": -76.4, "lat": 2.44, "size": 3.37},
                    {"name": "Belt", "kind": "Geoarea", "lon": 10.0, "lat": 15.0, "size": 18.0}, {"name": "Shelf", "kind": "Geoarea", "lon": 10.0, "lat": -15.0, "size": 18.0}],
        "peak": [{"name": "Peak", "lon": 86.9, "lat": 28.0}],
        "river": [{"name": "Flow", "lines": [[0, 0, 100, 0, 200, 0]]}, {"name": "Brook", "lines": [[3000, 0, 3020, 0]]}],
        "volcano": [["Cone", 15.0, 38.0, 900, "", "", ""]],
    }
    wiki = {"city": {"Right|10.000|50.000": ["Right", "Q1"], "Namesake|20.000|40.000": ["Namesake, Elsewhere", "Q2"], "Disambig|30.000|30.000": ["Disambig", "Q3"],
                     "Dead|0.000|10.000": ["Dead", "Q4"], "Twin A|60.000|60.000": ["Twin", "Q5"], "Twin B|60.050|60.000": ["Twin", "Q5"],
                     "Edge|0.000|0.000": ["Edge, Otherland", "Q14"], "Wïde|0.000|20.000": ["Wide", "Q15"], "Gone|1.000|1.000": ["Gone", "Q6"]},
            "country": {"AAA": ["Aland", "Q7"], "BBB": ["Bland", "Q8"], "CCC": ["Isles", "Q16"]}, "dispute": {"D|n": ["D", "Q9"]},
            "feature": {"Sea|sea|-30.000|0.000": ["Sea", "Q10"], "Hills|Range/mtn|5.000|5.000": ["Hills (elsewhere)", "Q11"], "Strait|strait|120.000|20.000": ["Strait", "Q17"],
                        "Twice|Range/mtn|-76.400|2.440": ["Twice", "Q19"],
                        "Belt|Geoarea|10.000|15.000": ["Belt, Elsewhere", "Q20"], "Shelf|Geoarea|10.000|-15.000": ["Shelf (region)", "Q21"]},
            "peak": {"Peak|86.900|28.000": ["Peak", "Q12"]}, "river": {"Flow|0|0": ["Flow", "Q13"], "Brook|3000|0": ["Brook", "Q18"]}, "volcano": {},
            "counts": {"city": [8, 9], "country": [3, 3], "dispute": [1, 1], "feature": [6, 6], "peak": [1, 1], "river": [2, 2], "volcano": [0, 1]}}
    at = lambda lon, lat: {"item": [lon, lat], "article": []}
    coords = {"Q1": at(10.2, 50.1), "Q2": at(-70.0, 40.0), "Q3": at(30.0, 30.0), "Q4": at(0.0, 10.0), "Q5": at(60.0, 60.0), "Q6": at(1.0, 1.0),
              "Q7": at(11.0, 51.0),            # inside Aland
              "Q8": at(115.0, 0.0),            # 1550 km outside Bland, whose box is 314 km across: too far even by name
              "Q9": at(0.52, 0.45),            # 6 km outside the disputed square, off its corner: within the 100 km floor
              "Q10": at(-10.0, 5.0),           # 2,280 km from the label point of a sea 10 degrees across: within 2.5 x 1,112 km
              "Q11": at(8.0, 5.0),             # 330 km from hills half a degree across, and the title is another place's: too far
              "Q12": at(86.925, 27.988),
              "Q13": {"item": None, "article": [[50.0, 50.0], [2.3, 0.2]]},   # no coordinate on the item; the article has the source and the mouth, 40 km past the last drawn point
              "Q14": at(0.0, 0.19),            # 21 km from a place of no people, under another title: just past the 20 km limit
              "Q15": at(0.0, 20.4),            # 44 km away, and the title is the card's name but for an accent: within three limits
              "Q16": at(180.0, 0.0),           # between two islets either side of the date line, 200 km from each: within half the spread
              "Q17": at(125.0, 20.0),          # 520 km from the label point of a strait drawn with no area: the title is its name, under 1000 km
              "Q19": at(-77.6, -9.2),          # a range drawn twice under one name: the article's range is 1,290 km from this one, whose own limit is 937 km
              "Q20": at(10.0, 36.0),           # found by name: a namesake 2,330 km off, inside the 5,000 km limit of a belt 18 degrees across: too far for a name
              "Q21": at(10.0, -36.0),          # the same distance under another title, but by Natural Earth's id: within the limit
              "Q18": at(30.9, 0.0)}            # 78 km past the end of a brook drawn 22 km long: too far, and three limits is 180 km... but the title is its name
    ok = lambda t: {"missing": False, "disambig": False, "to": t}
    enwiki = {t: ok(t) for t in ["Right", "Namesake, Elsewhere", "Twin", "Gone", "Aland", "Bland", "D", "Sea", "Hills (elsewhere)", "Peak", "Edge, Otherland", "Wide", "Isles", "Strait", "Brook", "Twice", "Belt, Elsewhere", "Shelf (region)"]}
    enwiki["Disambig"] = {"missing": False, "disambig": True, "to": "Disambig"}
    enwiki["Dead"] = {"missing": True, "disambig": False, "to": "Dead"}
    enwiki["Flow"] = {"missing": False, "disambig": False, "to": "Flow (river)"}
    S, findings, M = run({"wiki": wiki, "cards": cards, "coords": coords, "enwiki": enwiki, "checked": "2026-01-01", "build": {},
                          "by_name": {"feature": {"Belt|Geoarea|10.000|15.000"}}})
    want = {"orphan_keys": 1, "uncovered_city": 1, "uncovered_volcano": 1, "uncovered_country": 0, "uncovered_feature": 0, "uncovered_river": 0,
            "misplaced": 6,                # Namesake, Bland, Hills, Edge, Twice, Belt
            "by_name": 3,                  # Wïde, Strait, Brook
            "by_article_coord": 1,         # Flow
            "disambiguation": 1, "dead_titles": 1, "redirects": 1, "unchecked": 0, "shared_articles": 1}
    for k, v in want.items():
        assert M[k] == v, f"selftest: {k} is {M[k]}, known answer {v}\n" + "\n".join(f["what"] for f in findings) + "\n" + "\n".join(S["named"])
    named = " ".join(f["what"] for f in findings if f["check"] == "place")
    assert all(n in named for n in ("Namesake", "Bland", "Hills", "Edge", "Twice", "Belt")) and not any(n in named for n in ("Right", "Sea", "Flow", "Isles", "Strait", "Brook", "Wïde", "Shelf")), named
    assert n3(-0.0) == "0.000" and n3(139.749) == "139.749" and card_key("river", cards["river"][0]) == "Flow|0|0" and card_key("city", ["Dead", -0.0001, 10.0]) == "Dead|0.000|10.000"
    assert fold("Wïde") == fold("wide") and fold("Atakor Volcanic Field") == fold("Atakor volcanic field") and fold("El Progreso") != fold("El Progreso, Jutiapa")
    # a record that is not there is a failure, not a pass
    S2 = {"wiki": {"city": {"Right|10.000|50.000": ["Right", "Q1"]}, "counts": {k: ([1, 1] if k == "city" else [0, 0]) for k in KINDS}},
          "cards": {k: ([cards["city"][0]] if k == "city" else []) for k in KINDS}, "coords": {}, "enwiki": {}, "checked": None, "build": {}}
    _, f2, M2 = run(S2)
    assert M2["unchecked"] == 2 and all(f["severity"] == "HIGH" for f in f2), (M2, f2)
    print("selftest OK")


def _register(S, findings, M):
    lines = ["# Card text: which Wikipedia article belongs to which card", "",
             "Written by `Research/modeling/audit_cardtext.py`. The page shows, on a location card, the lead of one English Wikipedia",
             "article, fetched from en.wikipedia.org when the card opens; `web/data/wiki.json` names the article and",
             "`build/wiki_titles.py` chose it. No Wikipedia text is in the repository.", "",
             f"Titles last checked against en.wikipedia.org: {S.get('checked') or 'never'}.", "",
             "## Coverage", "", "| kind | cards | with an article | without | how the article was found |", "|---|---|---|---|---|"]
    names = {"ne": "Natural Earth's id", "geonames": "GeoNames id", "gvp": "Smithsonian volcano number", "name": "name search, place-checked"}
    for k in KINDS:
        n = len(S["cards"][k]); u = M[f"uncovered_{k}"]
        routes = S["build"].get(k, {}).get("routes", {})
        lines.append(f"| {k} | {n} | {n - u} ({100 * (n - u) / max(n, 1):.1f}%) | {u} | " + (", ".join(f"{names.get(r, r)} {v}" for r, v in sorted(routes.items(), key=lambda t: -t[1])) or "-") + " |")
    tot = sum(len(S["cards"][k]) for k in KINDS); un = sum(M[f"uncovered_{k}"] for k in KINDS)
    lines += [f"| all | {tot} | {tot - un} ({100 * (tot - un) / tot:.1f}%) | {un} | |", "",
              "A card with no article says so in one line and is otherwise complete. Rivers are counted by drawn reach: 462 reaches, of which",
              "12 have no name and one has no line, leave 449 that can open a card.", "",
              "## The place check", "", "The mapped Wikidata item's own coordinate (P625) must lie within a limit of the card's position:", ""]
    lines += [f"- **{k}**: {LIMITS[k]}" for k in KINDS]
    lines += ["", f"A mapping further off than its limit is kept only if the article's title is the card's own name, accents and case aside, AND it lies",
              f"within {WIDE:g} limits. For a feature the wider limit is 1000 km where its own is less, and no more: Natural Earth draws only a piece of",
              "some seas, straits and reefs, and it also draws two ranges under one name. For a state it is at least 1000 km: the Seychelles are drawn",
              "as one island. Where the item has no coordinate of its own (most rivers) the coordinates the English article carries stand in.",
              f"An article the build found by NAME (no id led to it) is held tighter: within {NAME_KM:g} km, or under the card's own name within the limit.",
              "A big thing's limit is thousands of km and a namesake fits inside it: the Sahel of Tunisia inside the Sahel's.", "",
              "| kind | checked | median distance / limit | 95th percentile | worst |", "|---|---|---|---|---|"]
    for k in KINDS:
        r = sorted(S["offsets"][k])
        if r:
            lines.append(f"| {k} | {len(r)} | {r[len(r) // 2]:.3f} | {r[min(len(r) - 1, int(len(r) * 0.95))]:.3f} | {r[-1]:.3f} |")
    lines += ["", f"Shipped mappings that fail the rule: **{M['misplaced']}**. Kept past the limit by name: {M['by_name']}. Checked by the article's coordinates: {M['by_article_coord']}.",
              f"Unchecked (no coordinate or no title record): **{M['unchecked']}**.",
              f"Disambiguation pages: **{M['disambiguation']}**. Titles that do not exist: **{M['dead_titles']}**. Redirects (followed by the page): {M['redirects']}.",
              f"Keys that open no card: **{M['orphan_keys']}**. Articles shared by two cards of a kind: {M['shared_articles']}.", ""]
    wrong = [(k, w) for k in KINDS for w in S["build"].get(k, {}).get("ne_wrong", [])]
    lines += ["## Natural Earth ids the build refused", "",
              f"{len(wrong)} of Natural Earth's `wikidataid` values did not pass (the item is somewhere else, has no English article, has no",
              "coordinate to check, or its article is a disambiguation page). Each was then tried by the other routes; the last column is what the card has now.", "",
              "| kind | card | why refused | article now |", "|---|---|---|---|"]
    for k, w in wrong:
        lines.append(f"| {k} | {w['key'].split('|')[0]} | {w['why']} | {w.get('now') or 'none'} |")
    found = [(k, w) for k in KINDS for w in S["build"].get(k, {}).get("found", [])]
    if found:
        lines += ["", "## Articles found without Natural Earth's id", "", "By GeoNames id, or by name (exactly one item of that name says it is that kind of thing, has an English article and passes the place check).", "",
                  "| kind | card | route | article | km |", "|---|---|---|---|---|"] + [f"| {k} | {w['key'].split('|')[0]} | {w['route']} | {w['title']} | {w['km']:.0f} |" for k, w in found]
    lines += ["", "## Cards without an article", ""]
    for k in KINDS:
        wo = S["build"].get(k, {}).get("without", [])
        if not wo:
            continue
        lines += [f"### {k} ({len(wo)})", ""]
        if len(wo) > 80:
            why = {}
            for w in wo:
                r = w["why"].split(";")[0]
                r = "".join(ch for ch in r if not ch.isdigit()).replace("Q:", "").strip()
                why[r] = why.get(r, 0) + 1
            lines += ["By first reason (numbers and ids taken out):", ""] + [f"- {v} x {r}" for r, v in sorted(why.items(), key=lambda t: -t[1])[:12]] + ["", "The first 40:", ""]
        lines += [f"- {w['key'].split('|')[0]}: {w['why']}" for w in wo[:40 if len(wo) > 80 else None]] + [""]
    if S["named"]:
        lines += ["## Kept past the limit because the article's title is the card's name", ""] + [f"- {t}" for t in S["named"]] + [""]
    sh = [f for f in findings if f["check"] == "shared"]
    if sh:
        lines += ["## One article on two cards", ""] + [f"- {f['what']}: {f['detail']}" for f in sh] + [""]
    hi = [f for f in findings if f["severity"] == "HIGH"]
    lines += ["## HIGH findings", ""] + ([f"- {f['check']}: {f['what']} {f['detail']}" for f in hi] or ["None."]) + [""]
    open(os.path.join(HERE, "REGISTER-cardtext.md"), "w").write("\n".join(lines))


def _report(findings):
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: order.get(f.get("severity", "LOW"), 9))
    shown = 0
    for f in findings:
        if f["severity"] == "LOW" and shown > 40:
            continue
        shown += 1
        print(f"{f['severity']:4}  {f['check']:9}  {f['what']}" + (f"\n      {f['detail']}" if f["detail"] else ""))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("HIGH", "MED", "LOW")}
    print(f"\n{len(findings)} findings: {counts['HIGH']} HIGH / {counts['MED']} MED / {counts['LOW']} LOW")
    return counts


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    S = load_subject()
    if "--live" in sys.argv:
        S["enwiki"] = live(S)
        import time
        S["checked"] = time.strftime("%Y-%m-%d", time.gmtime()) + " (asked again by this audit)"
    S, findings, M = run(S)
    _register(S, findings, M)
    if "--json" in sys.argv:
        gate = {k: M[k] for k in ["misplaced", "disambiguation", "dead_titles", "orphan_keys", "unchecked", "by_name", "shared_articles"] + [f"uncovered_{k}" for k in KINDS]}
        print(json.dumps(gate))
        sys.exit(0)
    counts = _report(findings)
    if S.get("checked"):
        import datetime
        age = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.date.fromisoformat(S["checked"][:10])).days
        print(f"titles checked against en.wikipedia.org {age} days ago" + (": run build/wiki_titles.py --recheck" if age > STALE_DAYS else ""))
    sys.exit(1 if counts["HIGH"] else 0)
