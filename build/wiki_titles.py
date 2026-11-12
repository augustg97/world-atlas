#!/usr/bin/env python3
"""Which English Wikipedia article belongs to which card.  Output: ../web/data/wiki.json

    ./venv/bin/python build/wiki_titles.py              # resolve, check, write (a cold cache is about two hours: see api())
    ./venv/bin/python build/wiki_titles.py --offline    # from the cache only; fails if a response is missing
    ./venv/bin/python build/wiki_titles.py --recheck    # ask en.wikipedia.org again whether every title still resolves
    ./venv/bin/python build/wiki_titles.py --stats      # also print, per kind, how far the items lie from the cards

The page shows a card's description by asking en.wikipedia.org for the lead of ONE article when the card opens
(web/js/wiki.js). This file decides which article, at build time, and stores a title and a Wikidata id per card.
No Wikipedia text is fetched or stored here: only titles, ids and coordinates.

WHERE AN ID COMES FROM, in this order, and the route is recorded for every card:
  ne        Natural Earth's own `wikidataid` attribute. The shipped populated-places and river files lack it, so
            the full places file (joined on ne_id) and the rivers by scale rank (joined on name AND geometry) are
            fetched through fetch_sources.py's Natural Earth route.
  geonames  a city Natural Earth gives no id: the item whose GeoNames ID (Wikidata P1566) is Natural Earth's.
  gvp       a volcano: the item whose Smithsonian Volcano ID (Wikidata P1886) is the catalogue's number.
  name      nothing else: Wikidata's entity search on the card's name, kept only if exactly ONE item carries that
            exact English label or alias, says in its description that it is that kind of thing (says_kind), has
            an English article, and passes the place check below in its stricter form (within 350 km, or under the
            card's own name within the limit). Never used for a volcano or a dispute.
Every route then passes the same checks or the card is left WITHOUT an article (no guessing):
  place     the item's own coordinate (P625) lies within a limit of the card's position that grows with the size of
            the thing (`offset_km`), or within three times that limit if the article's title IS the card's name
            (`passes`). Where the item has no coordinate (most rivers) the English article's own coordinates stand
            in. Research/modeling/audit_cardtext.py measures all of it again, with its own copy of the rule, on
            what is shipped. This is what catches a wrong id.
  article   the item has an English article, the title exists, and it is not a disambiguation page.
An id from Natural Earth that fails is tried again by name.

The output is keyed so web/js/wiki.js can look a card up WITHOUT touching places.json, political.json or
physical.json (their row order is an id that three other readers share). The keys are made of the card's own
shipped values; `card_key` here and `wikiKey` in web/js/wiki.js are the same rule, and build/test_app_math.mjs
counts the page's lookups against the counts written here.

Sources: Natural Earth 5.1.2 (public domain); Wikidata (CC0) through www.wikidata.org/w/api.php; article
existence from en.wikipedia.org/w/api.php (titles and page properties only). Raw responses are cached under the
ignored data/_cache/wiki/. Requests are serial, carry a generic User-Agent and nothing about the project.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from units import admin_units

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "web", "data")
CACHE = os.path.join(DATA, "_cache", "wiki")
WD = "https://www.wikidata.org/w/api.php"
WP = "https://en.wikipedia.org/w/api.php"
UA = "atlas-build-script/1.0 (python-urllib; serial, cached)"
R_KM = 6371.0088
OFFLINE = "--offline" in sys.argv
KINDS = ["city", "country", "dispute", "feature", "peak", "river", "volcano"]


# ------------------------------------------------------------------------------------ the network, cached
GAP_S = 6.5          # seconds between requests that go to the network
_last = [0.0]


def api(host, params, fresh=False, pace=0.0):
    """One GET of a MediaWiki API, answered from data/_cache/wiki/ (gzipped, as received) when it has been asked
    before. Returns JSON.

    PACING. Since 2026 Wikimedia allows a client that does not identify itself with contact details TEN requests a
    minute, across all its sites (mediawiki.org/wiki/Wikimedia_APIs/Rate_limits; a User-Agent with an address or
    an e-mail gets 200). This script sends a generic User-Agent on purpose and nothing about the project, so it
    keeps under ten: one request every GAP_S seconds, and it waits as long as a 429 says. A cold cache is about
    a thousand requests, so about two hours; a warm one is no requests at all."""
    params = dict(params, format="json", formatversion="2")
    q = urllib.parse.urlencode(sorted(params.items()))
    tag = "wd" if host == WD else "wp"
    p = os.path.join(CACHE, tag, hashlib.sha1(q.encode()).hexdigest() + ".json.gz")
    if os.path.exists(p) and not fresh:
        return json.loads(gzip.open(p).read())
    if OFFLINE:
        raise SystemExit(f"--offline, and this request is not in the cache: {host}?{q[:200]}")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    for k in range(8):
        wait = 5 * (k + 1)
        time.sleep(max(0.0, _last[0] + GAP_S - time.time()))
        _last[0] = time.time()
        try:
            req = urllib.request.Request(host + "?" + q, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
            j = json.loads(b)
            if "error" in j:                                   # a rate limit: wait and ask again; anything else is a bug here
                if j["error"].get("code") in ("maxlag", "ratelimited"):
                    raise IOError(j["error"].get("info", "busy"))
                raise SystemExit(f"API error for {q[:200]}: {j['error']}")
            with gzip.open(p, "wb") as f:
                f.write(b)
            return j
        except urllib.error.HTTPError as e:
            if e.code == 429:                                  # asked to slow down: do as the host says
                wait = max(wait, int(e.headers.get("Retry-After") or 0) + 2, 30)
            print(f"  retry (HTTP {e.code}); waiting {wait}s", flush=True)
        except (urllib.error.URLError, IOError, TimeoutError) as e:
            print(f"  retry ({e}); waiting {wait}s", flush=True)
        time.sleep(wait)
    raise SystemExit(f"could not fetch {host}?{q[:200]}")


def chunks(seq, n=50):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def progress(label, i, n):
    if i % 20 == 0 or i == n:
        print(f"\r  {label}: {i}/{n}", end="" if i < n else "\n", flush=True)


def sitelinks(qids):
    """qid -> (resolved qid, enwiki title or None). A merged item answers under its target; a deleted one is None."""
    out = {}
    groups = list(chunks(sorted(set(qids))))
    for n, grp in enumerate(groups, 1):
        j = api(WD, {"action": "wbgetentities", "ids": "|".join(grp), "props": "sitelinks", "sitefilter": "enwiki"})
        for key, e in j.get("entities", {}).items():
            asked = e.get("redirects", {}).get("from", key)
            if "missing" in e:
                out[asked] = (None, None)
            else:
                out[asked] = (e["id"], e.get("sitelinks", {}).get("enwiki", {}).get("title"))
        progress("sitelinks", n, len(groups))
    return out


def coordinates(qids):
    """qid -> (lon, lat) of the item's primary coordinate on Earth (P625), or absent."""
    out = {}
    groups = list(chunks(sorted(set(qids))))
    for n, grp in enumerate(groups, 1):
        j = api(WD, {"action": "query", "prop": "coordinates", "titles": "|".join(grp), "colimit": "max", "coprimary": "primary"})
        assert "continue" not in j, "coordinates were cut short; lower the batch size"
        for pg in j["query"]["pages"]:
            for c in pg.get("coordinates", []):
                if c.get("globe", "earth") == "earth" and c.get("primary"):
                    out[pg["title"]] = (c["lon"], c["lat"])
        progress("coordinates", n, len(groups))
    return out


def by_statement(prop, value):
    """The items that carry an external id: Wikidata's own search, exact on the statement."""
    j = api(WD, {"action": "query", "list": "search", "srsearch": f"haswbstatement:{prop}={value}", "srnamespace": "0", "srlimit": "5", "srprop": ""}, pace=2.0)
    return [h["title"] for h in j["query"]["search"]]


def index_of(prop):
    """value -> [qids] for EVERY item that carries an external-id property: a few pages of search and the items'
    own statements, where asking once per value would be thousands of rate-limited searches."""
    qids, off = [], 0
    while True:
        j = api(WD, {"action": "query", "list": "search", "srsearch": f"haswbstatement:{prop}", "srnamespace": "0", "srlimit": "500", "srprop": "", "sroffset": str(off)}, pace=2.0)
        qids += [h["title"] for h in j["query"]["search"]]
        if "continue" not in j:
            break
        off = j["continue"]["sroffset"]
    out = {}
    groups = list(chunks(sorted(set(qids))))
    for n, grp in enumerate(groups, 1):
        j = api(WD, {"action": "wbgetentities", "ids": "|".join(grp), "props": "claims"}, pace=0.5)
        for e in j.get("entities", {}).values():
            for st in e.get("claims", {}).get(prop, []):
                v = st.get("mainsnak", {}).get("datavalue", {}).get("value")
                if v is not None and st.get("rank") != "deprecated":
                    out.setdefault(str(v).strip(), [])
                    if e["id"] not in out[str(v).strip()]:
                        out[str(v).strip()].append(e["id"])
        progress(f"items with {prop}", n, len(groups))
    return out


def by_name(name):
    """Items whose English label or alias IS the name (Wikidata's entity search matches prefixes; those are dropped),
    each with its English description: [(qid, description)]."""
    j = api(WD, {"action": "wbsearchentities", "search": name, "language": "en", "uselang": "en", "type": "item", "limit": "30"})
    want = name.casefold()
    return [(h["id"], h.get("description") or "") for h in j.get("search", [])
            if h.get("match", {}).get("text", "").casefold() == want and h["match"].get("type") in ("label", "alias")]


# What an item found BY NAME must say it is, in the head of its English description on Wikidata (the words before
# the first "in", "of", "on", "at", comma or bracket: "city in Japan", "river in Russia", "mountain range of ...").
# A namesake of another kind that happens to lie nearby (the state of Colorado beside the river Colorado, a railway
# station in a town) fails here. An id from Natural Earth or from an external identifier is not put through this.
HEAD = re.compile(r"\s+(?:in|of|on|at|near|between|within|along|off)\s+|[,(;]")
SAYS = {
    "city": re.compile(r"\b(city|town|village|municipality|capital|settlement|commune|locality|township|borough|suburb|hamlet|community|metropolis|port)\b"),
    "river": re.compile(r"\b(river|stream|canal|tributary|distributary|watercourse|creek|waterway)\b"),
    "peak": re.compile(r"\b(mountain|peak|volcano|stratovolcano|summit|massif|hill|depression|basin|valley|crater|dome|landform|point)\b"),   # the elevation points hold low points too
    "land": re.compile(r"\b(mountains?|range|hills|massif|highlands?|uplands?|cordillera|islands?|archipelago|atoll|plateau|plain|basin|lowlands?|tundra|desert|valley|gorge|canyon|coast|delta|"
                       r"wetlands?|swamp|marsh|peninsula|cape|headland|isthmus|steppe|landform|continent|region|subcontinent|zone|belt)\b"),
    "sea": re.compile(r"\b(sea|gulf|bay|strait|channel|ocean|sound|reef|river|lake|estuary|lagoon|bight|passage|inlet)\b"),
}
NOT_A_PLACE = re.compile(r"\b(station|airport|district|province|county|governorate|oblast|prefecture|department|state|voivodeship|constituency|diocese|battle|"
                         r"company|club|ship|film|album|family|given|surname|disambiguation)\b")


def says_kind(kind, card, description):
    head = HEAD.split(description.strip().lower(), 1)[0]
    want = SAYS.get(kind if kind in SAYS else card.get("realm", "land") if kind == "feature" else "")
    return bool(want and want.search(head) and not NOT_A_PLACE.search(head))


def _read_info(j, pages, alias):
    """What one answer of en.wikipedia.org says: per page, missing / disambiguation / its own coordinates; and which
    asked title leads to which page (normalisation, redirects)."""
    q = j.get("query", {})
    for pg in q.get("pages", []):
        e = pages.setdefault(pg["title"], {"missing": False, "disambig": False, "coords": []})
        e["missing"] = e["missing"] or bool(pg.get("missing")) or bool(pg.get("invalid"))
        e["disambig"] = e["disambig"] or "disambiguation" in pg.get("pageprops", {})
        for c in pg.get("coordinates", []):
            pt = [c["lon"], c["lat"]]
            if c.get("globe", "earth") == "earth" and pt not in e["coords"]:
                e["coords"].append(pt)
    redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
    alias.update(redir)
    for n in q.get("normalized", []):
        alias[n["from"]] = redir.get(n["to"], n["to"])


def enwiki_info(titles, fresh=False):
    """title -> {'missing', 'disambig', 'to': the title after redirects, 'coords': the article's own coordinates
    ([lon, lat], the primary one first where there is one)}. Titles already answered in the cache are not asked
    again, whatever batch they were asked in, unless `fresh`."""
    pages, alias = {}, {}
    wp = os.path.join(CACHE, "wp")
    if not fresh and os.path.isdir(wp):
        for f in sorted((os.path.join(wp, n) for n in os.listdir(wp)), key=os.path.getmtime):
            _read_info(json.loads(gzip.open(f).read()), pages, alias)
    known = lambda t: alias.get(t, t) in pages
    groups = list(chunks(sorted(t for t in set(titles) if fresh or not known(t))))
    for n, grp in enumerate(groups, 1):
        more = {}
        while True:                                            # a batch with many coordinates comes in several answers
            j = api(WP, dict({"action": "query", "titles": "|".join(grp), "prop": "pageprops|coordinates", "ppprop": "disambiguation", "redirects": "1",
                              "coprimary": "all", "colimit": "max"}, **more), fresh=fresh)
            _read_info(j, pages, alias)
            if "continue" not in j:
                break
            more = j["continue"]
        progress("enwiki", n, len(groups))
    lost = [t for t in set(titles) if not known(t)]
    assert not lost, f"en.wikipedia.org answered nothing for {lost[:5]}"
    return {t: dict(pages[alias.get(t, t)], to=alias.get(t, t)) for t in set(titles)}


# ------------------------------------------------------------------------------------ the cards, as shipped
def n3(v):
    """A coordinate as the page prints it for a key: three decimals, and no negative zero (JS toFixed(3))."""
    s = f"{v:.3f}"
    return "0.000" if s == "-0.000" else s


def card_key(kind, c):
    """The same rule as wikiKey() in web/js/wiki.js. Made only of values the page holds for the card."""
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


def km(lon1, lat1, lon2, lat2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_KM * math.asin(min(1.0, math.sqrt(a)))


def km_to_points(lon, lat, flat):
    """Great-circle distance from a point to the nearest of many (a flat [lon*100, lat*100, ...] list), km."""
    a = np.asarray(flat, dtype=np.float64).reshape(-1, 2) / 100.0
    p1, p2 = math.radians(lat), np.radians(a[:, 1])
    dl = np.radians(a[:, 0] - lon)
    h = np.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * R_KM * np.arcsin(np.sqrt(np.clip(h.min(), 0, 1))))


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


def fold(name):
    """A name for comparing: no accents, no case, letters and digits only."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", name or "") if ch.isalnum() and not unicodedata.combining(ch)).casefold()


def extent_km(polys, lon0):
    """The diagonal of the box round ALL the parts of a unit (an archipelago is as big as its spread). Longitudes are
    taken round lon0, so a unit that crosses the date line is not the whole world wide."""
    a = np.concatenate([np.asarray(poly[0], dtype=np.float64).reshape(-1, 2) / 100.0 for poly in polys])
    x = ((a[:, 0] - lon0 + 180.0) % 360.0) - 180.0 + lon0
    return km(x.min(), a[:, 1].min(), x.max(), a[:, 1].max())


def offset_km(kind, c, pts, ctx):
    """How far the nearest of an item's coordinates lies from the card: (distance in km, the limit in km)."""
    def one(lon, lat):
        if kind in ("city", "volcano"):
            return km(lon, lat, c[1], c[2])
        if kind in ("peak", "feature"):
            return km(lon, lat, c["lon"], c["lat"])
        if kind in ("country", "dispute"):
            return 0.0 if inside(lon, lat, c["polys"]) else km_to_points(lon, lat, [v for poly in c["polys"] for v in poly[0]])
        return km_to_points(lon, lat, ctx["river_pts"][c["name"]])      # a river: the nearest drawn point of any reach of that name
    d = min(one(lon, lat) for lon, lat in pts)
    if kind == "city":
        return d, 20 + 0.012 * math.sqrt(max(c[3], 0))         # 20 km for a village, 58 km for a city of ten million
    if kind in ("volcano", "peak"):
        return d, 30.0
    if kind in ("country", "dispute"):
        return d, max(100.0, 0.5 * extent_km(c["polys"], c["lon"]))
    if kind == "feature":
        return d, max(150.0, 2.5 * c["size"] * 111.2)          # size: the side of a square of its drawn area, degrees
    return d, max(60.0, ctx["river_km"][c["name"]])            # a river's coordinate is its mouth or its source: within its drawn length


WIDE = 3.0
NAME_KM = 350.0        # an article found BY NAME under another title must lie this close, whatever the thing's size


def wide_km(kind, lim):
    """How far off a mapping may lie when the article's title IS the card's name. Three limits, as a rule. A feature:
    1000 km where its own limit is less, and no more (Natural Earth draws only a piece of some seas, straits and
    reefs, and it also draws two ranges under one name: the Cordillera Blanca in Peru, and again in Colombia). A
    state: at least 1000 km (the Seychelles are drawn as one island; the item's coordinate is the archipelago's)."""
    return max(lim, 1000.0) if kind == "feature" else max(WIDE * lim, 1000.0) if kind == "country" else WIDE * lim


def passes(kind, name, title, d, lim):
    """'near': inside the limit. 'named': inside the wider limit, and the article's title IS the card's name. Else None."""
    if d <= lim:
        return "near"
    if d <= wide_km(kind, lim) and fold(title) == fold(name):
        return "named"
    return None


def load_cards():
    """Every location card the page can open, as the page holds it, with Natural Earth's id where it has one."""
    places = json.load(open(os.path.join(OUT, "places.json")))
    pol = json.load(open(os.path.join(OUT, "political.json")))
    phys = json.load(open(os.path.join(OUT, "physical.json")))
    volc = json.load(open(os.path.join(OUT, "volcanoes.json")))
    ne = lambda name: json.load(open(os.path.join(DATA, "ne", f"{name}.geojson")))["features"]
    def wid(p):
        v = (p.get("WIKIDATAID") or p.get("wikidataid") or "").strip()
        return v if re.fullmatch(r"Q[1-9][0-9]*", v) else None          # anything else is not an id, and would fail a whole batch
    cards = {k: [] for k in KINDS}          # each: {"card": the shipped object, "ne": qid or None, "alt": {...}}

    # cities: the shipped row -> the simple file's feature (name and rounded position) -> ne_id -> the full file
    simple = {(f["properties"]["name"], round(f["properties"]["longitude"], 3), round(f["properties"]["latitude"], 3)): f["properties"]["ne_id"]
              for f in ne("ne_10m_populated_places_simple")}
    full = {f["properties"]["NE_ID"]: f["properties"] for f in ne("ne_10m_populated_places")}
    for r in places["rows"]:
        p = full[simple[(r[0], r[1], r[2])]]
        gn = p.get("GEONAMESID")
        cards["city"].append({"card": r, "ne": wid(p), "geonames": int(gn) if gn and gn > 0 else None})

    units = {f["properties"]["ADM0_A3"]: f["properties"] for f in admin_units(DATA)}
    for c in pol["countries"]:
        cards["country"].append({"card": c, "ne": wid(units[c["a3"]])})

    brk = {}
    for f in ne("ne_50m_admin_0_breakaway_disputed_areas"):
        p = f["properties"]
        brk.setdefault((p.get("BRK_NAME") or p.get("NAME"), p.get("NOTE_BRK")), wid(p))
    for d in pol["disputes"]:
        cards["dispute"].append({"card": d, "ne": brk[(d["name"], d["note"])]})

    # physical.json is written in the files' own order (vectors.step_physical): walk both together and insist they agree
    src = [(p["NAME_EN"] or p["NAME"], p["FEATURECLA"], wid(p)) for p in (f["properties"] for f in ne("ne_50m_geography_regions_polys"))]
    src += [(p["name_en"] or p["name"], p["featurecla"], wid(p)) for p in (f["properties"] for f in ne("ne_50m_geography_marine_polys"))]
    assert len(src) == len(phys["features"]), (len(src), len(phys["features"]))
    for f, (name, kind, q) in zip(phys["features"], src):
        assert (f["name"], f["kind"]) == (name, kind), (f["name"], name)
        cards["feature"].append({"card": f, "ne": q})
    src = [f["properties"] for f in ne("ne_50m_geography_regions_elevation_points")]
    assert len(src) == len(phys["peaks"])
    for pk, p in zip(phys["peaks"], src):
        assert pk["name"] == (p["name_en"] or p["name"]) and pk["elev"] == p["elevation"], pk
        if pk["name"]:
            cards["peak"].append({"card": pk, "ne": wid(p)})

    # rivers: the drawn file has no ids; the same centrelines cut by scale rank do. Join on the name AND on the line.
    from scipy.spatial import cKDTree
    ranked = {}
    for fn, tol in (("ne_50m_rivers_lake_centerlines_scale_rank", 0.03), ("ne_10m_rivers_lake_centerlines_scale_rank", 0.2)):
        for f in ne(fn):
            p, g = f["properties"], f["geometry"]
            if not g or not wid(p):
                continue
            pts = [pt[:2] for line in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]) for pt in line]
            for nm in {p.get("name"), p.get("name_en")} - {None, ""}:
                ranked.setdefault(nm, []).append((wid(p), np.asarray(pts, dtype=np.float64), tol))
    for r in phys["rivers"]:
        if not r["name"] or not r["lines"] or not r["lines"][0]:
            continue                                                    # twelve drawn reaches have no name and one has no line: no card
        mine = np.asarray([v for line in r["lines"] for v in line], dtype=np.float64).reshape(-1, 2) / 100.0
        tree = cKDTree(mine)
        ids = {}
        for q, pts, tol in ranked.get(r["name"], []):
            d, _ = tree.query(pts)
            share = float((d < tol).mean())
            if share > 0.5:                                             # most of that piece lies on this reach
                ids[q] = ids.get(q, 0) + int((d < tol).sum())
        cards["river"].append({"card": r, "ne": max(ids, key=ids.get) if len(ids) == 1 else None, "ne_many": sorted(ids) if len(ids) > 1 else None})

    # volcanoes: the shipped row -> the catalogue's own number (the Smithsonian's), from the cached NCEI pages
    num = {}
    n = 1
    while os.path.exists(os.path.join(DATA, "_cache", f"ncei_volc_{n}.json")):
        for v in json.load(open(os.path.join(DATA, "_cache", f"ncei_volc_{n}.json")))["items"]:
            if v.get("latitude") is not None and v.get("longitude") is not None:
                num.setdefault((v.get("name"), round(v["longitude"], 3), round(v["latitude"], 3)), v.get("newNum"))
        n += 1
    for v in volc["rows"]:
        cards["volcano"].append({"card": v, "ne": None, "gvp": num.get((v[0], v[1], v[2]))})

    ctx = {"river_pts": {}, "river_km": {}}                 # per river name: every drawn point, and the drawn length
    for r in phys["rivers"]:
        if r["name"]:
            ctx["river_pts"].setdefault(r["name"], []).extend(v for line in r["lines"] for v in line)
            ctx["river_km"][r["name"]] = ctx["river_km"].get(r["name"], 0.0) + sum(
                km(l[i] / 100.0, l[i + 1] / 100.0, l[i + 2] / 100.0, l[i + 3] / 100.0) for l in r["lines"] for i in range(0, len(l) - 3, 2))
    return cards, ctx


# ------------------------------------------------------------------------------------ resolve and check
def card_name(k, c):
    return c[0] if k in ("city", "volcano") else c["name"]


def main():
    cards, ctx = load_cards()
    for k in KINDS:
        keys = [card_key(k, c["card"]) for c in cards[k]]
        # two drawn reaches of one river can start at the same point under the same name: they share a key, and an article
        # (the volcano catalogue lists a few volcanoes twice, name and position alike; the same holds for them)
        assert k in ("river", "volcano") or len(set(keys)) == len(keys), f"{k}: two cards share a key"
    print({k: len(v) for k, v in cards.items()})
    todo = [(k, c) for k in KINDS for c in cards[k]]

    # 1. candidate ids by the exact routes
    gvp = index_of("P1886")                                             # Smithsonian volcano number -> items
    for c in cards["volcano"]:
        c["gvp_hits"] = gvp.get(str(c["gvp"]), []) if c.get("gvp") else []
    need_gn = [c for c in cards["city"] if not c["ne"] and c.get("geonames")]
    for i, c in enumerate(need_gn, 1):
        c["gn_hits"] = by_statement("P1566", c["geonames"])
        progress("GeoNames ids", i, len(need_gn))

    def ids():
        return {q for _, c in todo for q in [c.get("ne")] + c.get("gvp_hits", []) + c.get("gn_hits", []) + c.get("name_hits", []) if q}

    links = sitelinks(ids())
    coords = coordinates({v[0] for v in links.values() if v[0]})
    art = enwiki_info({v[1] for v in links.values() if v[1]}, fresh="--recheck" in sys.argv)

    def judge(k, c, q, by_name=False):
        """((title, qid, km, limit, witness, how), None) if this item may stand for the card, else (None, why).
        Found by name, the place check is stricter: a big thing's limit is thousands of km, and a namesake fits inside
        it (the Sahel of Tunisia inside the Sahel's). Then the article lies within NAME_KM, or its title IS the card's
        name and it lies within the limit; never further."""
        rq, title = links.get(q, (None, None))
        if not rq:
            return None, "the item does not exist"
        if not title:
            return None, "the item has no English article"
        a = art[title]
        if a["missing"]:
            return None, f"the article '{title}' does not exist"
        if a["disambig"]:
            return None, f"'{title}' is a disambiguation page"
        pts, witness = ([coords[rq]], "item") if rq in coords else (a["coords"], "article")
        if not pts:
            return None, "neither the item nor its article has a coordinate to check"
        d, lim = offset_km(k, c["card"], pts, ctx)
        how = passes(k, card_name(k, c["card"]), title, d, lim)
        if by_name:
            how = "near" if d <= min(lim, NAME_KM) or (d <= lim and fold(title) == fold(card_name(k, c["card"]))) else None
        if not how:
            return None, f"the {witness}'s coordinate lies {d:.0f} km away (limit {lim:.0f} km{', or ' + format(NAME_KM, '.0f') + ' km under another title' if by_name else ''})"
        return (title, rq, round(d, 1), round(lim, 1), witness, how), None

    # 2. the exact routes, judged
    for k, c in todo:
        c["tried"], c["got"] = [], None
        for route, qs in (("ne", [c.get("ne")] if c.get("ne") else []), ("gvp", c.get("gvp_hits", [])), ("geonames", c.get("gn_hits", []))):
            if c["got"] or not qs:
                continue
            # an external id can sit on several items (a volcano and its field; a duplicate): the one of them that
            # has an English article and is in the right place stands for the card, if it is the only one
            res = [(q,) + judge(k, c, q) for q in qs]
            ok = list({g[1]: g for _, g, _ in res if g}.values())
            if len(ok) == 1:
                c["got"] = (route,) + ok[0]
            elif len(qs) == 1:
                c["tried"].append((route, f"{qs[0]}: {res[0][2]}"))
            else:
                c["tried"].append((route, f"{len(qs)} items carry that id ({', '.join(qs)}) and {len(ok)} pass"))

    # 3. by name, for what is left. Not by name: a volcano (it has its number or nothing: the names repeat), a dispute
    # (too much rides on which article), and a drawn reach that holds two rivers of one name.
    for k, c in todo:
        if c.get("ne_many"):
            c["tried"].append(("ne", f"the drawn reach holds more than one river of this name ({', '.join(c['ne_many'])})"))
    left = [(k, c) for k, c in todo if not c["got"] and k not in ("volcano", "dispute") and not c.get("ne_many")]
    for i, (k, c) in enumerate(left, 1):
        found = [(q, d) for q, d in by_name(card_name(k, c["card"])) if q != c.get("ne")]
        c["name_found"] = len(found)
        c["name_hits"] = [q for q, d in found if says_kind(k, c["card"], d)]
        progress("name searches", i, len(left))
    links.update(sitelinks(ids() - set(links)))
    coords.update(coordinates({v[0] for v in links.values() if v[0]} - set(coords)))
    art.update(enwiki_info({v[1] for v in links.values() if v[1]} - set(art)))
    for k, c in left:
        ok = list({g[1]: g for g in (judge(k, c, q, by_name=True)[0] for q in c["name_hits"]) if g}.values())
        if len(ok) == 1:
            c["got"] = ("name",) + ok[0]
        else:
            c["tried"].append(("name", f"{c['name_found']} other items carry the name, {len(c['name_hits'])} say they are this kind of thing, {len(ok)} pass the place check"
                               + ("" if len(ok) < 2 else ": " + ", ".join(g[1] for g in ok))))

    # 4. write
    out = {"note": "English Wikipedia article title and Wikidata id per location card. Keys are made of each card's own shipped values (wikiKey in js/wiki.js). "
                   "The article's text is fetched by the page when a card opens and is never stored here.",
           "source": "Natural Earth 5.1.2 wikidataid attributes (public domain); Wikidata sitelinks and external ids (CC0); article existence checked on en.wikipedia.org",
           "checked": time.strftime("%Y-%m-%d", time.gmtime()), "counts": {}}
    report = {"checked": out["checked"], "kinds": {}, "coords": {}, "enwiki": {}}
    for k in KINDS:
        table, clash = {}, set()
        rep = {"mapped": 0, "total": len(cards[k]), "routes": {}, "how": {}, "witness": {}, "ne_wrong": [], "without": [], "redirects": []}
        for c in cards[k]:
            key = card_key(k, c["card"])
            ne_fail = [t for t in c["tried"] if t[0] == "ne"]
            if ne_fail:
                rep["ne_wrong"].append({"key": key, "why": ne_fail[0][1], "now": f"{c['got'][1]} (by {c['got'][0]})" if c["got"] else None})
            if c["got"]:
                route, title, q, d, lim, witness, how = c["got"]
                if table.get(key, [title, q]) != [title, q]:               # two reaches under one key that disagree: neither
                    clash.add(key)
                table[key] = [title, q]
                rep["mapped"] += 1
                for name, v in (("routes", route), ("how", how), ("witness", witness)):
                    rep[name][v] = rep[name].get(v, 0) + 1
                if route != "ne" and route != "gvp":
                    rep.setdefault("found", []).append({"key": key, "route": route, "title": title, "km": d})
                if art[title]["to"] != title:
                    rep["redirects"].append({"key": key, "title": title, "to": art[title]["to"]})
                # what the audit measures again: the item's own coordinate, and the article's where the item has none
                report["coords"][q] = {"item": coords.get(q), "article": art[title]["coords"]}
                report["enwiki"][title] = {"missing": art[title]["missing"], "disambig": art[title]["disambig"], "to": art[title]["to"]}
            else:
                rep["without"].append({"key": key, "why": "; ".join(f"{r}: {w}" for r, w in c["tried"]) or ("no number in the catalogue, or no item with it" if k == "volcano" else "no id")})
        for key in clash:
            del table[key]
            n = sum(1 for c in cards[k] if card_key(k, c["card"]) == key)
            rep["mapped"] -= n
            rep["without"].append({"key": key, "why": f"{n} reaches share this key and resolve to different articles"})
        out[k] = table
        out["counts"][k] = [rep["mapped"], rep["total"]]
        report["kinds"][k] = rep
        print(f"  {k:8} {rep['mapped']:5} of {rep['total']:5}  routes {rep['routes']}  {rep['how']}  witness {rep['witness']}  Natural Earth ids refused {len(rep['ne_wrong'])}  redirects {len(rep['redirects'])}")

    if "--stats" in sys.argv:
        for k in KINDS:
            r = sorted((c["got"][3] / c["got"][4] for c in cards[k] if c["got"]), reverse=True)
            if r:
                print(f"  {k:8} distance / limit: median {r[len(r) // 2]:.3f}, 95th {r[len(r) // 20]:.3f}, worst {r[0]:.3f}")

    # Landmarks: known cards must have their known articles.
    assert out["city"]["Tokyo|139.749|35.687"] == ["Tokyo", "Q1490"], out["city"].get("Tokyo|139.749|35.687")
    assert out["country"]["JPN"][0] == "Japan" and out["country"]["GUF"][0] == "French Guiana", (out["country"].get("JPN"), out["country"].get("GUF"))
    assert any(v[0] == "Mount Everest" for v in out["peak"].values()) and any(v[0] == "Danube" for v in out["river"].values())
    assert any(v[0] == "Mediterranean Sea" for v in out["feature"].values()) and len(out["dispute"]) >= 10, len(out["dispute"])
    assert out["counts"]["city"][0] > 0.9 * out["counts"]["city"][1], out["counts"]["city"]

    json.dump(out, open(os.path.join(OUT, "wiki.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(report, open(os.path.join(CACHE, "report.json"), "w"), indent=1, ensure_ascii=False)
    print(f"  wiki.json: {os.path.getsize(os.path.join(OUT, 'wiki.json')) / 1024:.0f} KB; the report is in data/_cache/wiki/report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
