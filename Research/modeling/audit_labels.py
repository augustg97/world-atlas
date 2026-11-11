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

INSETS. On the whole-Earth sheet the app draws insets (web/js/insets.js): second views of the same sheet,
magnified, each with its own camera and its own label layer. Their names are counted and held to the SAME
checks: a state named in an inset is named; the ground under an inset's name is found through the INSET'S OWN
camera inverse and tested against the same Natural Earth polygons; its ink is re-measured the same way; a click
on it (sent through the app's own pick, at the window point) must open that unit's card, and a click on the
inset's ground must open the card of the ground the inset's inverse says is there. An inset name whose ink
leaves its frame counts as an overlap. Reported apart: how much of each frame lies over land on the main map.

PANELS. A fifth check that must be ZERO: under_panel - a name whose ink lies under one of the interface's
panels (their rectangles are read from the page here, not from the label layer) or under an inset's frame, or
an inset that touches a panel, another inset or the window's edge. A state whose label point is under a panel
and that has no name is not in view and is not counted as unnamed (key hidden198); the count the old audit
made, which took a name under a panel for a name, is kept as named_raw198.

A continent's name is set one letter at a time (overlays.js, _spread): each letter is a label here, with its
own ink, held to the same overlap, size, panel and click checks.

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
BORDER_KM = 6.0              # a click on an inset's ground may open the neighbour this close to a border (the shipped outlines are generalised)

# Runs in the page. Everything geometric is taken from the camera (cam.unproject is the exact inverse; the label
# layer uses its own table) and from a fresh canvas (ink boxes), so the layer's rectangles are checked, not trusted.
PANELS = ["top", "left", "left-open", "card", "dash", "legend", "hud", "time"]
JS = """([NX, NY, PANELS]) => {
  const cam = ATLAS.cam, W = cam.w, H = cam.h;
  const g = document.createElement('canvas').getContext('2d');
  // every name of one label layer, as drawn: L its layer, vcam the camera it was set through, (ox, oy) where that
  // view's own origin is in the window. Rectangles and ink come back in WINDOW px; the ground under them through vcam.
  const grab = (L, vcam, ox, oy) => {
    const ll = (x, y) => { const p = vcam.unproject(x, y); return p ? [+p[0].toFixed(4), +p[1].toFixed(4)] : null; };
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
      const cx = (ink[0] + ink[2]) / 2, cy = (ink[1] + ink[3]) / 2, sh = (r) => [r[0] + ox, r[1] + oy, r[2] + ox, r[3] + oy].map((v) => +v.toFixed(2));
      out.push({ cls: p.it.cls, text: p.lines ? p.lines.map((l) => l.t).join(' ') : p.it.text, a3: c ? c.a3 : null, state: !!p.it.state, kind: p.kind || 'point', abbr: !!p.abbr,
        size, font: p.font || null, rect: sh([p.x0, p.y0, p.x1, p.y1]), ink: sh(ink), measured,
        leader: p.leader ? sh(Array.from(p.leader)) : null, end: p.leader ? ll(p.leader[2], p.leader[3]) : null, samples,
        // a click on the name, and on the middle of its leader, must open this unit's card: asked of the layer, and of
        // the app's own pick at the window point (which has to find the right view first)
        hit: L.hit(cx, cy) === p.it && (!ATLAS.pickAt || ATLAS.pickAt(cx + ox, cy + oy) === p.it.ref)
          && (!p.leader || L.hit((p.leader[0] + p.leader[2]) / 2, (p.leader[1] + p.leader[3]) / 2) === p.it) });
    }
    return out;
  };
  const main = (x, y) => { const p = cam.unproject(x, y); return p ? [+p[0].toFixed(3), +p[1].toFixed(3)] : null; };
  const insets = (ATLAS.insets || []).filter((I) => I.rect).map((I) => {
    const r = I.rect, under = [], ground = [];
    // what the frame covers on the main map, every 4 px, through the MAIN camera
    for (let y = r.y + 2; y < r.y + r.h; y += 4) for (let x = r.x + 2; x < r.x + r.w; x += 4) under.push(main(x, y));
    // clicks on its ground, on a 7 x 7 grid: what the app would open, and where the inset's own inverse puts the point
    for (let j = 0; j < 7; j++) for (let i = 0; i < 7; i++) {
      const x = r.x + r.w * (i + 0.5) / 7, y = r.y + r.h * (j + 0.5) / 7, ref = ATLAS.pickAt(x, y), q = I.cam.unproject(x - r.x, y - r.y);
      ground.push({ ll: q, name: !!I.labels.hit(x - r.x, y - r.y), kind: ref ? ref[0] : null, a3: ref && ref[0] === 'country' ? ref[1].a3 : null, at: ref && ref[0] === 'probe' ? ref[1] : null });
    }
    return { id: I.id, rect: [r.x, r.y, r.x + r.w, r.y + r.h], km: I.k, alpha: I.alpha, labels: grab(I.labels, I.cam, r.x, r.y), under, ground };
  });
  const panels = [];
  for (const id of PANELS) { const e = document.getElementById(id), r = e && e.getBoundingClientRect(); if (r && r.width >= 2 && r.height >= 2) panels.push([r.left, r.top, r.right, r.bottom]); }
  cam.beginFrame();
  const units = ATLAS.data.political.countries.map((c) => { const q = c.lp || [c.lon, c.lat], a = cam.project(q[0], q[1]);
    return { a3: c.a3, type: c.type, home: c.home !== false, continent: c.continent, seen: !!a && a[0] >= 0 && a[0] <= W && a[1] >= 0 && a[1] <= H, at: a ? [+a[0].toFixed(1), +a[1].toFixed(1)] : null }; });
  return { km: cam.kmPerPx(), w: W, h: H, labels: grab(ATLAS.labels, cam, 0, 0), units, insets, panels };
}"""
PROJECT = """(pts) => { const c = ATLAS.cam; c.beginFrame(); return pts.map((p) => c.project(p[0], p[1])); }"""
# the same through an inset's own camera, in window px
PROJECT_INSET = """([id, pts]) => { const I = ATLAS.insets.find((i) => i.id === id), c = I.cam; c.beginFrame(); return pts.map((p) => { const q = c.project(p[0], p[1]); return q ? [q[0] + I.rect.x, q[1] + I.rect.y] : null; }); }"""
MOVE = """([lon, lat, km]) => { const c = ATLAS.cam; if (km) { c.lookAt(lon, lat); c.setKmPerPx(km); } ATLAS.redraw(); ATLAS.step(2); return c.kmPerPx(); }"""

# Stability under small camera moves (not zero checks; reported). On the sheet a drag only translates the picture,
# so every state's name should keep its text and its place relative to the ground. Names within EDGE px of the
# window edge are left out: there a name may legitimately move to stay in view.
PANS = [(3, 0), (0, 3), (-7, 5), (11, -4), (-5, -9), (-2, 5)]          # px; they sum to zero
ZOOMS = 5                                                              # steps of 2% towards the ground
EDGE = 140
SNAP = """() => { const L = ATLAS.labels, o = {}; for (const p of L.placed) if (p.it.cls === 'country' && p.it.state) o[p.it.ref[1].a3] = [p.lines.map((l) => l.t).join(' '), p.kind, p.x0, p.y0, p.x1, p.y1]; return o; }"""
# what is not map: the panels (read from the page) and the insets' frames. A name may legitimately move to keep clear of them.
TAKEN = """(PANELS) => { const out = []; for (const id of PANELS) { const e = document.getElementById(id), r = e && e.getBoundingClientRect(); if (r && r.width >= 2 && r.height >= 2) out.push([r.left, r.top, r.right, r.bottom]); }
  for (const I of (ATLAS.insets || [])) if (I.rect) out.push([I.rect.x, I.rect.y, I.rect.x + I.rect.w, I.rect.y + I.rect.h]); return out; }"""
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
        sys.path.insert(0, os.path.join(ROOT, "build"))
        from units import admin_units                 # what the app reads: French Guiana and its like are their own units
        fc = admin_units(os.path.join(ROOT, "data"))
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


def _inside(a, b, tol=0.5):
    return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol


def check_taken(labels, insets, panels, W, H):
    """Names under what is not map: a main-map name whose ink lies under a panel or under an inset's frame; an inset
    that touches a panel, another inset or the window's edge."""
    bad = []
    for l in labels:
        for r in panels:
            if _overlap(l["ink"], r):
                bad.append(("name under a panel", l["text"], [round(v) for v in r]))
        for i in insets:
            if _overlap(l["ink"], i["rect"]):
                bad.append(("name under an inset", l["text"], i["id"]))
    for n, i in enumerate(insets):
        r = i["rect"]
        if r[0] < 0 or r[1] < 0 or r[2] > W or r[3] > H:
            bad.append(("inset off the window", i["id"], r))
        for q in panels:
            if _overlap(r, q):
                bad.append(("inset under a panel", i["id"], [round(v) for v in q]))
        for j in insets[n + 1:]:
            if _overlap(r, j["rect"]):
                bad.append(("insets overlap", i["id"], j["id"]))
    return bad


def check_inset_ground(inset, ground):
    """Clicks on an inset's ground: the card that opens must be the card of the ground the inset's own inverse puts there."""
    bad = []
    for g in inset["ground"]:
        if g["name"]:
            continue                                  # a name is there: tested with the names
        if g["ll"] is None or g["kind"] is None:
            bad.append((inset["id"], "a click in the frame found no ground", g["ll"]))
        elif g["kind"] == "country":
            lon, lat = g["ll"]
            if not (ground.holds(g["a3"], lon, lat) or ground.km_to(g["a3"], lon, lat) < BORDER_KM):
                bad.append((inset["id"], f"ground at {lon:.2f}, {lat:.2f} opened {g['a3']}", ground.owner(lon, lat)))
        elif g["kind"] == "probe":
            if abs(g["at"][0] - g["ll"][0]) > 1e-6 or abs(g["at"][1] - g["ll"][1]) > 1e-6:
                bad.append((inset["id"], f"probe opened at {g['at']}", g["ll"]))
    return bad


def frame_land(inset, ground, project):
    """What an inset's frame covers on the main map. Two measures: the share of points under it (every 4 px, through the
    main camera) that are land; and, because an island can pass between points, every unit with an outline vertex inside
    the frame (project = the MAIN camera's forward projection)."""
    pts = [q for q in inset["under"] if q]
    r = inset["rect"]
    if not pts:
        return {"points": len(inset["under"]), "off_earth": len(inset["under"]), "on_land": 0, "units": {}}
    lo0, lo1 = min(q[0] for q in pts) - 1, max(q[0] for q in pts) + 1
    la0, la1 = min(q[1] for q in pts) - 1, max(q[1] for q in pts) + 1
    units, on = {}, 0
    cand = [(a3, b, rs) for a3, polys in ground.units.items() for b, rs in polys if b[0] <= lo1 and b[2] >= lo0 and b[1] <= la1 and b[3] >= la0]
    for a3, b, rs in cand:
        for xy in project(rs[0].tolist()):
            if xy is not None and r[0] <= xy[0] <= r[2] and r[1] <= xy[1] <= r[3]:
                units[a3] = units.get(a3, 0) + 1
                break
    for q in pts:
        if any(b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3] and ground._inside(rs, q[0], q[1]) for _, b, rs in cand):
            on += 1
    return {"points": len(inset["under"]), "off_earth": len(inset["under"]) - len(pts), "on_land": on, "units": units}


def check_view(view, ground, project, inset_project=None):
    """All the numbers for one framing. view: what JS returned; project: the main camera's forward projection at that
    framing; inset_project(id): the same through that inset's camera (window px)."""
    L, km, W, H = view["labels"], view["km"], view["w"], view["h"]
    insets, panels = view.get("insets") or [], view.get("panels") or []
    taken = panels + [i["rect"] for i in insets]
    IL = [(i, l) for i in insets for l in i["labels"]]
    ALL = L + [l for _, l in IL]
    whole = lambda l: l["ink"][0] >= 0 and l["ink"][1] >= 0 and l["ink"][2] <= W and l["ink"][3] <= H
    clear = lambda l: not any(_overlap(l["ink"], r) for r in taken)
    under = lambda u: u.get("at") is not None and any(r[0] <= u["at"][0] <= r[2] and r[1] <= u["at"][1] <= r[3] for r in taken)
    named_raw = {l["a3"]: l for l in L if l["cls"] == "country" and whole(l)}          # the old count: a name under a panel is a name
    named_main = {a: l for a, l in named_raw.items() if clear(l)}
    named_inset = {}
    for i, l in IL:
        if l["cls"] == "country" and _inside(l["ink"], i["rect"]):
            named_inset.setdefault(l["a3"], l)
    named = {**named_inset, **named_main}
    res = {"km": round(km, 2), "labels": len(ALL), "insets": {i["id"]: {"rect": i["rect"], "km": round(i["km"], 2), "alpha": i["alpha"], "labels": len(i["labels"])} for i in insets}}
    for tag, pred in (("198", is_state198), ("204", is_state204)):
        window = [u for u in view["units"] if pred(u) and u["seen"]]
        hidden = [u for u in window if under(u) and u["a3"] not in named]        # under a panel and unnamed: not in view
        seen = [u for u in window if not (under(u) and u["a3"] not in named)]
        got = [named[u["a3"]] for u in seen if u["a3"] in named]
        res[f"in_view{tag}"] = len(seen)
        res[f"named{tag}"] = len(got)
        res[f"full{tag}"] = sum(1 for l in got if not l["abbr"])
        res[f"abbr{tag}"] = sum(1 for l in got if l["abbr"])
        res[f"unnamed{tag}"] = len(seen) - len(got)
        if tag == "198":
            res["in_window198"], res["hidden198"], res["hidden_list"] = len(window), len(hidden), [u["a3"] for u in hidden]
            res["named_raw198"] = sum(1 for u in window if u["a3"] in named_raw)
            res["named_main198"] = sum(1 for u in seen if u["a3"] in named_main)
            res["inset_only198"] = sum(1 for u in seen if u["a3"] in named_inset and u["a3"] not in named_main)
            res["inset_names198"] = sum(1 for _, l in IL if l["cls"] == "country" and l["a3"] in {u["a3"] for u in view["units"] if is_state198(u)})
            res["leaders"] = sum(1 for l in got if l.get("leader"))
            res["named_list"] = sorted(u["a3"] for u in seen if u["a3"] in named)
            res["inset_only_list"] = sorted(u["a3"] for u in seen if u["a3"] in named_inset and u["a3"] not in named_main)
            res["unnamed_list"] = [u["a3"] for u in seen if u["a3"] not in named]
            res["by_continent"] = {c: [sum(1 for u in seen if u["continent"] == c and u["a3"] in named), sum(1 for u in seen if u["continent"] == c)]
                                   for c in sorted({u["continent"] for u in seen})}
            # the count the original audit made: any unit of the type whose label was placed, in the window or not
            res["placed204"] = len({l["a3"] for l in ALL if l["cls"] == "country"} & {u["a3"] for u in view["units"] if is_state204(u)})
    res["overlap_list"] = check_overlaps(ALL) + [("outside its frame", l["text"], i["id"]) for i, l in IL if not _inside(l["ink"], i["rect"])]
    res["under_list"] = check_type(ALL)
    res["ink_outside_rect"] = check_ink_in_rect(ALL)
    res["taken_list"] = check_taken(L, insets, panels, W, H)
    mis, other, states = [], [], {u["a3"] for u in view["units"] if is_state198(u)}
    for i, l in [(None, l) for l in L] + IL:
        if l["cls"] != "country":
            continue
        why = place_of(l, ground, project if i is None else (lambda pts, _id=i["id"]: inset_project(_id, pts)))
        if why:
            (mis if l["a3"] in states else other).append((l["text"] if i is None else f"{l['text']} [{i['id']} inset]", l["a3"], l["kind"], why))
    res["misplaced_list"], res["misplaced_other_list"] = mis, other
    res["hit_wrong"] = [l["text"] for l in ALL if l.get("hit") is False] + [g for i in insets for g in check_inset_ground(i, ground)]
    res["inset_land"] = {i["id"]: frame_land(i, ground, project) for i in insets}
    res["overlaps"], res["under_9px"], res["misplaced"] = len(res["overlap_list"]) + len(res["ink_outside_rect"]), len(res["under_list"]), len(mis)
    res["under_panel"] = len(res["taken_list"])
    return res


def stability(page, w=1440, h=900):
    """Drag the map by a few pixels six times, then zoom in by 2% five times. Returns (flips, zoom losses, names compared):
    flips = a state's name that changed text, appeared, vanished or moved against the ground during a drag;
    zoom losses = a state named at one step and not at the next one closer in.
    Names within EDGE px of the window's edge, of a panel or of an inset's frame are left out: there a name may
    legitimately move to stay in view (an inset keeps its size on the screen, so the map moves against it in a zoom)."""
    taken = page.evaluate(TAKEN, PANELS)
    gap = lambda r, q: max(q[0] - r[4], r[2] - q[2], q[1] - r[5], r[3] - q[3])       # px between a name (SNAP row) and a rectangle; negative inside
    inner = lambda r: r[2] > EDGE and r[4] < w - EDGE and r[3] > EDGE and r[5] < h - EDGE and all(gap(r, q) > EDGE for q in taken)
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
        a, taken = b, page.evaluate(TAKEN, PANELS)
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
    units = [{"a3": a, "type": "Sovereign country", "home": True, "continent": "Test", "seen": True, "at": at} for a, at in (("AAA", (50, 50)), ("BBB", (150, 50)), ("ISL", (301, 50)))]
    view = lambda labels, **more: {"km": km, "w": 400, "h": 100, "labels": labels, "units": units, **more}
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
    # 7. panels: a name under one is a fault and names nothing; a state wholly under one, unnamed, is not in view
    r = check_view(view([lab("AAA", "AAA", (10, 40, 50, 48)), clean[1], clean[2]], panels=[[0, 0, 25, 100]]), ground, project)
    ok.append(("a name under a panel is caught, and is not counted as a name", r["under_panel"] == 1 and r["named198"] == 2 and r["named_raw198"] == 3 and r["unnamed198"] == 1))
    r = check_view(view([clean[1], clean[2]], panels=[[0, 0, 100, 100]]), ground, project)
    ok.append(("a state under a panel with no name is hidden, not unnamed", r["hidden198"] == 1 and r["in_view198"] == 2 and r["unnamed198"] == 0 and r["under_panel"] == 0))
    r = check_view(view(clean, panels=[[0, 0, 25, 100]]), ground, project)
    ok.append(("names clear of the panels pass", r["under_panel"] == 0 and r["named198"] == 3))
    # 8. an inset: a state too small to name on the main map (6 px), shown 8 times larger in a frame over the sea.
    #    Window px in the frame -> ground through the INSET'S inverse: lon = (223 + (x - 353) / 8) / 10, lat = 10 - (57 + (y - 50) / 8) / 10
    g2 = Ground({**ground.units, "TNY": [Ground._poly(sq(22, 4, 22.6, 4.6))]})
    units.append({"a3": "TNY", "type": "Sovereign country", "home": True, "continent": "Test", "seen": True, "at": (223, 57)})
    FR = [310, 10, 396, 90]
    igeo = lambda x, y: [(223 + (x - 353) / 8) / 10, 10 - (57 + (y - 50) / 8) / 10]
    iproj = lambda _id, pts: [(353 + (q[0] * 10 - 223) * 8, 50 + ((10 - q[1]) * 10 - 57) * 8) for q in pts]

    def ilab(text, a3, ink):
        l = lab(text, a3, ink)
        l["samples"] = [igeo(ink[0] + (ink[2] - ink[0]) * (i + 0.5) / NX, ink[1] + (ink[3] - ink[1]) * (j + 0.5) / NY) for j in range(NY) for i in range(NX)]
        return l

    def inset(labels, rect=FR, opened="TNY"):
        under = [geo(x, y) for y in range(rect[1] + 2, rect[3], 4) for x in range(rect[0] + 2, rect[2], 4)]            # through the MAIN camera
        grid = [{"ll": igeo(353, 50), "name": False, "kind": "country", "a3": opened, "at": None}, {"ll": igeo(320, 80), "name": False, "kind": "probe", "a3": None, "at": igeo(320, 80)}]
        return {"id": "tiny", "rect": rect, "km": km / 8, "alpha": 1, "labels": labels, "under": under, "ground": grid}
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52))])]), g2, project, iproj)
    ok.append(("a clean inset passes, and its name names the state", r["overlaps"] == 0 and r["misplaced"] == 0 and r["under_panel"] == 0 and not r["hit_wrong"]
               and r["named198"] == 4 and r["inset_only198"] == 1 and r["unnamed198"] == 0 and r["inset_land"]["tiny"]["units"] == {}))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52))])]), g2, project, lambda _id, pts: project(pts))
    r0 = check_view(view(clean, insets=[inset([lab("TNY", "TNY", (340, 44, 366, 52))])]), g2, project, iproj)       # samples taken through the main camera
    ok.append(("an inset's names are tested through the inset's own camera", r["misplaced"] == 0 and r0["misplaced"] == 1))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (312, 12, 336, 18))])]), g2, project, iproj)       # 8 px clear of the state, no leader
    ok.append(("an inset name off its state is caught", r["misplaced"] == 1 and "inset" in r["misplaced_list"][0][0]))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (380, 44, 404, 52))])]), g2, project, iproj)
    ok.append(("an inset name that leaves its frame is caught, and names nothing", any(o[0] == "outside its frame" for o in r["overlap_list"]) and r["named198"] == 3))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52)), ilab("AAA", "AAA", (350, 48, 380, 56))])]), g2, project, iproj)
    ok.append(("two inset names that collide are caught", any(o[0] == "ink" for o in r["overlap_list"])))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52))], opened="BBB")]), g2, project, iproj)
    ok.append(("a click on an inset's ground that opens the wrong card is caught", len(r["hit_wrong"]) == 1))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52))], rect=[230, 10, 316, 90])]), g2, project, iproj)   # over ISL's name and the island
    ok.append(("an inset set over a name, and over land, is caught", r["under_panel"] >= 1 and "ISL" in r["inset_land"]["tiny"]["units"]))
    r = check_view(view(clean, insets=[inset([ilab("TNY", "TNY", (340, 44, 366, 52))])], panels=[[390, 0, 400, 100]]), g2, project, iproj)
    ok.append(("an inset under a panel is caught", r["under_panel"] == 1))
    units.pop()
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
            iproject = lambda _id, pts: page.evaluate(PROJECT_INSET, [_id, pts])
            look = lambda: check_view(page.evaluate(JS, [NX, NY, PANELS]), ground, project, iproject)
            views[name] = look()
            if name == "sheet":
                views["_stability"] = stability(page)
                page.evaluate("() => { ATLAS.cam.home(); ATLAS.redraw(); ATLAS.step(1); }")
            for reg, (lon, lat) in REGIONS.items():
                for km in SCALES:
                    page.evaluate(MOVE, [lon, lat, km])
                    views[f"{name}_{reg}{km}"] = look()
            if name == "sheet":
                for reg, km in CARRIED:
                    page.evaluate(MOVE, [*REGIONS[reg], km])
                    views[f"{name}_{reg}{km}_carried"] = look()
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
    if "--dump" in sys.argv:                     # every view in full, for a before/after comparison state by state
        json.dump({"views": views, "flips": flips, "lost": lost}, open(sys.argv[sys.argv.index("--dump") + 1], "w"))
    s, g = views["sheet"], views["globe"]
    regional = [v for k, v in views.items() if k.endswith(("12", "6"))]
    # on the globe only about half the states face the camera, so only the sheet is held to "all of them"
    res = {"sheet_states_unnamed": 204 - s["placed204"], "sheet_states_named": s["placed204"], "globe_states_named": g["placed204"],
           "sheet_states198_unnamed": s["unnamed198"], "sheet_states198_named": s["named198"], "sheet_states198_full": s["full198"], "sheet_states198_abbr": s["abbr198"],
           "sheet_states198_named_main": s["named_main198"], "sheet_states198_inset_only": s["inset_only198"], "sheet_states198_hidden": s["hidden198"],
           "sheet_states198_named_raw": s["named_raw198"], "sheet_states198_unnamed_of_198": s["in_window198"] - s["named198"],
           "sheet_leaders": s["leaders"],
           "globe_states198_in_view": g["in_view198"], "globe_states198_unnamed": g["unnamed198"], "globe_states198_named": g["named198"], "globe_states198_full": g["full198"], "globe_states198_abbr": g["abbr198"],
           "regional_states198_in_view": sum(v["in_view198"] for v in regional), "regional_states198_unnamed": sum(v["unnamed198"] for v in regional),
           "regional12_states198_unnamed": sum(v["unnamed198"] for k, v in views.items() if k.endswith("12")), "regional6_states198_unnamed": sum(v["unnamed198"] for k, v in views.items() if k.endswith("6")),
           "overlaps": sum(v["overlaps"] for v in views.values()), "under_9px": sum(v["under_9px"] for v in views.values()),
           "misplaced": sum(v["misplaced"] for v in views.values()), "misplaced_other_units": sum(len(v["misplaced_other_list"]) for v in views.values()),
           "hit_wrong": sum(len(v["hit_wrong"]) for v in views.values()), "under_panel": sum(v["under_panel"] for v in views.values()),
           "inset_names": sum(v["inset_names198"] for v in views.values()), "sheet_insets": s["insets"], "sheet_inset_land": s["inset_land"],
           "sheet_drag_flips": len(flips), "sheet_zoom_in_losses": len(lost),
           "views": {k: {q: v[q] for q in ("km", "in_view198", "named198", "full198", "abbr198", "leaders", "overlaps", "under_9px", "misplaced", "under_panel", "hidden198", "named_raw198", "in_window198", "inset_only198")} for k, v in views.items()}}
    if "--json" not in sys.argv:
        print("named: states with a name a reader can see (on the map clear of the panels, or in an inset) / states in view (in the window and not hidden under a panel)")
        print("raw:   the old count, which took a name under a panel for a name / states in the window")
        print(f"{'view':26} {'km/px':>6} {'named':>9} {'inset':>5} {'hidden':>6} {'raw':>9} {'full':>5} {'abbr':>5} {'leader':>6} {'labels':>6}  overlaps under9 misplaced hit panel  (other units misplaced)")
        for k, v in views.items():
            print(f"{k:26} {v['km']:6.2f} {v['named198']:4d}/{v['in_view198']:<4d} {v['inset_only198']:5d} {v['hidden198']:6d} {v['named_raw198']:4d}/{v['in_window198']:<4d} {v['full198']:5d} {v['abbr198']:5d} {v['leaders']:6d} {v['labels']:6d}"
                  f"  {v['overlaps']:8d} {v['under_9px']:6d} {v['misplaced']:9d} {len(v['hit_wrong']):3d} {v['under_panel']:5d}  ({len(v['misplaced_other_list'])})")
        for k in ("sheet", "globe"):
            print(f"\n{k}: states named per continent: " + ", ".join(f"{c} {a}/{n}" for c, (a, n) in views[k]["by_continent"].items()))
            print(f"{k}: by the original count, {views[k]['placed204']} of 204 units of TYPE Sovereign country or Country are named")
        for k, v in views.items():
            for i, d in v["insets"].items():
                land = v["inset_land"][i]
                print(f"\n{k}: inset {i}: frame {[round(q) for q in d['rect']]}, {d['km']} km/px ({v['km'] / d['km']:.2f} x), {d['labels']} names, strength {d['alpha']:.2f}")
                print(f"{k}: inset {i}: over land on the main map at {land['on_land']} of {land['points']} points ({land['off_earth']} off the Earth); units with land inside the frame: {land['units'] or 'none'}")
            if v["insets"]:
                print(f"{k}: states named only in an inset: {' '.join(v['inset_only_list'])}")
        print(f"\nsheet, {len(PANS)} drags of a few px: {len(flips)} of {compared} state names changed text or moved against the ground {flips or ''}")
        print(f"sheet, {ZOOMS} steps of 2% closer: {len(lost)} state names lost on the way in {lost or ''}")
        if "--list" in sys.argv:
            for k, v in views.items():
                print(f"\n{k}: unnamed: {' '.join(v['unnamed_list'])}")
                if v["hidden_list"]:
                    print(f"{k}: hidden under a panel, no name: {' '.join(v['hidden_list'])}")
        for k, v in views.items():
            for kind in ("overlap_list", "under_list", "ink_outside_rect", "misplaced_list", "hit_wrong", "taken_list"):
                for row in v[kind]:
                    print(f"  FAULT {k} {kind}: {row}")
            if "--list" in sys.argv:
                for row in v["misplaced_other_list"]:
                    print(f"  note  {k} other unit: {row}")
    print(json.dumps(res))


if __name__ == "__main__":
    main()
