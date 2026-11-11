// Feature overlays that sit ON the rendered world: instanced lines and points (projected in
// the vertex shader by the same camera code as the substrate) and a 2D canvas for labels.

import { program, setUniforms } from './gl.js?v=20261111T002557Z';
import { D2R } from './astro.js?v=20261111T002557Z';
import { R_KM, wtForward, wtInverse, WT_XMAX, WT_YMAX } from './camera.js?v=20261111T002557Z';

const QUAD = new Float32Array([0, -1, 1, -1, 0, 1, 0, 1, 1, -1, 1, 1]);
const SQ = new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]);

export class LineBatch {
  static STRIDE = 11;       // lonA latA lonB latB | r g b a | width kmA kmB
  constructor(gl, prog, dynamic = false) {
    this.gl = gl; this.prog = prog; this.count = 0; this.dynamic = dynamic;
    this.vao = gl.createVertexArray(); this.buf = gl.createBuffer();
    gl.bindVertexArray(this.vao);
    const q = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, q); gl.bufferData(gl.ARRAY_BUFFER, QUAD, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    const S = LineBatch.STRIDE * 4;
    [[1, 4, 0], [2, 4, 16], [3, 3, 32]].forEach(([loc, n, off]) => { gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, S, off); gl.vertexAttribDivisor(loc, 1); });
    gl.bindVertexArray(null);
    this.cap = 0;
  }
  set(data, count = data.length / LineBatch.STRIDE) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    if (data.byteLength > this.cap || !this.dynamic) { gl.bufferData(gl.ARRAY_BUFFER, data, this.dynamic ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW); this.cap = data.byteLength; }
    else gl.bufferSubData(gl.ARRAY_BUFFER, 0, data, 0, count * LineBatch.STRIDE);
    this.count = count;
  }
  draw(camU, o = {}) {
    if (!this.count) return;
    const gl = this.gl;
    gl.useProgram(this.prog.p);
    setUniforms(gl, this.prog, { ...camU, uHeight: o.height || 0, uWidthScale: o.widthScale || 1, uAlpha: o.alpha === undefined ? 1 : o.alpha, uDashKm: o.dashKm || 0, uDashDuty: o.duty || 0.5 });
    gl.bindVertexArray(this.vao);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, this.count);
  }
}

export class PointBatch {
  static STRIDE = 9;        // lon lat h | r g b a | size shape
  constructor(gl, prog, dynamic = false) {
    this.gl = gl; this.prog = prog; this.count = 0; this.dynamic = dynamic;
    this.vao = gl.createVertexArray(); this.buf = gl.createBuffer();
    gl.bindVertexArray(this.vao);
    const q = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, q); gl.bufferData(gl.ARRAY_BUFFER, SQ, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    const S = PointBatch.STRIDE * 4;
    [[1, 3, 0], [2, 4, 12], [3, 2, 28]].forEach(([loc, n, off]) => { gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, S, off); gl.vertexAttribDivisor(loc, 1); });
    gl.bindVertexArray(null);
  }
  set(data, count = data.length / PointBatch.STRIDE) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    gl.bufferData(gl.ARRAY_BUFFER, data, this.dynamic ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW);
    this.count = count;
  }
  draw(camU, o = {}) {
    if (!this.count) return;
    const gl = this.gl;
    gl.useProgram(this.prog.p);
    setUniforms(gl, this.prog, { ...camU, uSizeScale: o.sizeScale || 1, uAlpha: o.alpha === undefined ? 1 : o.alpha });
    gl.bindVertexArray(this.vao);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, this.count);
  }
}

function kmBetween(lon1, lat1, lon2, lat2) {
  const p1 = lat1 * D2R, p2 = lat2 * D2R, dl = (lon2 - lon1) * D2R;
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Build line instances from polylines. lines: array of flat [lon, lat, ...] in DEGREES. */
export function segmentsFromLines(lines, color, width) {
  let n = 0;
  for (const l of lines) n += Math.max(0, l.length / 2 - 1);
  const out = new Float32Array(n * LineBatch.STRIDE);
  let o = 0;
  for (const l of lines) {
    let km = 0;
    for (let i = 0; i + 3 < l.length; i += 2) {
      const d = kmBetween(l[i], l[i + 1], l[i + 2], l[i + 3]);
      out[o++] = l[i] * D2R; out[o++] = l[i + 1] * D2R; out[o++] = l[i + 2] * D2R; out[o++] = l[i + 3] * D2R;
      out[o++] = color[0]; out[o++] = color[1]; out[o++] = color[2]; out[o++] = color[3];
      out[o++] = width; out[o++] = km; out[o++] = km + d;
      km += d;
    }
  }
  return out;
}
/** Quantised [lon*100, lat*100, ...] -> degrees. */
export const deq = (qline) => { const a = new Float32Array(qline.length); for (let i = 0; i < a.length; i++) a[i] = qline[i] / 100; return a; };

export function graticule(step = 15) {
  const lines = [];
  for (let lon = -180; lon < 180; lon += step) { const l = []; for (let lat = -88; lat <= 88; lat += 2) l.push(lon, lat); lines.push(l); }
  for (let lat = -75; lat <= 75; lat += step) { const l = []; for (let lon = -180; lon <= 180; lon += 2) l.push(lon, lat); lines.push(l); }
  return lines;
}
export function parallels(lats) {
  return lats.map((lat) => { const l = []; for (let lon = -180; lon <= 180; lon += 2) l.push(lon, lat); return l; });
}

/** Points along the great circle between two places (degrees), n segments. */
export function greatCircle(lon1, lat1, lon2, lat2, n) {
  const a = [Math.cos(lat1 * D2R) * Math.cos(lon1 * D2R), Math.cos(lat1 * D2R) * Math.sin(lon1 * D2R), Math.sin(lat1 * D2R)];
  const b = [Math.cos(lat2 * D2R) * Math.cos(lon2 * D2R), Math.cos(lat2 * D2R) * Math.sin(lon2 * D2R), Math.sin(lat2 * D2R)];
  const om = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const s0 = om < 1e-6 ? 1 - t : Math.sin((1 - t) * om) / Math.sin(om), s1 = om < 1e-6 ? t : Math.sin(t * om) / Math.sin(om);
    const x = a[0] * s0 + b[0] * s1, y = a[1] * s0 + b[1] * s1, z = a[2] * s0 + b[2] * s1;
    out.push(Math.atan2(y, x) / D2R, Math.asin(Math.max(-1, Math.min(1, z))) / D2R);
  }
  return out;
}

// ------------------------------------------- labels -------------------------------------------
// Names on the map. Every label is an exact rectangle; nothing overlaps anything.
//
// STATES are placed by their own geometry (register F1; the reference is a printed political sheet that
// names every state with small type, abbreviations and leader lines). In order:
//   A1  every state tries its FULL NAME INSIDE itself: one line or two, at the size its extent on screen
//       earns and then down to 9 px, at each of its good interior points;
//   A2  a state still unnamed tries, in turn: its full name beside it, touching it and on no other land;
//       its abbreviation (Natural Earth's own) inside; its abbreviation beside, touching;
//   B   what is left goes to open water with a LEADER LINE back to the state, the nearest free water first.
// ONE PRIORITY RULE throughout: the more populous state chooses first, and a name once placed is never
// moved by a later one. The order does not depend on the camera, so which states win does not change as
// the map is dragged. No history is kept either: the same view always gives the same picture.
// What "inside", "touching" and "open water" mean is tested against the ground, not assumed: each
// candidate rectangle is sampled against the 0.1 degree owner raster (data.js).
// Everything else (seas, dependencies, cities, landforms) keeps one position each and is placed after the
// states, so that it can never cost a state its name.
// CONTINENTS are set last of all, in the manner of a political wall map: wide letter-spaced capitals in quiet
// ink that lie across the states. Each letter is its own rectangle and goes only where nothing else is, so a
// continent's name costs no other name its place and touches no other name's ink (see _spread).
// TAKEN GROUND: setBlocked() gives the layer rectangles of the window that are not map (the interface's panels,
// an inset's frame). No name, leader or letter is set on them; they are tested at the real scale (see draw).
// A SUB-VIEW (an inset) is a second Labels on the same canvas, confined to a rectangle of it: place() says where.
const SERIF = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif';
const SANS = '-apple-system, "Helvetica Neue", "Segoe UI", system-ui, sans-serif';

const MIN_TYPE = 9;                              // px; no state name is set smaller
const RINGS = [3, 9, 16, 24, 33, 43, 54, 66];    // px from a state's anchor to the nearest point of a name beside it
const DIRS = [0, 180, 22.5, -22.5, 157.5, -157.5, 45, -45, 135, -135, 67.5, -67.5, 112.5, -112.5, 90, -90]
  .map((d) => [Math.cos(d * D2R), -Math.sin(d * D2R)]);   // east first; screen y runs down
const LEADER_MAX = 46;                           // px of leader line, label to the edge of its state
const LEADER_OVER_OTHERS = 20;                   // px of that which may cross other states' land
const IN_OWN = 0.3, IN_FOREIGN = 0.15;           // a name "inside": this share of it on its own state at least, that share on others at most
const PAD_X = 2, PAD_Y = 2;                      // clear space kept around a state's name
const NP = 13;                                   // interior points per state: 6 boxes, the deepest point, the source's label point, 5 more
const SLOTS = NP + RINGS.length * DIRS.length;
const ZOOM_STEP = 1.05;                         // the sheet's layout is solved once per 5% of zoom and rides the ground in between
const CONFIRMED = 1 << 24, UNTOUCHED = 1 << 25; // bits in a candidate's cached result (see _scan, _confirm)
const NV = 10;                                   // text variants per state (see _variants)
// A continent's name (see _spread)
const SPREAD_MIN = 14, SPREAD_MAX = 22;          // px; its type, a fourteenth of the continent's breadth on screen
const SPREAD_FILL = [1, 0.88, 0.78, 0.68, 0.58, 0.5, 0.42, 0.35, 0.28];   // share of that breadth from its first letter to its last, widest first
const SPREAD_TIGHT = 1.3, SPREAD_LOOSE = 4.2;    // letter pitch, in type sizes: closer is ordinary type, wider no longer reads as a word
const SPREAD_ROW = 0.5, SPREAD_UP = 0.5;         // rows tried: every half a type size, out to this share of the breadth above and below the anchor
const SPREAD_SHIFT = 0.3, SPREAD_ALONG = 0.4;    // and shifts along the line: every 0.3 of the pitch, out to this share of the breadth
const SPREAD_GAPS = [1.9, 2.4, 2.9, 3.4, 3.9];  // line spacing of a name on two lines, in type sizes
const SPREAD_PAD = 2.5;                          // px kept clear around each letter
const SPREAD_ON_OWN = 0.6;                       // share of its letters that must lie on the continent's own land (the rest: on water)
const SPREAD_STRAY_Y = 1.2, SPREAD_STRAY_X = 0.6, SPREAD_OWN = 0.3;   // the score: breadths lost per breadth strayed up or along; gained for all of it on its own land
const SPREAD_ALIAS = { Australia: 'Oceania' };   // Natural Earth's continent field calls it that

// The sheet's inverse projection as a table (the exact inverse is a Newton solve, far too slow to ask
// what lies under every corner of every candidate rectangle). 256 x 128 cells, bilinear; a cell with a
// corner off the sheet falls back to the exact solve.
const LUT_W = 256, LUT_H = 128;
let LUT = null;
function wtTable() {
  const lon = new Float32Array((LUT_W + 1) * (LUT_H + 1)), lat = new Float32Array(lon.length);
  for (let j = 0; j <= LUT_H; j++) {
    const y = -WT_YMAX + (2 * WT_YMAX * j) / LUT_H;
    let lam = NaN, phi = NaN;
    for (let i = 0; i <= LUT_W; i++) {
      const x = -WT_XMAX + (2 * WT_XMAX * i) / LUT_W, o = j * (LUT_W + 1) + i;
      let ok = false;
      if (lam === lam) {                         // warm start from the neighbour: three Newton steps
        let l = lam, p = phi;
        for (let it = 0; it < 4 && !ok; it++) {
          const f = wtForward(l, p), ex = f[0] - x, ey = f[1] - y;
          if (ex * ex + ey * ey < 1e-14) { ok = Math.abs(l) <= Math.PI + 1e-6; break; }
          const h = 1e-5, a = wtForward(l + h, p), b = wtForward(l, p + h);
          const flx = (a[0] - f[0]) / h, fly = (a[1] - f[1]) / h, fpx = (b[0] - f[0]) / h, fpy = (b[1] - f[1]) / h;
          const det = flx * fpy - fpx * fly;
          if (Math.abs(det) < 1e-12) break;
          l -= (ex * fpy - fpx * ey) / det; p -= (flx * ey - ex * fly) / det;
          p = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, p));
        }
        if (ok) { lam = l; phi = p; }
      }
      if (!ok) { const ll = wtInverse(x, y); if (ll) { lam = ll[0]; phi = ll[1]; ok = true; } else { lam = phi = NaN; } }
      lon[o] = ok ? lam / D2R : NaN; lat[o] = ok ? phi / D2R : NaN;
    }
  }
  return { lon, lat };
}

function segHitsRect(ax, ay, bx, by, x0, y0, x1, y1) {
  if ((ax < x0 && bx < x0) || (ax > x1 && bx > x1) || (ay < y0 && by < y0) || (ay > y1 && by > y1)) return false;
  let t0 = 0, t1 = 1;                            // Liang-Barsky
  const dx = bx - ax, dy = by - ay;
  const clip = (p, q) => { if (p === 0) return q >= 0; const r = q / p; if (p < 0) { if (r > t1) return false; if (r > t0) t0 = r; } else { if (r < t0) return false; if (r < t1) t1 = r; } return true; };
  return clip(-dx, ax - x0) && clip(dx, x1 - ax) && clip(-dy, ay - y0) && clip(dy, y1 - ay);
}
function segsCross(a, b) {
  const d = (b[2] - b[0]) * (a[3] - a[1]) - (b[3] - b[1]) * (a[2] - a[0]);
  if (Math.abs(d) < 1e-9) return false;
  const u = ((b[0] - a[0]) * (a[3] - a[1]) - (b[1] - a[1]) * (a[2] - a[0])) / d;
  const t = ((b[0] - a[0]) * (b[3] - b[1]) - (b[1] - a[1]) * (b[2] - b[0])) / d;
  return u >= 0 && u <= 1 && t >= 0 && t <= 1;
}

export class Labels {
  constructor(canvas, sub = false) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.items = []; this.placed = [];
    this.states = []; this.before = []; this.after = []; this.geo = null;
    this._tw = new Map(); this._cap = new Map(); this._epoch = 0; this._key = ''; this._sig = null; this._gen = 0;
    this.sub = sub; this.ox = 0; this.oy = 0; this.alpha = 1; this.blocked = []; this._bsig = ''; this.underlay = null; this._cont = new Map();
  }
  resize(w, h, dpr) { if (!this.sub) { this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr); } this.w = w; this.h = h; this.dpr = dpr; this._sig = null; }
  /** A sub-view's rectangle on the shared canvas, CSS px. Its own coordinates run from its top-left corner. */
  place(x, y, w, h, dpr) { this.ox = x; this.oy = y; if (w !== this.w || h !== this.h || dpr !== this.dpr) this.resize(w, h, dpr); }
  /** Rectangles [x0, y0, x1, y1] of this view (CSS px, its own coordinates) that are taken by something that is not map. */
  setBlocked(rects) {
    const sig = rects.map((r) => r.map((v) => Math.round(v * 2) / 2).join(',')).join(';');
    if (sig === this._bsig) return false;
    this._bsig = sig; this.blocked = rects.map((r) => r.slice()); this._sig = null;
    return true;
  }
  /** Is a rectangle at the REAL scale clear of everything taken? */
  _clear(x0, y0, x1, y1) {
    const B = this.blocked;
    for (let i = 0; i < B.length; i++) { const r = B[i]; if (x0 < r[2] && x1 > r[0] && y0 < r[3] && y1 > r[1]) return false; }
    return true;
  }
  /** The same for a leader, given in layout coordinates with the rectangle of the name it starts at. */
  _segClear(seg, R) {
    const B = this.blocked;
    if (!B.length) return true;
    const z = this._z, w2 = this.w / 2, h2 = this.h / 2, dx = ((R.x0 + R.x1) / 2 - w2) * (z - 1), dy = ((R.y0 + R.y1) / 2 - h2) * (z - 1);
    const ax = seg[0] + dx, ay = seg[1] + dy, bx = w2 + (seg[2] - w2) * z, by = h2 + (seg[3] - h2) * z;
    for (let i = 0; i < B.length; i++) { const r = B[i]; if (segHitsRect(ax, ay, bx, by, r[0] - 2.5, r[1] - 2.5, r[2] + 2.5, r[3] + 2.5)) return false; }
    return true;
  }

  /** items: {text, lon, lat, cls, prio, minKm, maxKm, ref} - lower prio is placed first and keeps its place.
   *  A country item with `state` is placed by its geometry (ref[1] carries lp, pts, inner, area, sea); items.geo is the owner raster. */
  setItems(items) {
    this.geo = items.geo || null;
    this.items = items.slice().sort((a, b) => a.prio - b.prio);
    const st = (it) => it.cls === 'country' && it.state && this.geo;
    this.states = this.items.filter(st);
    const first = this.states.length ? this.states[0].prio : Infinity;
    this.before = this.items.filter((it) => !st(it) && it.prio < first);
    this.after = this.items.filter((it) => !st(it) && it.prio >= first);
    this.states.forEach((it, i) => { it._i = i; it._L = null; });
    // which continent each unit is on (Natural Earth's own field): a continent's letters lie on its own land
    this._cont = new Map();
    for (const it of this.items) if (it.cls === 'country' && it.ref && it.ref[1] && it.ref[1].id) this._cont.set(it.ref[1].id, it.ref[1].continent);
    this._gen++; this._sig = null;
  }

  // ---- text metrics (cached: measureText is the expensive call) ----
  _width(text, font, spacing) {
    const key = font + '|' + spacing + '|' + text;
    let w = this._tw.get(key);
    if (w === undefined) {
      const ctx = this.ctx;
      ctx.font = font;
      const ls = 'letterSpacing' in ctx;
      if (ls) ctx.letterSpacing = spacing + 'px';
      w = ctx.measureText(text).width - (ls ? spacing : 0);       // the trailing gap is not part of the word
      this._tw.set(key, w);
    }
    return w;
  }
  _capHeight(font, size) {
    let c = this._cap.get(font);
    if (c === undefined) { this.ctx.font = font; this.ctx.textBaseline = 'alphabetic'; const m = this.ctx.measureText('H'); c = m.actualBoundingBoxAscent > 0 ? m.actualBoundingBoxAscent : size * 0.72; this._cap.set(font, c); }
    return c;
  }

  // ---- what is under a screen point ----
  /** Sets this._lo/_la (degrees). False when the point is off the Earth. */
  _inv(x, y) {
    const cam = this.cam;
    if (this._sheet) {
      const fx = x * this._fa + this._fb, fy = y * this._fc + this._fd;          // table coordinates of the pixel
      if (!(fx >= 0 && fy >= 0 && fx < LUT_W && fy < LUT_H)) return false;
      const i = fx | 0, j = fy | 0, o = j * (LUT_W + 1) + i, u = fx - i, v = fy - j, T = LUT;
      const a = T.lon[o], b = T.lon[o + 1], c = T.lon[o + LUT_W + 1], d = T.lon[o + LUT_W + 2];
      if (a !== a || b !== b || c !== c || d !== d) {             // at the sheet's edge: the exact inverse
        if (a !== a && b !== b && c !== c && d !== d) return false;
        const ll = wtInverse(cam.mapCenter[0] + (x - this.w / 2) * cam.mapUnitsPerPx, cam.mapCenter[1] - (y - this.h / 2) * cam.mapUnitsPerPx);
        if (!ll) return false;
        this._lo = ll[0] / D2R; this._la = ll[1] / D2R;
        return true;
      }
      this._lo = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
      this._la = (T.lat[o] * (1 - u) + T.lat[o + 1] * u) * (1 - v) + (T.lat[o + LUT_W + 1] * (1 - u) + T.lat[o + LUT_W + 2] * u) * v;
      return true;
    }
    // the globe: where the ray through the pixel meets the unit sphere (no normalising: a = d.d rides along)
    const B = this._b, G = this._g, nx = x * G[0] - G[1], ny = G[2] - y * G[3];
    const dx = B.right[0] * nx + B.up[0] * ny + B.f[0], dy = B.right[1] * nx + B.up[1] * ny + B.f[1], dz = B.right[2] * nx + B.up[2] * ny + B.f[2];
    const a = dx * dx + dy * dy + dz * dz, bb = B.pos[0] * dx + B.pos[1] * dy + B.pos[2] * dz, disc = bb * bb - a * G[4];
    if (disc <= 0 || bb >= 0) return false;
    const s = (-bb - Math.sqrt(disc)) / a, pz = B.pos[2] + s * dz;
    this._lo = Math.atan2(B.pos[1] + s * dy, B.pos[0] + s * dx) / D2R; this._la = Math.asin(pz > 1 ? 1 : pz < -1 ? -1 : pz) / D2R;
    return true;
  }
  /** Id of the unit under a screen point: 0 for water, -1 off the Earth. */
  _owner(x, y) {
    const g = this.geo;
    if (this._sheet) {                           // the common case of _inv, written out: this is the hot path
      const fx = x * this._fa + this._fb, fy = y * this._fc + this._fd;
      if (!(fx >= 0 && fy >= 0 && fx < LUT_W && fy < LUT_H)) return -1;
      const i = fx | 0, j = fy | 0, o = j * (LUT_W + 1) + i, T = LUT.lon, U = LUT.lat;
      const a = T[o], b = T[o + 1], c = T[o + LUT_W + 1], d = T[o + LUT_W + 2];
      if (a === a && b === b && c === c && d === d) {
        const u = fx - i, v = fy - j, lo = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
        const la = (U[o] * (1 - u) + U[o + 1] * u) * (1 - v) + (U[o + LUT_W + 1] * (1 - u) + U[o + LUT_W + 2] * u) * v;
        let cc = ((lo + 180) * 10) | 0, rr = ((90 - la) * 10) | 0;
        if (cc < 0) cc = 0; else if (cc >= g.cols) cc = g.cols - 1;
        if (rr < 0) rr = 0; else if (rr >= g.rows) rr = g.rows - 1;
        return g.id[rr * g.cols + cc];
      }
    }
    if (!this._inv(x, y)) return -1;
    let c = ((this._lo + 180) * 10) | 0, r = ((90 - this._la) * 10) | 0;
    if (c < 0) c = 0; else if (c >= g.cols) c = g.cols - 1;
    if (r < 0) r = 0; else if (r >= g.rows) r = g.rows - 1;
    return g.id[r * g.cols + c];
  }
  /** The same for "is there any other land here": at the whole-Earth scales it answers from the 0.4 degree blocks
   *  (255: land of more than one unit), so that an island smaller than a pixel still counts. */
  _ownerB(x, y) {
    if (this._exact) return this._owner(x, y);
    if (!this._inv(x, y)) return -1;
    const g = this.geo;
    let c = ((this._lo + 180) * 2.5) | 0, r = ((90 - this._la) * 2.5) | 0;
    if (c < 0) c = 0; else if (c >= g.poolCols) c = g.poolCols - 1;
    if (r < 0) r = 0; else if (r >= g.poolRows) r = g.poolRows - 1;
    return g.pool[r * g.poolCols + c];
  }
  /** Sample a rectangle against the ground. -1 when any of it is off the Earth or more than `share` of it
   *  lies on other units; otherwise centreOnOwn | others << 1 | own << 8 | samples << 16. */
  _scan(x0, y0, x1, y1, own, share) {
    // share 0 (beside): samples run edge to edge, where other land would first intrude, and ask for ANY other land.
    // Otherwise (inside): at cell centres, so that the counts are shares of the name's area; its centre must be its own.
    const edge = share === 0;
    let o = edge ? this._ownerB((x0 + x1) / 2, (y0 + y1) / 2) : this._owner((x0 + x1) / 2, (y0 + y1) / 2);
    if (o < 0) return -1;
    const cOwn = o === own ? 1 : 0;
    if (edge ? o && !cOwn : !cOwn) return -1;
    const nx = edge ? Math.min(14, Math.max(3, Math.ceil((x1 - x0) / 5) + 1)) : Math.min(20, Math.max(6, Math.ceil((x1 - x0) / 3))), ny = edge ? (y1 - y0 > 17 ? 4 : 3) : 4, max = Math.floor(share * nx * ny);
    if (!edge && (this._owner(x0, y0) < 0 || this._owner(x1, y0) < 0 || this._owner(x0, y1) < 0 || this._owner(x1, y1) < 0)) return -1;   // a corner off the limb
    let nOwn = 0, nFor = 0;
    for (let j = 0; j < ny; j++) {
      const y = edge ? y0 + ((y1 - y0) * j) / (ny - 1) : y0 + ((y1 - y0) * (j + 0.5)) / ny;
      for (let i = 0; i < nx; i++) {
        o = edge ? this._ownerB(x0 + ((x1 - x0) * i) / (nx - 1), y) : this._owner(x0 + ((x1 - x0) * (i + 0.5)) / nx, y);
        if (o < 0) return -1;
        if (o === own) nOwn++; else if (o && ++nFor > max) return -1;
      }
    }
    return cOwn | (nFor << 1) | (nOwn << 8) | ((nx * ny) << 16);
  }

  // ---- collisions: exact rectangles in a hash of 64 px cells, plus leader segments ----
  _hashInit() {
    const gw = Math.ceil(this.w / 64) + 1, gh = Math.ceil(this.h / 64) + 1;
    if (!this._cells || this._gw !== gw || this._gh !== gh) { this._cells = Array.from({ length: gw * gh }, () => []); this._gw = gw; this._gh = gh; } else for (const c of this._cells) c.length = 0;
    this._R = []; this._segs = [];
  }
  /** kind: 0 a label, 1 a state's anchor (ignored by its owner, dropped once the states are placed). */
  _take(x0, y0, x1, y1, owner, kind) {
    const idx = this._R.length;
    this._R.push({ x0, y0, x1, y1, owner, kind, dead: false });
    const gw = this._gw, gh = this._gh, cx0 = Math.min(gw - 1, Math.max(0, Math.floor(x0 / 64))), cx1 = Math.max(0, Math.min(gw - 1, Math.floor(x1 / 64))), cy0 = Math.min(gh - 1, Math.max(0, Math.floor(y0 / 64))), cy1 = Math.max(0, Math.min(gh - 1, Math.floor(y1 / 64)));
    for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) this._cells[cy * gw + cx].push(idx);
  }
  _free(x0, y0, x1, y1, owner) {
    const gw = this._gw, R = this._R, gh = this._gh, cx0 = Math.min(gw - 1, Math.max(0, Math.floor(x0 / 64))), cx1 = Math.max(0, Math.min(gw - 1, Math.floor(x1 / 64))), cy0 = Math.min(gh - 1, Math.max(0, Math.floor(y0 / 64))), cy1 = Math.max(0, Math.min(gh - 1, Math.floor(y1 / 64)));
    for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) {
      const cell = this._cells[cy * gw + cx];
      for (let n = 0; n < cell.length; n++) {
        const r = R[cell[n]];
        if (r.dead) continue;
        if (r.kind === 1) { if (r.owner !== owner && x0 + PAD_X < r.x1 && x1 - PAD_X > r.x0 && y0 + PAD_Y < r.y1 && y1 - PAD_Y > r.y0) return false; continue; }
        if (x0 < r.x1 && x1 > r.x0 && y0 < r.y1 && y1 > r.y0) return false;
      }
    }
    for (const s of this._segs) if (segHitsRect(s[0], s[1], s[2], s[3], x0, y0, x1, y1)) return false;
    return true;
  }
  _segFree(seg, owner) {
    const gw = this._gw, R = this._R, x0 = Math.min(seg[0], seg[2]) - 3, x1 = Math.max(seg[0], seg[2]) + 3, y0 = Math.min(seg[1], seg[3]) - 3, y1 = Math.max(seg[1], seg[3]) + 3;
    const gh = this._gh, cx0 = Math.min(gw - 1, Math.max(0, Math.floor(x0 / 64))), cx1 = Math.max(0, Math.min(gw - 1, Math.floor(x1 / 64))), cy0 = Math.min(gh - 1, Math.max(0, Math.floor(y0 / 64))), cy1 = Math.max(0, Math.min(gh - 1, Math.floor(y1 / 64)));
    for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) {
      const cell = this._cells[cy * gw + cx];
      for (let n = 0; n < cell.length; n++) {
        const r = R[cell[n]];
        if (r.dead || (r.kind === 1 && r.owner === owner)) continue;
        if (segHitsRect(seg[0], seg[1], seg[2], seg[3], r.x0, r.y0, r.x1, r.y1)) return false;
      }
    }
    // no leader crosses another, and none passes within 4 px of another's dot: which name a dot belongs to must be plain
    for (const s of this._segs) if (segsCross(s, seg) || segHitsRect(seg[0], seg[1], seg[2], seg[3], s[2] - 4, s[3] - 4, s[2] + 4, s[3] + 4) || segHitsRect(s[0], s[1], s[2], s[3], seg[2] - 4, seg[3] - 4, seg[2] + 4, seg[3] + 4)) return false;
    return true;
  }

  // ---- a state's text variants ----
  // 0-5 full name inside: one line / two lines at the earned size, a middle size, the floor;
  // 6-7 full name beside (one line / two); 8-9 abbreviation (inside at up to 10 px; the floor inside or beside).
  _variants(it, S, atlas) {
    const key = (atlas ? 'a' : 's') + S;
    if (it._vk === key) return it._v;
    const full = it.text.toUpperCase(), sp = full.lastIndexOf(' ') > 0 && full.length >= 8;
    let two = null;
    if (sp) {                                    // break at the space nearest the middle
      let best = -1;
      for (let i = full.indexOf(' '); i >= 0; i = full.indexOf(' ', i + 1)) if (best < 0 || Math.abs(i - full.length / 2) < Math.abs(best - full.length / 2)) best = i;
      two = [full.slice(0, best), full.slice(best + 1)];
    }
    const mk = (lines, size, abbr) => {
      const font = `${atlas ? 600 : 500} ${size}px ${SANS}`, spacing = +(size * (size >= 11 ? 0.15 : 0.08)).toFixed(2), cap = this._capHeight(font, size);
      const ws = lines.map((t) => this._width(t, font, spacing)), w = Math.max(...ws), pitch = size * 1.12;
      return { lines, ws, size, font, spacing, cap, w, h: cap + (lines.length - 1) * pitch, pitch, abbr };
    };
    const mid = S > 11 ? 10.5 : S > 10 ? 10 : 0, v = new Array(NV).fill(null);
    v[0] = mk([full], S, false); if (two) v[1] = mk(two, S, false);
    if (mid) { v[2] = mk([full], mid, false); if (two) v[3] = mk(two, mid, false); }
    v[4] = mk([full], MIN_TYPE, false); if (two) v[5] = mk(two, MIN_TYPE, false);
    v[6] = mk([full], 9.5, false); if (two) v[7] = mk(two, 9.5, false);
    if (it.abbr) { const ab = it.abbr.toUpperCase(); v[8] = mk([ab], Math.min(S, 10), true); v[9] = mk([ab], MIN_TYPE, true); }
    it._vk = key; it._v = v;
    return v;
  }

  /** Per-frame geometry of a state: where its anchor and interior points fall, its scale on screen, the size its name earns. */
  _prep(it) {
    const cam = this.cam, c = it.ref[1];
    let L = it._L;
    if (!L) L = it._L = { epoch: -1, ox: new Float32Array(NP), oy: new Float32Array(NP), ok: new Uint8Array(NP), code: new Int32Array(NV * SLOTS), probe: new Int8Array(RINGS.length * DIRS.length) };
    const A = cam.project(c.lp[0], c.lp[1]);
    if (!A) { L.on = false; return L; }
    L.ax = A[0]; L.ay = A[1];
    if (L.epoch !== this._epoch) {
      L.epoch = this._epoch; L.code.fill(-2); L.probe.fill(-2);
      const cl = Math.max(0.05, Math.cos(c.lp[1] * D2R)), e = cam.project(c.lp[0] + 0.3 / cl, c.lp[1]), n = cam.project(c.lp[0], c.lp[1] + (c.lp[1] > 89 ? -0.3 : 0.3));
      if (!e || !n) { L.on = false; L.epoch = -1; return L; }
      const km = 0.3 * R_KM * D2R, ex = (e[0] - A[0]) / km, ey = (e[1] - A[1]) / km, nx = (n[0] - A[0]) / km, ny = (n[1] - A[1]) / km;
      L.sE = Math.hypot(ex, ey); L.sN = Math.hypot(nx, ny);
      const det = Math.abs(ex * ny - ey * nx);
      L.scale = Math.sqrt(det);                                   // px per km, areal
      L.flat = det / Math.max(L.sE, L.sN) ** 2;                   // 1 face on, 0 on the limb
      const d = Math.sqrt(c.area || 1) * L.scale;                 // side of the square of the state's area, px
      L.S = d < 42 ? 10 : d < 70 ? 10.5 : d < 105 ? 11.5 : d < 150 ? 12.5 : 13.5;
      L.d = d; L.tiny = d < 4;
      L.reach = (c.reach || 0) * L.scale;
      L.sea = (c.sea || 0) * L.scale;
      const P = L.P = [];
      for (const q of c.inner || []) P.push(q);
      while (P.length < 6) P.push(null);
      P.push(c.lp, [it.lon, it.lat]);
      for (const q of c.pts || []) P.push(q);
      for (let i = 0; i < NP; i++) {
        const q = P[i], p = q ? (q === c.lp ? A : cam.project(q[0], q[1])) : null;
        L.ok[i] = p ? (q.length > 3 && !q[3] ? 2 : 1) : 0;         // 2: a point on a far part of the state (Svalbard, Alaska, Guiana)
        if (p) { L.ox[i] = p[0] - A[0]; L.oy[i] = p[1] - A[1]; }
      }
    }
    L.on = true;
    return L;
  }

  _rectAt(v, cx, cy) { const R = this._rc; R.x0 = cx - v.w / 2 - PAD_X; R.x1 = cx + v.w / 2 + PAD_X; R.y0 = cy - v.h / 2 - PAD_Y; R.y1 = cy + v.h / 2 + PAD_Y; return R; }
  /** Is the rectangle wholly in the window, once the layout is carried to the real scale (see draw)? */
  _visible(R) {
    const z = this._z, hw = (R.x1 - R.x0) / 2, hh = (R.y1 - R.y0) / 2, cx = this.w / 2 + ((R.x0 + R.x1) / 2 - this.w / 2) * z, cy = this.h / 2 + ((R.y0 + R.y1) / 2 - this.h / 2) * z;
    return cx - hw >= 1 && cy - hh >= 1 && cx + hw <= this.w - 1 && cy + hh <= this.h - 1 && this._clear(cx - hw, cy - hh, cx + hw, cy + hh);
  }
  _onScreen(x, y, mx, my) { const z = this._z, X = this.w / 2 + (x - this.w / 2) * z, Y = this.h / 2 + (y - this.h / 2) * z; return X >= -mx && X <= this.w + mx && Y >= -my && Y <= this.h + my; }

  /** Try a state's variant vi inside itself, at each interior point. */
  _tryInside(it, L, vi) {
    const v = it._v[vi];
    if (!v) return false;
    if (L.d * L.d < 0.8 * IN_OWN * v.w * v.h) return false;       // all of the state would not cover enough of this name
    const c = it.ref[1], asp = this.geo.aspects, a = (v.w / v.h) * (L.sN / L.sE);
    let b = 0;
    while (b < asp.length - 1 && asp[b] < a) b++;
    // the box of this name's proportion first, then the deepest point, the source's label point, the rest
    for (let n = 0; n < NP - 5; n++) {
      const pi = n === 0 ? b : n === 1 ? 6 : n === 2 ? 7 : n + 5;
      if (!L.ok[pi] || (L.ok[pi] === 2 && L.anchor)) continue;      // a far part carries the name only when the main part is out of view
      const slot = vi * SLOTS + pi;
      let code = L.code[slot];
      if (code === -1) continue;                                  // already known not to be its own ground
      const R = this._rectAt(v, L.ax + L.ox[pi], L.ay + L.oy[pi]);
      if (!this._visible(R) || !this._free(R.x0, R.y0, R.x1, R.y1, it._i)) continue;
      if (code === -2) code = L.code[slot] = this._scan(R.x0 + PAD_X, R.y0 + PAD_Y, R.x1 - PAD_X, R.y1 - PAD_Y, c.id, IN_FOREIGN);
      if (code < 0 || !(code & 1)) continue;
      const n0 = code >> 16;
      if (((code >> 8) & 255) < IN_OWN * n0) continue;
      this._place(it, v, R, 'in', null, L);
      return true;
    }
    return false;
  }

  /** Before a name is set beside its state: look again, closely. The first scan samples every 5 px, and a thin cape
   *  or a small island of another state can pass between samples. Here no cell under the name is skipped: at the
   *  whole-Earth scales the 0.4 degree raster (a block is clear only if no other unit has any land in it), closer in
   *  the 0.1 degree one. touch: it must also reach its own ground, asked of the polygon where the raster is coarse. */
  _confirm(R, c, touch) {
    const g = this.geo, wide = !this._exact, m = this._margin, x0 = R.x0 + PAD_X - m, x1 = R.x1 - PAD_X + m, y0 = R.y0 + PAD_Y - m, y1 = R.y1 - PAD_Y + m;
    const pitch = Math.max(1, Math.min(2.5, 0.9 * this._cellPx * (wide ? 4 : 1)));
    const nx = Math.max(3, Math.ceil((x1 - x0) / pitch) + 1), ny = Math.max(3, Math.ceil((y1 - y0) / pitch) + 1);
    let own = 0;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      if (!this._inv(x0 + ((x1 - x0) * i) / (nx - 1), y0 + ((y1 - y0) * j) / (ny - 1))) return false;
      let cc = ((this._lo + 180) * 10) | 0, rr = ((90 - this._la) * 10) | 0;
      if (cc < 0) cc = 0; else if (cc >= g.cols) cc = g.cols - 1;
      if (rr < 0) rr = 0; else if (rr >= g.rows) rr = g.rows - 1;
      const fine = g.id[rr * g.cols + cc], o = wide ? g.pool[(rr >> 2) * g.poolCols + (cc >> 2)] : fine;
      if (o && o !== c.id) return false;
      if (fine === c.id) own++;
    }
    if (!touch) return true;
    if (wide) return own > 0;
    // the raster's coast is half a cell generous: does the name really reach the state? (its own polygons only: cheap)
    const tx0 = R.x0 + PAD_X - 1.5, tx1 = R.x1 - PAD_X + 1.5, ty0 = R.y0 + PAD_Y - 1.5, ty1 = R.y1 - PAD_Y + 1.5;
    const mx = Math.max(3, Math.ceil((tx1 - tx0) / 2) + 1), my = Math.max(3, Math.ceil((ty1 - ty0) / 2) + 1);
    for (let j = 0; j < my; j++) for (let i = 0; i < mx; i++) if (this._inv(tx0 + ((tx1 - tx0) * i) / (mx - 1), ty0 + ((ty1 - ty0) * j) / (my - 1)) && g.inside(c, this._lo, this._la)) return true;
    return false;
  }

  /** Try a state's variant vi beside its anchor on ring ri. touching: the name must touch its own state (no leader).
   *  overMax: px of other states' land a leader may cross. */
  _tryBeside(it, L, vi, ri, touching, overMax = 0) {
    const v = it._v[vi];
    if (!v) return false;
    const c = it.ref[1], g = RINGS[ri], m = this._margin;
    if (touching && g > L.reach + 3) return false;
    for (let di = 0; di < DIRS.length; di++) {
      const ux = DIRS[di][0], uy = DIRS[di][1], kx = Math.max(-1, Math.min(1, ux * 1.6)), ky = Math.max(-1, Math.min(1, uy * 1.6));
      // a point every variant's rectangle covers at this position: on other land, nothing fits here
      let pr = L.probe[ri * DIRS.length + di];
      if (pr === -2) { const o = this._ownerB(L.ax + g * ux + 6 * kx, L.ay + g * uy + 3 * ky); pr = L.probe[ri * DIRS.length + di] = o === 0 || o === c.id ? 1 : 0; }
      if (!pr) continue;
      const slot = vi * SLOTS + NP + ri * DIRS.length + di;
      let code = L.code[slot];
      if (code === -1) continue;                                  // already known to lie on other land
      const cx = L.ax + g * ux + (v.w / 2) * kx, cy = L.ay + g * uy + (v.h / 2) * ky;
      const R = this._rectAt(v, cx, cy);
      if (!this._visible(R) || !this._free(R.x0, R.y0, R.x1, R.y1, it._i)) continue;
      if (code === -2) code = L.code[slot] = this._scan(R.x0 + PAD_X - m, R.y0 + PAD_Y - m, R.x1 - PAD_X + m, R.y1 - PAD_Y + m, c.id, 0);
      if (code < 0) continue;                                     // beside it means on no other land at all
      // touching its own state (the part its anchor is in): it needs no leader
      let touch = ((code >> 8) & 255) >= 2;
      if (touch && g > L.reach + 3) continue;                     // that is some far part of it (Svalbard for Norway)
      if (touching && !touch) continue;
      if (!(code & (CONFIRMED | UNTOUCHED))) {
        if (this._confirm(R, c, touch)) code = L.code[slot] = code | CONFIRMED;
        else if (touch && this._confirm(R, c, false)) code = L.code[slot] = code | UNTOUCHED;     // clear water, but it does not quite reach
        else { L.code[slot] = -1; continue; }
      }
      if (code & UNTOUCHED) touch = false;
      if (touch) { this._place(it, v, R, code & 1 ? 'in' : 'coast', null, L); return true; }
      if (touching) continue;
      // how far is its own ground, on the way from the text to the anchor?
      const tx0 = R.x0 + PAD_X, tx1 = R.x1 - PAD_X, ty0 = R.y0 + PAD_Y, ty1 = R.y1 - PAD_Y;
      const sx = Math.max(tx0 - 1, Math.min(tx1 + 1, L.ax)), sy = Math.max(ty0 - 1.5, Math.min(ty1 + 1.5, L.ay));
      const len = Math.hypot(L.ax - sx, L.ay - sy);
      if (len < 1) continue;
      const dx = (L.ax - sx) / len, dy = (L.ay - sy) / len;
      // d0: where its own ground begins for good - a run of it as long as the leader goes in (a thin neck or an
      // islet on the way does not count, or the line could end beyond it on another state)
      const inset = Math.max(2.5, m);
      let d0 = -1, over = 0;
      for (let t = 0; t < len; t += 1.5) {
        const o = this._owner(sx + dx * t, sy + dy * t);
        if (o === c.id) { if (d0 < 0) d0 = t; if (t - d0 >= inset) break; } else { d0 = -1; if (o) over += 1.5; }
      }
      if (d0 >= 0 && len - d0 > L.reach + 3) continue;            // the leader would end on a far part of it
      // a leader, to just inside the state (or to the anchor of one too small for the raster to see)
      let end = d0 < 0 ? len : Math.min(len, d0 + inset);
      if (end > LEADER_MAX || over > LEADER_OVER_OTHERS) continue;
      if (over > overMax) { this._crossers++; continue; }       // a candidate for the second pass
      if (d0 >= 0 && this._exact && end < len) {               // the raster is coarser than a pixel here: confirm on the polygon
        let ok = false;
        for (; end < len; end += 2) { if (this._inv(sx + dx * end, sy + dy * end) && this.geo.inside(c, this._lo, this._la)) { ok = true; break; } }
        if (!ok) end = len;
        if (end > LEADER_MAX) continue;
      }
      const ex = sx + dx * end, ey = sy + dy * end;
      const seg = [sx, sy, ex, ey];
      if (!this._segFree(seg, it._i) || !this._segClear(seg, R)) continue;
      this._place(it, v, R, 'lead', seg, L);
      return true;
    }
    return false;
  }

  _place(it, v, R, kind, seg, L) {
    const cx = (R.x0 + R.x1) / 2, top = R.y0 + PAD_Y, lines = [];
    for (let i = 0; i < v.lines.length; i++) lines.push({ t: v.lines[i], x: cx - v.ws[i] / 2, y: top + v.cap + i * v.pitch });
    this._take(R.x0, R.y0, R.x1, R.y1, it._i, 0);
    if (seg) { this._segs.push(seg); this._take(seg[2] - 2.5, seg[3] - 2.5, seg[2] + 2.5, seg[3] + 2.5, it._i, 0); }   // the dot at its end
    it._done = this._frame;
    this.placed.push({ x0: R.x0, y0: R.y0, x1: R.x1, y1: R.y1, it, px: seg ? seg[2] : cx, py: seg ? seg[3] : (R.y0 + R.y1) / 2, kind, abbr: v.abbr, size: v.size, font: v.font, spacing: v.spacing, base: 'alphabetic', lines, leader: seg, st: null });
  }

  /** One position, as before: centred on its point, or right of its dot. */
  _legacy(it, k, atlas) {
    const p = this.cam.project(it.lon, it.lat);
    if (!p || !this._onScreen(p[0], p[1], 40, 20)) return;
    const st = STYLES[it.cls](it, k, atlas), text = st.upper ? it.text.toUpperCase() : it.text, spacing = parseFloat(st.spacing || '0');
    const tw = this._width(text, st.font, spacing), th = st.size * 1.15;
    let x = p[0];
    const y = p[1];
    if (st.dot) x += st.dot + 4; else x -= tw / 2;
    const x0 = st.dot ? p[0] - st.dot - 1.5 : x - 3, y0 = y - th / 2 - 1, x1 = x + tw + 3, y1 = y + th / 2 + 1;
    // where it will be at the real scale (it holds on to its point, see _carry): clear of everything taken,
    // and in a sub-view wholly inside the frame (a name cut by an inset's rule reads as a mistake)
    const z = this._z, cdx = (p[0] - this.w / 2) * (z - 1), cdy = (p[1] - this.h / 2) * (z - 1);
    if (!this._clear(x0 + cdx, y0 + cdy, x1 + cdx, y1 + cdy)) return;
    if (this.sub && (x0 + cdx < 1 || y0 + cdy < 1 || x1 + cdx > this.w - 1 || y1 + cdy > this.h - 1)) return;
    if (!this._free(x0, y0, x1, y1, -1)) return;
    this._take(x0, y0, x1, y1, -1, 0);
    this.placed.push({ x0, y0, x1, y1, it, px: p[0], py: p[1], kind: 'point', abbr: false, size: st.size, font: st.font, spacing, base: 'middle', lines: [{ t: text, x, y }], leader: null, st });
    return true;
  }

  draw(view, style, show) {
    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, this.ox * this.dpr, this.oy * this.dpr);
    ctx.clearRect(0, 0, this.w, this.h);
    if (!show) { this.placed = []; this._sig = null; return; }
    const atlas = style === 'atlas', sheet = view.view === 'sheet';
    // ON THE SHEET the layout is solved at the next coarser step of a 5% scale ladder and then carried to the real
    // scale: every name keeps its place on the ground and only spreads apart, so nothing can come to overlap, and
    // a continuous zoom re-lays the names once per step, not once per frame (names would otherwise swap places
    // every frame as the fit of each changed by a hair).
    let cam = view, z = 1, step = 0;
    if (sheet) {
      step = Math.ceil(Math.log(view.kmPerPx()) / Math.log(ZOOM_STEP) - 1e-9);
      z = Math.pow(ZOOM_STEP, step) / view.kmPerPx();
      cam = Object.create(view); cam.mapUnitsPerPx = view.mapUnitsPerPx * z;
    }
    const k = view.kmPerPx();                 // what shows at which zoom goes by the real scale
    // nothing moved: repaint what was solved (the clock redraws this layer every tick)
    const key = sheet ? `s|${step}|${style}|${this.w}|${this.h}|${this._gen}` : `g|${cam.lon}|${cam.lat}|${cam.dist}|${cam.tanHalfFov}|${style}|${this.w}|${this.h}|${this._gen}`;
    const sig = (sheet ? `${key}|${view.mapUnitsPerPx}|${cam.mapCenter[0]}|${cam.mapCenter[1]}` : key) + '|' + this._bsig;
    if (sig === this._sig) { this._paint(atlas); return; }
    this._sig = sig;
    // a drag only translates the sheet, and a zoom within a step only spreads it: what lies under each candidate is kept
    if (key !== this._key) { this._key = key; this._epoch++; }
    this.cam = cam; this._sheet = sheet; this._z = z; this._frame = (this._frame || 0) + 1;
    this.placed = [];
    this._rc = this._rc || { x0: 0, y0: 0, x1: 0, y1: 0 };
    this._hashInit();
    cam.beginFrame();
    this._b = cam._b;
    if (!sheet) { const t = cam.tanHalfFov; this._g = [(2 * t) / this.h, t * (this.w / this.h), t, (2 * t) / this.h, cam.dist * cam.dist - 1]; }
    if (sheet) {
      if (!LUT) LUT = wtTable();
      const u = cam.mapUnitsPerPx, sx = LUT_W / (2 * WT_XMAX), sy = LUT_H / (2 * WT_YMAX);
      this._fa = u * sx; this._fb = (cam.mapCenter[0] - (this.w / 2) * u + WT_XMAX) * sx;
      this._fc = -u * sy; this._fd = (cam.mapCenter[1] + (this.h / 2) * u + WT_YMAX) * sy;
    }
    const names = new Set();                     // a name is not printed twice (AUSTRALIA the continent and the state)
    const spreads = [];                          // continents: set last, across whatever is there
    const legacy = (it) => {
      if (k < (it.minKm || 0)) return;
      if (it.cls === 'continent') { if (k <= it.maxKm) spreads.push(it); return; }
      const twin = it.cls === 'country' ? it.text.toUpperCase() : null;
      if (twin && names.has(twin)) return;
      if (k > it.maxKm) {
        // a dependency shows before its rank's zoom once its full name fits inside it
        if (!(it.roomy && this.geo && this._roomy(it, atlas))) return;
      } else if (!this._legacy(it, k, atlas)) return;
      if (twin) names.add(twin);
    };
    for (const it of this.before) legacy(it);

    if (this.states.length && k >= 0.7) {
      const cellPx = (this.geo.cell * R_KM * D2R) / cam.kmPerPx();
      this._margin = Math.max(1, 0.75 * cellPx);                  // keep a name in water clear of other land by the raster's own error
      this._exact = cellPx > 1; this._cellPx = cellPx;
      const live = [];
      for (const it of this.states) {
        const L = this._prep(it);
        if (!L.on) continue;
        let seen = this._onScreen(L.ax, L.ay, 0, 0);
        L.anchor = seen;
        for (let i = 0; i < NP && !seen; i++) if (L.ok[i]) seen = this._onScreen(L.ax + L.ox[i], L.ay + L.oy[i], 0, 0);
        if (!seen) continue;
        this._variants(it, L.S, atlas);
        live.push(it);
        // a state too small to see, on the water, is only its anchor: no other state's name may sit on it
        if (L.anchor && L.tiny && L.sea < 2.5) this._take(L.ax - 1.5, L.ay - 1.5, L.ax + 1.5, L.ay + 1.5, it._i, 1);
      }
      const fr = this._frame, IN = [0, 1, 2, 3, 4, 5];
      // A1: the full name inside
      for (const it of live) { const L = it._L; for (const vi of IN) if (this._tryInside(it, L, vi)) break; }
      // A2: full name touching; abbreviation inside; abbreviation touching
      for (const it of live) {
        if (it._done === fr) continue;
        const L = it._L, near = L.anchor && L.flat > 0.35;
        let done = false;
        if (near) for (let ri = 0; ri < RINGS.length && !done; ri++) done = this._tryBeside(it, L, 6, ri, true) || this._tryBeside(it, L, 7, ri, true);
        if (!done) done = this._tryInside(it, L, 8) || this._tryInside(it, L, 9);
        if (!done && near) for (let ri = 0; ri < RINGS.length && !done; ri++) done = this._tryBeside(it, L, 9, ri, true);
      }
      // B: open water and a leader - first one that crosses no other state, then one that may cross a little
      const tryB = (it, ri, over) => {
        const L = it._L, reach = RINGS[ri] + 6;
        for (const vi of [6, 7, 9]) {
          const v = it._v[vi];
          if (!v || reach + v.w + v.h < L.sea) continue;          // no water that near
          if (this._tryBeside(it, L, vi, ri, false, over)) return true;
        }
        return false;
      };
      for (const it of live) {
        if (it._done === fr || !it._L.anchor || it._L.flat <= 0.35) continue;      // not on the limb of the globe
        let done = false;
        this._crossers = 0;
        for (let ri = 0; ri < RINGS.length && !done; ri++) done = tryB(it, ri, 0);
        if (this._crossers) for (let ri = 0; ri < RINGS.length && !done; ri++) done = tryB(it, ri, LEADER_OVER_OTHERS);
      }
      for (const r of this._R) if (r.kind === 1) r.dead = true;
      for (const p of this.placed) if (p.it.cls === 'country') names.add(p.it.text.toUpperCase());
    }

    for (const it of this.after) legacy(it);
    for (const it of spreads) if (!names.has(it.text.toUpperCase()) && this.geo) this._spread(it, atlas);
    if (z !== 1) this._carry(z);
    this._paint(atlas);
  }

  /** A continent's name, wall-map fashion: capitals set far apart on one line or two, across the continent, each
   *  letter in a place of its own. Every setting is looked at (how wide, which row, how far along it) in which each
   *  letter is in the window, on nothing taken, clear of every name and leader already placed, and on no other
   *  continent's land; the one kept is the widest that stays near the continent's own anchor (see the score).
   *  It takes nothing from anybody: it comes last. */
  _spread(it, atlas) {
    const cam = this.cam, A = cam.project(it.lon, it.lat);
    if (!A) return false;
    const cl = Math.max(0.05, Math.cos(it.lat * D2R)), e = cam.project(it.lon + 1 / cl, it.lat);
    if (!e) return false;
    const Wc = ((it.ref && it.ref[1] && it.ref[1].size) || 30) * Math.hypot(e[0] - A[0], e[1] - A[1]);      // the continent's breadth on screen, px (the source's own size, degrees)
    if (Wc < 60) return false;
    const size = Math.max(SPREAD_MIN, Math.min(SPREAD_MAX, Math.round(Wc / 14))), font = `600 ${size}px ${SANS}`, cap = this._capHeight(font, size);
    const text = it.text.toUpperCase(), sp = text.indexOf(' '), own = SPREAD_ALIAS[it.text] || it.text;
    const st = { color: atlas ? 'rgba(60,50,74,.62)' : 'rgba(255,255,255,.5)', halo: 2, haloColor: atlas ? 'rgba(255,255,255,.4)' : 'rgba(0,6,16,.3)' };
    // one line; or two, at each of a few line spacings (a narrow continent has few clear rows)
    const settings = [[[text], 0]];
    if (sp > 0) for (const g of SPREAD_GAPS) settings.push([[text.slice(0, sp), text.slice(sp + 1)], g * size]);
    const R = this._rc;
    let G = [], best = null, bs = -Infinity;
    for (const [lines, gap] of settings) {
      const nmax = Math.max(...lines.map((l) => l.length)), n = lines.reduce((a, l) => a + l.replace(/ /g, '').length, 0);
      const y0 = -((lines.length - 1) * gap) / 2 + cap / 2, cost = lines.length > 1 ? 0.12 + 0.05 * (gap / size - SPREAD_GAPS[0]) : 0;
      let last = 0;
      for (const f of SPREAD_FILL) {
        const pitch = Math.min(SPREAD_LOOSE * size, (f * Wc) / (nmax - 1));
        if (pitch < SPREAD_TIGHT * size) break;                    // closer than this it is ordinary type
        if (pitch === last) continue;
        last = pitch;
        const wide = (pitch * (nmax - 1)) / Wc;
        const ny = Math.floor((SPREAD_UP * Wc) / (SPREAD_ROW * size)), nx = Math.floor((SPREAD_ALONG * Wc) / (SPREAD_SHIFT * pitch));
        for (let iy = 0; iy <= 2 * ny; iy++) {                    // 0, -1, +1, -2, +2 ...: nearest the anchor first
          const dy = (iy & 1 ? -(iy + 1) / 2 : iy / 2) * SPREAD_ROW * size;
          for (let ix = 0; ix <= 2 * nx; ix++) {
            const dx = (ix & 1 ? -(ix + 1) / 2 : ix / 2) * SPREAD_SHIFT * pitch;
            // the score: breadth of the setting, less how far it has strayed from the anchor, plus the share of it on its own land
            const reach = wide - cost - (SPREAD_STRAY_Y * Math.abs(dy) + SPREAD_STRAY_X * Math.abs(dx)) / Wc;
            if (reach + SPREAD_OWN <= bs) continue;                 // cannot beat the best so far
            G.length = 0;
            let ok = true, onOwn = 0;
            for (let li = 0; li < lines.length && ok; li++) {
              const l = lines[li], base = A[1] + dy + y0 + li * gap;
              for (let j = 0; j < l.length; j++) {
                if (l[j] === ' ') continue;
                const w = this._width(l[j], font, 0), cx = A[0] + dx + (j - (l.length - 1) / 2) * pitch;
                R.x0 = cx - w / 2 - SPREAD_PAD; R.x1 = cx + w / 2 + SPREAD_PAD; R.y0 = base - cap - SPREAD_PAD; R.y1 = base + SPREAD_PAD;
                if (!this._visible(R) || !this._free(R.x0, R.y0, R.x1, R.y1, -1)) { ok = false; break; }
                const o = this._owner(cx, base - cap / 2);
                if (o < 0) { ok = false; break; }                   // off the Earth
                if (o) { if (this._cont.get(o) === own) onOwn++; else { ok = false; break; } }   // on another continent
                G.push({ t: l[j], x0: R.x0, y0: R.y0, x1: R.x1, y1: R.y1, x: cx - w / 2, y: base });
              }
            }
            if (!ok || onOwn < SPREAD_ON_OWN * n) continue;
            const score = reach + (SPREAD_OWN * onOwn) / n;
            if (score > bs) { bs = score; best = G; G = []; }
          }
        }
      }
    }
    if (!best) return false;
    for (const g of best) {
      this._take(g.x0, g.y0, g.x1, g.y1, -1, 0);
      this.placed.push({ x0: g.x0, y0: g.y0, x1: g.x1, y1: g.y1, it, px: (g.x0 + g.x1) / 2, py: (g.y0 + g.y1) / 2, kind: 'spread', abbr: false, size, font, spacing: 0, base: 'alphabetic', lines: [{ t: g.t, x: g.x, y: g.y }], leader: null, st });
    }
    return true;
  }

  /** Carry a layout solved at a coarser scale to the real one: each name moves with the ground under it (out from the
   *  window's centre by z >= 1) and keeps its size. Rectangles apart before are apart after. A leader is redrawn from
   *  its name to the same ground; in the rare case that it now touches another name or leader, that name is dropped. */
  _carry(z) {
    const w2 = this.w / 2, h2 = this.h / 2, P = this.placed;
    for (const p of P) {
      // a point label holds on to its point; a name on its state, to its own centre
      const fx = p.kind === 'point' ? p.px : (p.x0 + p.x1) / 2, fy = p.kind === 'point' ? p.py : (p.y0 + p.y1) / 2;
      const dx = (fx - w2) * (z - 1), dy = (fy - h2) * (z - 1);
      p.x0 += dx; p.x1 += dx; p.y0 += dy; p.y1 += dy;
      for (const l of p.lines) { l.x += dx; l.y += dy; }
      if (p.leader) {
        const ex = w2 + (p.leader[2] - w2) * z, ey = h2 + (p.leader[3] - h2) * z;
        p.leader = [Math.max(p.x0 + PAD_X - 1, Math.min(p.x1 - PAD_X + 1, ex)), Math.max(p.y0 + PAD_Y - 1.5, Math.min(p.y1 - PAD_Y + 1.5, ey)), ex, ey];
        p.px = ex; p.py = ey;
      } else { p.px += dx; p.py += dy; }
    }
    let drop = null, dropIt = null;
    for (let i = 0; i < P.length; i++) {
      const s = P[i].leader;
      if (!s) continue;
      for (let j = 0; j < P.length; j++) {
        const q = P[j];
        if (j === i || (drop && drop.has(q))) continue;
        if (q.kind === 'spread') {                               // a continent's letter gives way, and its whole name with it
          if (segHitsRect(s[0], s[1], s[2], s[3], q.x0, q.y0, q.x1, q.y1)) (dropIt = dropIt || new Set()).add(q.it);
          continue;
        }
        if (segHitsRect(s[0], s[1], s[2], s[3], q.x0 + 1, q.y0 + 1, q.x1 - 1, q.y1 - 1) || (j < i && q.leader && segsCross(q.leader, s))) { (drop = drop || new Set()).add(P[i]); break; }
      }
    }
    if (drop || dropIt) this.placed = P.filter((p) => !(drop && drop.has(p)) && !(dropIt && p.kind === 'spread' && dropIt.has(p.it)));
  }

  /** A dependency's full name inside it (one line, its own style), where it fits. */
  _roomy(it, atlas) {
    const c = it.ref[1], p = this.cam.project(c.lp[0], c.lp[1]);
    if (!p) return false;
    const size = 10, font = `${atlas ? 600 : 500} ${size}px ${SANS}`, spacing = 0.8, text = it.text.toUpperCase();
    const w = this._width(text, font, spacing), cap = this._capHeight(font, size);
    for (const q of [c.lp, [it.lon, it.lat]]) {
      const P = q === c.lp ? p : this.cam.project(q[0], q[1]);
      if (!P) continue;
      const x0 = P[0] - w / 2, y0 = P[1] - cap / 2, x1 = x0 + w, y1 = y0 + cap;
      const R = this._rc; R.x0 = x0 - PAD_X; R.y0 = y0 - PAD_Y; R.x1 = x1 + PAD_X; R.y1 = y1 + PAD_Y;
      if (!this._visible(R) || !this._free(R.x0, R.y0, R.x1, R.y1, -1)) continue;
      const code = this._scan(x0, y0, x1, y1, c.id, 0.1);
      if (code < 0 || !(code & 1) || ((code >> 8) & 255) < 0.6 * (code >> 16)) continue;
      this._take(x0 - PAD_X, y0 - PAD_Y, x1 + PAD_X, y1 + PAD_Y, -1, 0);
      this.placed.push({ x0: x0 - PAD_X, y0: y0 - PAD_Y, x1: x1 + PAD_X, y1: y1 + PAD_Y, it, px: P[0], py: P[1], kind: 'in', abbr: false, size, font, spacing, base: 'alphabetic', lines: [{ t: text, x: x0, y: y1 }], leader: null, st: null });
      return true;
    }
    return false;
  }

  _paint(atlas) {
    const ctx = this.ctx, ls = 'letterSpacing' in ctx;
    ctx.save();
    if (this.sub) { ctx.beginPath(); ctx.rect(0, 0, this.w, this.h); ctx.clip(); }
    ctx.globalAlpha = this.alpha;
    if (this.underlay) this.underlay(ctx, atlas);
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    const ink = atlas ? 'rgba(28,26,30,.92)' : 'rgba(255,255,255,.88)', hal = halo(atlas);
    // the continents' letters lie under everything else
    if (ls) ctx.letterSpacing = '0px';
    for (const p of this.placed) {
      if (p.kind !== 'spread') continue;
      ctx.font = p.font; ctx.textBaseline = p.base;
      ctx.lineWidth = p.st.halo; ctx.strokeStyle = p.st.haloColor; ctx.fillStyle = p.st.color;
      for (const l of p.lines) { ctx.strokeText(l.t, l.x, l.y); ctx.fillText(l.t, l.x, l.y); }
    }
    // leaders and dots under the type
    for (const p of this.placed) {
      if (p.leader) {
        const s = p.leader;
        ctx.beginPath(); ctx.moveTo(s[0], s[1]); ctx.lineTo(s[2], s[3]);
        ctx.lineWidth = 2.6; ctx.strokeStyle = hal; ctx.stroke();
        ctx.lineWidth = 0.9; ctx.strokeStyle = ink; ctx.stroke();
        ctx.beginPath(); ctx.arc(s[2], s[3], 1.7, 0, 6.2832); ctx.fillStyle = ink; ctx.fill();
      } else if (p.st && p.st.dot) {
        const st = p.st;
        ctx.beginPath(); ctx.arc(p.px, p.py, st.dot, 0, 6.2832);
        ctx.fillStyle = atlas ? '#fff' : 'rgba(255,255,255,.92)'; ctx.fill();
        ctx.lineWidth = 1.2; ctx.strokeStyle = atlas ? '#2a2a2a' : 'rgba(0,0,0,.75)'; ctx.stroke();
        if (st.capital) { ctx.beginPath(); ctx.arc(p.px, p.py, st.dot * 0.42, 0, 6.2832); ctx.fillStyle = atlas ? '#2a2a2a' : 'rgba(0,0,0,.85)'; ctx.fill(); }
      }
    }
    // every halo, then every glyph: a halo never eats a neighbour's letters
    for (let pass = 0; pass < 2; pass++) {
      for (const p of this.placed) {
        if (p.kind === 'spread') continue;
        ctx.font = p.font; ctx.textBaseline = p.base;
        if (ls) ctx.letterSpacing = p.spacing + 'px';
        if (pass === 0) { ctx.lineWidth = p.st ? p.st.halo : p.size < 10 ? 2.2 : 2.6; ctx.strokeStyle = p.st ? p.st.haloColor : hal; for (const l of p.lines) ctx.strokeText(l.t, l.x, l.y); }
        else { ctx.fillStyle = p.st ? p.st.color : ink; for (const l of p.lines) ctx.fillText(l.t, l.x, l.y); }
      }
    }
    if (ls) ctx.letterSpacing = '0px';
    ctx.restore();
  }

  /** The label under a screen point, if any: its name first, then its leader line, then anything within reach of it. */
  hit(x, y) {
    const P = this.placed;
    for (let i = P.length - 1; i >= 0; i--) { const p = P[i]; if (x >= p.x0 && x <= p.x1 && y >= p.y0 && y <= p.y1) return p.it; }
    for (let i = P.length - 1; i >= 0; i--) { const s = P[i].leader; if (s && segHitsRect(s[0], s[1], s[2], s[3], x - 2.5, y - 2.5, x + 2.5, y + 2.5)) return P[i].it; }
    let best = null, bd = 7;
    for (let i = P.length - 1; i >= 0; i--) {
      const p = P[i];
      if (x >= p.x0 - 2 && x <= p.x1 + 2 && y >= p.y0 - 3 && y <= p.y1 + 3) return p.it;
      const d = Math.hypot(x - p.px, y - p.py);
      if (d < bd) { bd = d; best = p.it; }
    }
    return best;
  }
}

const halo = (atlas) => (atlas ? 'rgba(255,255,255,.85)' : 'rgba(0,6,16,.72)');
const STYLES = {
  ocean: (it, k, a) => ({ font: `italic 400 ${it.rank <= 0 ? 17 : it.rank <= 2 ? 13.5 : 12}px ${SERIF}`, size: 15, upper: it.rank <= 0, spacing: it.rank <= 0 ? '5px' : '1.5px', color: a ? 'rgba(24,74,128,.9)' : 'rgba(150,195,235,.85)', halo: 2.5, haloColor: a ? 'rgba(255,255,255,.55)' : 'rgba(0,10,24,.6)' }),
  country: (it, k, a) => { const s = it.rank <= 2 ? 12 : it.rank <= 3 ? 11 : it.rank <= 4 ? 10.5 : 10; return { font: `${a ? 600 : 500} ${s}px ${SANS}`, size: s, upper: true, spacing: '1.8px', color: a ? 'rgba(28,26,30,.92)' : 'rgba(255,255,255,.88)', halo: 2.6, haloColor: halo(a) }; },
  city: (it, k, a) => { const big = it.pop > 5e6, s = big ? 12.5 : it.pop > 1e6 ? 11.5 : 10.5; return { font: `${it.capital ? 600 : 400} ${s}px ${SANS}`, size: s, dot: big ? 3.2 : 2.5, capital: it.capital, color: a ? 'rgba(20,20,24,.95)' : 'rgba(255,255,255,.95)', halo: 2.8, haloColor: halo(a) }; },
  feature: (it, k, a) => ({ font: `italic 400 ${it.rank <= 2 ? 12.5 : 11.5}px ${SERIF}`, size: 12, spacing: '1px', color: a ? 'rgba(84,58,30,.9)' : 'rgba(235,222,196,.85)', halo: 2.5, haloColor: halo(a) }),
  peak: (it, k, a) => ({ font: `italic 400 10.5px ${SERIF}`, size: 10.5, dot: 1.8, color: a ? 'rgba(84,58,30,.95)' : 'rgba(240,228,205,.9)', halo: 2.5, haloColor: halo(a) }),
  mark: (it, k, a) => ({ font: `600 11px ${SANS}`, size: 11, dot: 0, spacing: '1px', color: it.color || '#ffd66b', halo: 3, haloColor: 'rgba(0,6,16,.8)' }),
};
