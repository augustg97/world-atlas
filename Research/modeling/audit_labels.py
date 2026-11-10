"""Which states are named, and whether every name drawn is legible and true (register F1).

The baseline sheet (National Geographic, The World - Political) names every state at the whole-Earth
framing. This audit opens the frozen page headless at 1440 x 900 and asks the label layer what it
actually drew (measure what is drawn, not what is in the data), at 24 framings: the whole-Earth sheet,
the globe, five regions at 12 and 6 km a pixel on both, and two more on the sheet (see CARRIED). For each it reports

    states named, full and abbreviated counted separately, of the states in the window

and three checks that must be ZERO, none of which trusts the label layer's own account of itself:

    overlaps    two names whose INK overlaps (ink boxes re-measured here with measureText), or whose
                rectangles overlap, or a leader line through another name or across another leader
    under_9px   a name set in type smaller than 9 px
    misplaced   a state's name that sits on a different country than its own. The ground under each
                name is found with the camera's exact inverse and tested against the Natural Earth
                source polygons (data/ne), not against the layer's raster or the shipped JSON:
                  a name with a leader   - the leader must end on its own state, and the name must lie
                                           on no other country (10% of it at most, and not its centre)
                  a name without one     - centred on its own state with no more than a quarter of it
                                           on others; or, set beside it, within 4 px of its own state
                                           (touching, to the eye) and on no other country (10% at most,
                                           and not its centre)
                Distances are measured on the screen, in pixels, from the name's ink box and the leader's
                end to the state's outline.

Units that are not states (dependencies, non-home parts, indeterminate and disputed areas) keep one
position at their label point by design (CLAUDE.md rule 14 forbids changing how a dispute is named);
the same test is run on them and reported apart as misplaced_other_units, which is not a zero check.

Two counts of "state" are reported. The original keys count Natural Earth TYPE in ('Sovereign country',
'Country') = 204 units; that set leaves out Kazakhstan, Cuba, Israel and Kosovo (typed Sovereignty and
Disputed) and takes in ten non-home parts (Greenland, Hong Kong, Macao, Aruba, Curacao, Sint Maarten,
Jersey, Guernsey, Isle of Man, Aland). The keys with 198 count what the label layer treats as a state:
the home part of a sovereignty that Natural Earth types as a country, a sovereignty or a
self-administering disputed state (the 193 UN members, the Vatican, Taiwan, Kosovo, N. Cyprus, Somaliland).

    "$STUDIO/.venv/bin/python" Research/modeling/audit_labels.py [--json] [--port 8150] [--list]   # needs build/serve.py
    python Research/modeling/audit_labels.py --selftest        # no browser: planted faults must be caught
"""
import json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = "t=2026-06-21T12:00Z"
PAGES = {"sheet": f"/?frozen=1#{T}&v=sheet&s=atlas&on=daylight,borders,labels,ice",
         "globe": f"/?frozen=1#{T}&v=globe&s=space&ll=15,20&on=daylight,clouds,air,ice,lights,borders,labels"}
REGIONS = {"europe": (15, 50), "caribbean": (-70, 17), "wafrica": (-5, 10), "gulf": (50, 26), "seasia": (110, 8)}
SCALES = (12, 6)
# The sheet's layout is solved on a 5% ladder of scales and carried to the real one (overlays.js). 12 and 6 km a pixel
# sit near a rung; these two sit at the far end of one (5.80 and 11.48 are carried 4.8%), where a fault of the carrying would show.
CARRIED = (("europe", 5.8), ("seasia", 11.48))
MIN_PX = 9.0
TOL_PX = 1.5                 # a leader's end may be this far from its state's outline
TOUCH_PX = 4.0               # a name set beside its state with no leader may be this far from it
ON_OTHERS_BESIDE = 0.10      # share of a name set beside its state (or on a leader) that may lie on other countries
ON_OTHERS_INSIDE = 0.25      # share of a name centred on its state that may lie on other countries
NX, NY = 15, 5               # samples over a name's ink box, at cell centres (shares of its area); the middle one is its centre

# Runs in the page. Everything geometric is taken from the camera (cam.unproject is the exact inverse; the label
# layer uses its own table) and from a fresh canvas (ink boxes), so the layer's rectangles are checked, not trusted.
JS = """([NX, NY]) => {
  const L = ATLAS.labels, cam = ATLAS.cam, W = cam.w, H = cam.h;
  const g = document.createElement('canvas').getContext('2d');
  const ll = (x, y) => { const p = cam.unproject(x, y); return p ? [+p[0].toFixed(4), +p[1].toFixed(4)] : null; };
  const out = [];
  for (const p of L.placed) {
    let ink = [p.x0, p.y0, p.x1, p.y1], measured = false;
    if (p.lines && p.font) {
      g.font = p.font; g.textBaseline = p.base || 'middle';
      if ('letterSpacing' in g) g.letterSpacing = (p.spacing || 0) + 'px';
      ink = [1e9, 1e9, -1e9, -1e9];
      for (const l of p.lines) {
        const m = g.measureText(l.t);
        ink[0] = Math.min(ink[0], l.x - m.actualBoundingBoxLeft); ink[2] = Math.max(ink[2], l.x + m.actualBoundingBoxRight);
        ink[1] = Math.min(ink[1], l.y - m.actualBoundingBoxAscent); ink[3] = Math.max(ink[3], l.y + m.actualBoundingBoxDescent);
      }
      measured = true;
    }
    const c = p.it.cls === 'country' ? p.it.ref[1] : null, samples = [];
    if (c) for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) samples.push(ll(ink[0] + (ink[2] - ink[0]) * (i + 0.5) / NX, ink[1] + (ink[3] - ink[1]) * (j + 0.5) / NY));
    const size = p.size || (p.font ? parseFloat((p.font.match(/([0-9.]+)px/) || [0, 0])[1]) : null);
    out.push({ cls: p.it.cls, text: p.lines ? p.lines.map((l) => l.t).join(' ') : p.it.text, a3: c ? c.a3 : null, state: !!p.it.state, kind: p.kind || 'point', abbr: !!p.abbr,
      size, font: p.font || null, rect: [p.x0, p.y0, p.x1, p.y1].map((v) => +v.toFixed(2)), ink: ink.map((v) => +v.toFixed(2)), measured,
      leader: p.leader ? Array.from(p.leader, (v) => +v.toFixed(2)) : null, end: p.leader ? ll(p.leader[2], p.leader[3]) : null, samples,
      // a click on the name, and on the middle of its leader, must open this unit's card
      hit: L.hit((ink[0] + ink[2]) / 2, (ink[1] + ink[3]) / 2) === p.it && (!p.leader || L.hit((p.leader[0] + p.leader[2]) / 2, (p.leader[1] + p.leader[3]) / 2) === p.it) });
  }
  cam.beginFrame();
  const units = ATLAS.data.political.countries.map((c) => { const q = c.lp || [c.lon, c.lat], a = cam.project(q[0], q[1]);
    return { a3: c.a3, type: c.type, home: c.home !== false, continent: c.continent, seen: !!a && a[0] >= 0 && a[0] <= W && a[1] >= 0 && a[1] <= H }; });
  return { km: cam.kmPerPx(), w: W, h: H, labels: out, units };
}"""
PROJECT = """(pts) => { const c = ATLAS.cam; c.beginFrame(); return pts.map((p) => c.project(p[0], p[1])); }"""
MOVE = """([lon, lat, km]) => { const c = ATLAS.cam; if (km) { c.lookAt(lon, lat); c.setKmPerPx(km); } ATLAS.redraw(); ATLAS.step(2); return c.kmPerPx(); }"""

# Stability under small camera moves (not zero checks; reported). On the sheet a drag only translates the picture,
# so every state's name should keep its text and its place relative to the ground. Names within EDGE px of the
# window edge are left out: there a name may legitimately move to stay in view.
PANS = [(3, 0), (0, 3), (-7, 5), (11, -4), (-5, -9), (-2, 5)]          # px; they sum to zero
ZOOMS = 5                                                              # steps of 2% towards the ground
EDGE = 140
SNAP = """() => { const L = ATLAS.labels, o = {}; for (const p of L.placed) if (p.it.cls === 'country' && p.it.state) o[p.it.ref[1].a3] = [p.lines.map((l) => l.t).join(' '), p.kind, p.x0, p.y0, p.x1, p.y1]; return o; }"""
PAN = """([dx, dy]) => { ATLAS.cam.pan(dx, dy); ATLAS.redraw(); ATLAS.step(1); }"""
ZOOM = """(f) => { ATLAS.cam.zoom(f); ATLAS.redraw(); ATLAS.step(1); }"""

STATE_TYPES = ("Sovereign country", "Country", "Sovereignty", "Disputed")
is_state198 = lambda u: u["home"] and u["type"] in STATE_TYPES
is_state204 = lambda u: u["type"] in ("Sovereign country", "Country")


class Ground:
    """Natural Earth's country polygons, straight from the source file: who holds a point, and how far a point is from a unit."""

    def __init__(self, units):
        self.units = units           # {a3: [ (bbox, [ring arrays, exterior first]) ]}

    @classmethod
    def natural_earth(cls):
        fc = json.load(open(os.path.join(ROOT, "data", "ne", "ne_50m_admin_0_countries.geojson")))["features"]
        units = {}
        for f in fc:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            units[f["properties"]["ADM0_A3"]] = [cls._poly(p) for p in polys]
        return cls(units)

    @staticmethod
    def _poly(rings):
        rs = [np.asarray(r, dtype=np.float64)[:, :2] for r in rings]
        return (rs[0][:, 0].min(), rs[0][:, 1].min(), rs[0][:, 0].max(), rs[0][:, 1].max()), rs

    @staticmethod
    def _inside(rs, x, y):
        inside = False
        for r in rs:
            xi, yi = r[:, 0], r[:, 1]
            xj, yj = np.roll(xi, 1), np.roll(yi, 1)
            cut = (yi > y) != (yj > y)
            if cut.any():
                xc = (xj[cut] - xi[cut]) * (y - yi[cut]) / (yj[cut] - yi[cut]) + xi[cut]
                inside ^= bool(np.count_nonzero(x < xc) & 1)
        return inside

    def holds(self, a3, lon, lat):
        return any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and self._inside(rs, lon, lat) for b, rs in self.units.get(a3, ()))

    def owner(self, lon, lat):
        for a3, polys in self.units.items():
            for b, rs in polys:
                if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and self._inside(rs, lon, lat):
                    return a3
        return None

    def px_gap(self, a3, rect, near, project):
        """Distance on the screen, px, from a rectangle (x0, y0, x1, y1; a point if degenerate) to the unit's outline.
        near = (lon, lat) of the rectangle; project = the camera's own forward projection, [(lon, lat)] -> [(x, y) or None]."""
        best = math.inf
        x0, y0, x1, y1 = rect
        for b, rs in self.units.get(a3, ()):
            if b[1] > near[1] + 25 or b[3] < near[1] - 25 or min(abs((b[0] - near[0] + 540) % 360 - 180), abs((b[2] - near[0] + 540) % 360 - 180)) > 40 and not (b[0] <= near[0] <= b[2]):
                continue
            r = rs[0]
            pts = project(r.tolist())
            ok = np.array([q is not None for q in pts])
            xy = np.array([q if q is not None else (np.nan, np.nan) for q in pts], dtype=np.float64)
            px, py = xy[:, 0], xy[:, 1]
            qx, qy, okq = np.roll(px, 1), np.roll(py, 1), np.roll(ok, 1)
            d = np.hypot(np.maximum(np.maximum(x0 - px, 0), px - x1), np.maximum(np.maximum(y0 - py, 0), py - y1))
            if ok.any():
                best = min(best, float(np.nanmin(d)))
            # an edge can pass nearer than either of its ends
            close = ok & okq & (np.hypot(px - qx, py - qy) > 2) & (np.minimum(d, np.roll(d, 1)) < best + np.hypot(px - qx, py - qy))
            for ax, ay, bx, by in zip(px[close], py[close], qx[close], qy[close]):
                t = np.linspace(0, 1, int(min(400, math.hypot(bx - ax, by - ay) + 2)))
                sx, sy = ax + (bx - ax) * t, ay + (by - ay) * t
                best = min(best, float(np.hypot(np.maximum(np.maximum(x0 - sx, 0), sx - x1), np.maximum(np.maximum(y0 - sy, 0), sy - y1)).min()))
        return best

    def km_to(self, a3, lon, lat):
        """Distance from a point to the unit (0 inside it), km, in the local tangent plane."""
        if self.holds(a3, lon, lat):
            return 0.0
        best, c = math.inf, math.cos(math.radians(lat))
        for b, rs in self.units.get(a3, ()):
            if min(abs(lon - b[0]), abs(lon - b[2])) * c * 111.2 > best and not (b[0] <= lon <= b[2]):
                continue
            r = rs[0]
            px, py = (r[:, 0] - lon) * c * 111.195, (r[:, 1] - lat) * 111.195
            qx, qy = np.roll(px, 1), np.roll(py, 1)
            dx, dy = qx - px, qy - py
            t = np.clip(-(px * dx + py * dy) / np.maximum(dx * dx + dy * dy, 1e-12), 0, 1)
            best = min(best, float(np.sqrt(((px + t * dx) ** 2 + (py + t * dy) ** 2).min())))
        return best


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0.01 and min(a[3], b[3]) - max(a[1], b[1]) > 0.01


def _seg_rect(s, r):
    x0, y0, x1, y1 = r
    ax, ay, bx, by = s
    t0, t1, dx, dy = 0.0, 1.0, bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _seg_seg(a, b):
    d = (b[2] - b[0]) * (a[3] - a[1]) - (b[3] - b[1]) * (a[2] - a[0])
    if abs(d) < 1e-9:
        return False
    u = ((b[0] - a[0]) * (a[3] - a[1]) - (b[1] - a[1]) * (a[2] - a[0])) / d
    t = ((b[0] - a[0]) * (b[3] - b[1]) - (b[1] - a[1]) * (b[2] - b[0])) / d
    return 0 <= u <= 1 and 0 <= t <= 1


def check_overlaps(labels):
    """Pairs of names that collide: ink on ink, rectangle on rectangle, a leader through a name, a leader across a leader."""
    bad = []
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            if _overlap(a["ink"], b["ink"]):
                bad.append(("ink", a["text"], b["text"]))
            elif _overlap(a["rect"], b["rect"]):
                bad.append(("rect", a["text"], b["text"]))
            if a.get("leader") and b.get("leader") and _seg_seg(a["leader"], b["leader"]):
                bad.append(("leaders cross", a["text"], b["text"]))
        if a.get("leader"):
            for b in labels:
                if b is not a and _seg_rect(a["leader"], b["ink"]):
                    bad.append(("leader through name", a["text"], b["text"]))
    return bad


def check_type(labels):
    return [(l["text"], l["size"]) for l in labels if not l["size"] or l["size"] < MIN_PX - 1e-6]     # a name whose size cannot be read fails


def check_ink_in_rect(labels):
    """The layer's own rectangle must hold the ink it stands for, or its collision test protects nothing."""
    return [l["text"] for l in labels if l.get("measured") and (l["ink"][0] < l["rect"][0] - 1 or l["ink"][1] < l["rect"][1] - 1 or l["ink"][2] > l["rect"][2] + 1 or l["ink"][3] > l["rect"][3] + 1)]


def place_of(l, ground, project):
    """Why a country label is misplaced, or None. See the module docstring for the rule."""
    a3, S = l["a3"], l["samples"]
    if any(s is None for s in S):
        return "partly off the Earth"
    who = [ground.owner(s[0], s[1]) for s in S]
    others = sum(1 for w in who if w and w != a3) / len(who)
    centre = who[NX * (NY // 2) + NX // 2]
    if centre and centre != a3:
        return f"its centre is on {centre}"
    mid = S[NX * (NY // 2) + NX // 2]
    if l.get("leader"):
        if l["end"] is None:
            return "its leader ends off the Earth"
        ex, ey = l["leader"][2], l["leader"][3]
        d = 0.0 if ground.holds(a3, l["end"][0], l["end"][1]) else ground.px_gap(a3, (ex, ey, ex, ey), l["end"], project)
        if d > TOL_PX:
            return f"its leader ends {d:.1f} px outside it"
        if others > ON_OTHERS_BESIDE:
            return f"{others:.0%} of it is on other countries: {sorted({w for w in who if w and w != a3})}"
        return None
    if centre == a3:
        return None if others <= ON_OTHERS_INSIDE else f"{others:.0%} of it is on other countries: {sorted({w for w in who if w and w != a3})}"
    # beside its state without a leader: it must touch it, to the eye
    if not any(w == a3 for w in who):
        d = ground.px_gap(a3, l["ink"], mid, project)
        if d > TOUCH_PX:
            return f"it has no leader and is {d:.1f} px from its state"
    if others > ON_OTHERS_BESIDE:
        return f"{others:.0%} of it is on other countries: {sorted({w for w in who if w and w != a3})}"
    return None


def check_view(view, ground, project):
    """All the numbers for one framing. view: what JS returned; project: the camera's forward projection at that framing."""
    L, km, W, H = view["labels"], view["km"], view["w"], view["h"]
    whole = lambda l: l["ink"][0] >= 0 and l["ink"][1] >= 0 and l["ink"][2] <= W and l["ink"][3] <= H
    named = {l["a3"]: l for l in L if l["cls"] == "country" and whole(l)}
    res = {"km": round(km, 2), "labels": len(L)}
    for tag, pred in (("198", is_state198), ("204", is_state204)):
        seen = [u for u in view["units"] if pred(u) and u["seen"]]
        got = [named[u["a3"]] for u in seen if u["a3"] in named]
        res[f"in_view{tag}"] = len(seen)
        res[f"named{tag}"] = len(got)
        res[f"full{tag}"] = sum(1 for l in got if not l["abbr"])
        res[f"abbr{tag}"] = sum(1 for l in got if l["abbr"])
        res[f"unnamed{tag}"] = len(seen) - len(got)
        if tag == "198":
            res["leaders"] = sum(1 for l in got if l.get("leader"))
            res["unnamed_list"] = [u["a3"] for u in seen if u["a3"] not in named]
            res["by_continent"] = {c: [sum(1 for u in seen if u["continent"] == c and u["a3"] in named), sum(1 for u in seen if u["continent"] == c)]
                                   for c in sorted({u["continent"] for u in seen})}
            # the count the original audit made: any unit of the type whose label was placed, in the window or not
            res["placed204"] = len({l["a3"] for l in L if l["cls"] == "country"} & {u["a3"] for u in view["units"] if is_state204(u)})
    res["overlap_list"] = check_overlaps(L)
    res["under_list"] = check_type(L)
    res["ink_outside_rect"] = check_ink_in_rect(L)
    mis, other, states = [], [], {u["a3"] for u in view["units"] if is_state198(u)}
    for l in L:
        if l["cls"] != "country":
            continue
        why = place_of(l, ground, project)
        if why:
            (mis if l["a3"] in states else other).append((l["text"], l["a3"], l["kind"], why))
    res["misplaced_list"], res["misplaced_other_list"] = mis, other
    res["hit_wrong"] = [l["text"] for l in L if l.get("hit") is False]
    res["overlaps"], res["under_9px"], res["misplaced"] = len(res["overlap_list"]) + len(res["ink_outside_rect"]), len(res["under_list"]), len(mis)
    return res


def stability(page, w=1440, h=900):
    """Drag the map by a few pixels six times, then zoom in by 2% five times. Returns (flips, zoom losses, names compared):
    flips = a state's name that changed text, appeared, vanished or moved against the ground during a drag;
    zoom losses = a state named at one step and not at the next one closer in."""
    inner = lambda r: r[2] > EDGE and r[4] < w - EDGE and r[3] > EDGE and r[5] < h - EDGE
    a = page.evaluate(SNAP)
    flips, seen = set(), set()
    for dx, dy in PANS:
        page.evaluate(PAN, [dx, dy])
        b = page.evaluate(SNAP)
        for k in set(a) | set(b):
            ra, rb = a.get(k), b.get(k)
            if not any(r and inner(r) for r in (ra, rb)):
                continue
            seen.add(k)
            # cam.pan(dx, dy) moves the ground by (dx, dy) on the sheet
            if ra is None or rb is None or ra[0] != rb[0] or abs(rb[2] - ra[2] - dx) > 0.6 or abs(rb[3] - ra[3] - dy) > 0.6:
                flips.add(k)
        a = b
    lost = set()
    for _ in range(ZOOMS):
        page.evaluate(ZOOM, 1 / 1.02)
        b = page.evaluate(SNAP)
        lost |= {k for k, r in a.items() if inner(r) and k not in b}
        a = b
    return sorted(flips), sorted(lost), len(seen)


def selftest():
    """Planted faults in a synthetic world: each check must catch its own and pass the clean case."""
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]
    ground = Ground({"AAA": [Ground._poly(sq(0, 0, 10, 10))], "BBB": [Ground._poly(sq(10, 0, 20, 10))], "ISL": [Ground._poly(sq(30, 4.9, 30.2, 5.1))]})
    km = 11.12                                    # a pixel is 0.1 degree: x = lon * 10, y = (10 - lat) * 10
    geo = lambda x, y: [x / 10, 10 - y / 10]

    def lab(text, a3, ink, size=10, leader=None, state=True, cls="country"):
        S = [geo(ink[0] + (ink[2] - ink[0]) * (i + 0.5) / NX, ink[1] + (ink[3] - ink[1]) * (j + 0.5) / NY) for j in range(NY) for i in range(NX)]
        return {"cls": cls, "text": text, "a3": a3, "state": state, "kind": "lead" if leader else "in", "abbr": False, "size": size, "font": f"600 {size}px x",
                "rect": [ink[0] - 2, ink[1] - 2, ink[2] + 2, ink[3] + 2], "ink": list(ink), "measured": True, "leader": leader, "end": geo(*leader[2:]) if leader else None, "samples": S, "hit": True}
    project = lambda pts: [(q[0] * 10, (10 - q[1]) * 10) for q in pts]
    units = [{"a3": a, "type": "Sovereign country", "home": True, "continent": "Test", "seen": True} for a in ("AAA", "BBB", "ISL")]
    view = lambda labels: {"km": km, "w": 400, "h": 100, "labels": labels, "units": units}
    clean = [lab("AAA", "AAA", (30, 40, 70, 48)), lab("BBB", "BBB", (130, 40, 170, 48)),
             lab("ISL", "ISL", (240, 60, 270, 68), leader=[270, 60, 301, 50])]         # in the sea, its leader ending on the island
    r = check_view(view(clean), ground, project)
    ok = [("the clean case passes", r["overlaps"] == 0 and r["under_9px"] == 0 and r["misplaced"] == 0 and r["named198"] == 3 and r["leaders"] == 1)]
    # 1. a known overlap: BBB's name moved onto AAA's by 6 px of ink
    r = check_view(view([clean[0], lab("BBB", "BBB", (64, 44, 104, 52)), clean[2]]), ground, project)
    ok.append(("a planted overlap is caught", r["overlaps"] == 1 and r["overlap_list"][0][0] == "ink"))
    # 2. a known misplaced name: AAA's name set wholly on BBB
    r = check_view(view([lab("AAA", "AAA", (130, 20, 170, 28)), clean[1], clean[2]]), ground, project)
    ok.append(("a name on the wrong country is caught", r["misplaced"] == 1 and "centre is on BBB" in r["misplaced_list"][0][3]))
    # 3. a leader that ends in the sea 8 px from its island, and one that ends on another country
    r = check_view(view([clean[0], clean[1], lab("ISL", "ISL", (240, 60, 270, 68), leader=[270, 60, 290, 50])]), ground, project)
    ok.append(("a leader that misses its state is caught", r["misplaced"] == 1 and "leader ends" in r["misplaced_list"][0][3]))
    r = check_view(view([clean[0], clean[1], lab("ISL", "ISL", (240, 60, 270, 68), leader=[240, 60, 150, 50])]), ground, project)
    ok.append(("a leader that ends on another country is caught", r["misplaced"] == 1))
    # 4. a name beside its state with no leader that does not touch it; and one that straddles the border too far
    r = check_view(view([lab("AAA", "AAA", (240, 20, 280, 28)), clean[1], clean[2]]), ground, project)
    ok.append(("a floating name with no leader is caught", r["misplaced"] == 1 and "px from its state" in r["misplaced_list"][0][3]))
    r = check_view(view([lab("AAA", "AAA", (50, 103, 90, 111)), clean[1], clean[2]]), ground, project)       # 3 px off its coast, on nothing else: touching
    r2 = check_view(view([lab("AAA", "AAA", (50, 106, 90, 114)), clean[1], clean[2]]), ground, project)      # 6 px off: not
    ok.append(("touching is 4 px, measured on the screen", r["misplaced"] == 0 and r2["misplaced"] == 1))
    r = check_view(view([lab("AAA", "AAA", (45, 40, 125, 48)), clean[2]]), ground, project)
    ok.append(("a name spilling over the border is caught", r["misplaced"] == 1 and "on other countries" in r["misplaced_list"][0][3]))
    # 5. type under the floor; a leader drawn through another name; ink outside the layer's own rectangle
    r = check_view(view([clean[0], lab("BBB", "BBB", (130, 40, 170, 48), size=8.5), clean[2]]), ground, project)
    ok.append(("type under 9 px is caught", r["under_9px"] == 1))
    r = check_view(view([clean[0], clean[1], lab("ISL", "ISL", (80, 40, 110, 48), leader=[110, 44, 301, 50])]), ground, project)   # the line runs through BBB's name
    ok.append(("a leader through another name is caught", any(o[0] == "leader through name" for o in r["overlap_list"])))
    bad = lab("AAA", "AAA", (30, 40, 70, 48)); bad["rect"] = [34, 40, 66, 48]
    r = check_view(view([bad, clean[1], clean[2]]), ground, project)
    ok.append(("ink outside the layer's rectangle is caught", r["overlaps"] == 1 and r["ink_outside_rect"] == ["AAA"]))
    # 6. the instrument itself: the polygon test and the distance on a known shape
    ok.append(("the ground test knows a square", ground.owner(5, 5) == "AAA" and ground.owner(15, 5) == "BBB" and ground.owner(25, 5) is None
               and abs(ground.px_gap("AAA", (50, -20, 60, -10), (5.5, 11.5), project) - 10) < 0.6))
    for name, good in ok:
        print(f"  {'ok  ' if good else 'FAIL'} {name}")
    return 0 if all(g for _, g in ok) else 1


def run(port, ground):
    """Every framing, checked while the page is still at it (the px distances need its camera)."""
    from playwright.sync_api import sync_playwright
    views = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        for name, path in PAGES.items():
            page = ctx.new_page()
            page.goto(f"http://localhost:{port}" + path, wait_until="load", timeout=120000)
            page.wait_for_function("window.__FRAME_READY === true", timeout=240000)
            project = lambda pts: page.evaluate(PROJECT, pts)
            views[name] = check_view(page.evaluate(JS, [NX, NY]), ground, project)
            if name == "sheet":
                views["_stability"] = stability(page)
                page.evaluate("() => { ATLAS.cam.home(); ATLAS.redraw(); ATLAS.step(1); }")
            for reg, (lon, lat) in REGIONS.items():
                for km in SCALES:
                    page.evaluate(MOVE, [lon, lat, km])
                    views[f"{name}_{reg}{km}"] = check_view(page.evaluate(JS, [NX, NY]), ground, project)
            if name == "sheet":
                for reg, km in CARRIED:
                    page.evaluate(MOVE, [*REGIONS[reg], km])
                    views[f"{name}_{reg}{km}_carried"] = check_view(page.evaluate(JS, [NX, NY]), ground, project)
            page.close()
        b.close()
    return views


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8150"
    ground = Ground.natural_earth()
    views = run(port, ground)
    flips, lost, compared = views.pop("_stability")
    s, g = views["sheet"], views["globe"]
    regional = [v for k, v in views.items() if k.endswith(("12", "6"))]
    # on the globe only about half the states face the camera, so only the sheet is held to "all of them"
    res = {"sheet_states_unnamed": 204 - s["placed204"], "sheet_states_named": s["placed204"], "globe_states_named": g["placed204"],
           "sheet_states198_unnamed": s["unnamed198"], "sheet_states198_named": s["named198"], "sheet_states198_full": s["full198"], "sheet_states198_abbr": s["abbr198"],
           "sheet_leaders": s["leaders"],
           "globe_states198_in_view": g["in_view198"], "globe_states198_unnamed": g["unnamed198"], "globe_states198_named": g["named198"], "globe_states198_full": g["full198"], "globe_states198_abbr": g["abbr198"],
           "regional_states198_in_view": sum(v["in_view198"] for v in regional), "regional_states198_unnamed": sum(v["unnamed198"] for v in regional),
           "regional12_states198_unnamed": sum(v["unnamed198"] for k, v in views.items() if k.endswith("12")), "regional6_states198_unnamed": sum(v["unnamed198"] for k, v in views.items() if k.endswith("6")),
           "overlaps": sum(v["overlaps"] for v in views.values()), "under_9px": sum(v["under_9px"] for v in views.values()),
           "misplaced": sum(v["misplaced"] for v in views.values()), "misplaced_other_units": sum(len(v["misplaced_other_list"]) for v in views.values()),
           "hit_wrong": sum(len(v["hit_wrong"]) for v in views.values()),
           "sheet_drag_flips": len(flips), "sheet_zoom_in_losses": len(lost),
           "views": {k: {q: v[q] for q in ("km", "in_view198", "named198", "full198", "abbr198", "leaders", "overlaps", "under_9px", "misplaced")} for k, v in views.items()}}
    if "--json" not in sys.argv:
        print(f"{'view':22} {'km/px':>6} {'named':>9} {'full':>5} {'abbr':>5} {'leader':>6} {'labels':>6}  overlaps under9 misplaced  (other units misplaced)")
        for k, v in views.items():
            print(f"{k:22} {v['km']:6.2f} {v['named198']:4d}/{v['in_view198']:<4d} {v['full198']:5d} {v['abbr198']:5d} {v['leaders']:6d} {v['labels']:6d}  {v['overlaps']:8d} {v['under_9px']:6d} {v['misplaced']:9d}  ({len(v['misplaced_other_list'])})")
        for k in ("sheet", "globe"):
            print(f"\n{k}: states named per continent: " + ", ".join(f"{c} {a}/{n}" for c, (a, n) in views[k]["by_continent"].items()))
            print(f"{k}: by the original count, {views[k]['placed204']} of 204 units of TYPE Sovereign country or Country are named")
        print(f"\nsheet, {len(PANS)} drags of a few px: {len(flips)} of {compared} state names changed text or moved against the ground {flips or ''}")
        print(f"sheet, {ZOOMS} steps of 2% closer: {len(lost)} state names lost on the way in {lost or ''}")
        if "--list" in sys.argv:
            for k, v in views.items():
                print(f"\n{k}: unnamed: {' '.join(v['unnamed_list'])}")
        for k, v in views.items():
            for kind in ("overlap_list", "under_list", "ink_outside_rect", "misplaced_list", "hit_wrong"):
                for row in v[kind]:
                    print(f"  FAULT {k} {kind}: {row}")
            if "--list" in sys.argv:
                for row in v["misplaced_other_list"]:
                    print(f"  note  {k} other unit: {row}")
    print(json.dumps(res))


if __name__ == "__main__":
    main()
