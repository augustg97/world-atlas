// Things that move: tracers in the wind, the jet stream and the ocean currents (advected through
// the same climatological fields the shader reads), tracers along the measured shipping lanes,
// and MODELLED aircraft on great circles. All are drawn as short streaks in geographic
// coordinates, so they survive any camera move.

import { LineBatch } from './overlays.js?v=20261110T175726Z';
import { D2R, R2D } from './astro.js?v=20261110T175726Z';

const S = LineBatch.STRIDE;

// One random source for everything that moves, so a frozen frame (main.js, ?frozen=1) can be
// reproduced exactly: seedRandom(n) swaps Math.random for a seeded generator (mulberry32).
let rnd = Math.random;
export function seedRandom(seed) {
  let a = seed >>> 0;
  rnd = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

/** Tracers advected through a vector field sampled by `sample(lon, lat, out)` -> false where there is no data. */
export class FlowTracers {
  constructor(gl, prog, n, trail, opts) {
    this.n = n; this.trail = trail; this.o = opts;
    this.lon = new Float32Array(n * trail); this.lat = new Float32Array(n * trail);
    this.age = new Float32Array(n); this.life = new Float32Array(n); this.speed = new Float32Array(n);
    this.head = 0; this.fresh = new Uint8Array(n).fill(1); this.dir = new Float32Array(n * 2);
    this.batch = new LineBatch(gl, prog, true);
    this.data = new Float32Array(n * (trail - 1) * S);
    this.v = [0, 0];
    this.spawned = false;
  }

  _spawn(i, cam) {
    // uniform over the SCREEN, so tracer density is the same at every zoom
    let ll = null;
    for (let k = 0; k < (this.o.tries || 6); k++) {
      ll = cam.unproject(rnd() * cam.w, rnd() * cam.h);
      if (ll && (!this.o.accept || this.o.accept(ll[0], ll[1]))) break;
      ll = null;
    }
    if (!ll) { this.age[i] = 1e9; return; }
    for (let t = 0; t < this.trail; t++) { this.lon[i * this.trail + t] = ll[0]; this.lat[i * this.trail + t] = ll[1]; }
    this.age[i] = 0; this.life[i] = this.o.life * (0.5 + rnd());
    this.fresh[i] = 1; this.dir[i * 2] = 0; this.dir[i * 2 + 1] = 0;
  }

  /** Advance one visual step. `kmPerPx` sets the stride so motion reads the same at any zoom. */
  step(cam, sample, dtFrames = 1) {
    const T = this.trail, h = this.head, nh = (h + 1) % T, v = this.v;
    const stepDeg = this.o.pxPerUnit * cam.kmPerPx() / 111.2 * dtFrames;     // degrees of arc per (unit of speed) per frame
    for (let i = 0; i < this.n; i++) {
      if (this.age[i] >= this.life[i]) { this._spawn(i, cam); continue; }
      const lon = this.lon[i * T + h], lat = this.lat[i * T + h];
      if (!sample(lon, lat, v, this.dir, i) || Math.abs(lat) > 88.5) { this.age[i] = 1e9; continue; }
      const sp = Math.hypot(v[0], v[1]);
      this.speed[i] = sp;
      const cl = Math.max(0.05, Math.cos(lat * D2R));
      let nl = lon + v[0] * stepDeg / cl, na = lat + v[1] * stepDeg;
      if (nl > 180) nl -= 360; else if (nl < -180) nl += 360;
      this.lon[i * T + nh] = nl; this.lat[i * T + nh] = na;
      this.age[i] += dtFrames; this.fresh[i] = Math.min(255, this.fresh[i] + 1);
    }
    this.head = nh;
  }

  draw(camU, alpha) {
    const T = this.trail, d = this.data, o = this.o;
    let c = 0;
    for (let i = 0; i < this.n; i++) {
      if (this.age[i] >= this.life[i]) continue;
      const have = Math.min(T - 1, this.fresh[i] - 1);
      const fade = Math.min(1, this.age[i] / 8) * Math.min(1, (this.life[i] - this.age[i]) / 8);
      const s = Math.min(1, this.speed[i] / o.vmax);
      const col = o.color(s);
      for (let t = 0; t < have; t++) {
        const a = (this.head - t + T) % T, b = (this.head - t - 1 + T) % T;
        const la = this.lon[i * T + a], lb = this.lon[i * T + b];
        if (Math.abs(la - lb) > 90) continue;
        const k = c * S;
        d[k] = la * D2R; d[k + 1] = this.lat[i * T + a] * D2R; d[k + 2] = lb * D2R; d[k + 3] = this.lat[i * T + b] * D2R;
        d[k + 4] = col[0]; d[k + 5] = col[1]; d[k + 6] = col[2]; d[k + 7] = col[3] * fade * (1 - t / (T - 1)) ** 1.3;
        d[k + 8] = o.width; d[k + 9] = 0; d[k + 10] = 0;
        c++;
      }
    }
    this.batch.set(d, c);
    this.batch.draw(camU, { alpha, height: o.height || 0 });
    return c;
  }
}

/** MODELLED aircraft: a pure function of the clock. Each route carries planes in proportion to
 *  its modelled flow; a plane exists only if its departure fell in the origin's waking hours. */
export class Flights {
  constructor(gl, prog, air) {
    this.air = air; this.batch = new LineBatch(gl, prog, true);
    const routes = air.routes, ap = air.airports;
    this.planes = [];
    let seed = 1;
    const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    for (const [a, b, flow, km] of routes) {
      const n = Math.max(1, Math.round(Math.pow(flow, 0.55) * 26 * Math.min(1.6, 0.35 + km / 4000)));
      for (let j = 0; j < n; j++) {
        const fwd = j % 2 === 0;
        const A = ap[fwd ? a : b], B = ap[fwd ? b : a];
        const ua = unit(A), ub = unit(B);
        const om = Math.acos(Math.max(-1, Math.min(1, ua[0] * ub[0] + ua[1] * ub[1] + ua[2] * ub[2])));
        this.planes.push({ A, B, km, a: ua, b: ub, om, so: Math.sin(om) || 1e-9, dur: km / 840 + 0.6, phase: rnd(), gate: rnd() });   // hours in the air, incl. climb and descent
      }
    }
    this.data = new Float32Array(this.planes.length * S * 2);
    this.aloft = 0;
  }
  /** Fraction of a day's departures happening at this local hour (peaks morning and evening, near zero at night). */
  static load(h) {
    const g = (m, s) => Math.exp(-((h - m) ** 2) / (2 * s * s));
    return Math.min(1, 0.05 + 0.95 * (g(8, 2.2) + 0.85 * g(13, 3) + g(18.5, 2.6)) / 1.25);
  }
  draw(camU, tMs, sunNow, alpha, kmPerPx) {
    const d = this.data, hours = tMs / 3600000;
    let c = 0, aloft = 0;
    const streakKm = kmPerPx * 9;                                   // a streak is about nine pixels long at any zoom
    for (const p of this.planes) {
      const cyc = hours / (p.dur * 2.4) + p.phase;                 // each airframe: fly, turn round, fly back
      const s = (cyc - Math.floor(cyc)) * 2.4;
      if (s > 1) continue;                                          // on the ground
      const dep = hours - s * p.dur;
      const depLst = (((12 + (p.A.lon - sunNow.lon) / 15 - (hours - dep)) % 24) + 24) % 24;
      if (p.gate > Flights.load(depLst)) continue;                  // this rotation did not operate: it would have left at night
      aloft++;
      const s0 = Math.max(0, s - Math.min(0.4, streakKm / p.km));
      const h1 = gcAt(p, s), h0 = gcAt(p, s0);
      if (Math.abs(h1[0] - h0[0]) > 90) continue;
      const k = c * S;
      d[k] = h0[0] * D2R; d[k + 1] = h0[1] * D2R; d[k + 2] = h1[0] * D2R; d[k + 3] = h1[1] * D2R;
      d[k + 4] = 1.0; d[k + 5] = 0.93; d[k + 6] = 0.72; d[k + 7] = 0.7;
      d[k + 8] = 1.0; d[k + 9] = 0; d[k + 10] = 0;
      c++;
    }
    this.aloft = aloft;
    this.batch.set(d, c);
    this.batch.draw(camU, { alpha, height: 0.0017 });               // ~11 km cruise
    return aloft;
  }
}
const unit = (P) => [Math.cos(P.lat * D2R) * Math.cos(P.lon * D2R), Math.cos(P.lat * D2R) * Math.sin(P.lon * D2R), Math.sin(P.lat * D2R)];
/** A point a fraction t along a plane's great circle. */
function gcAt(p, t) {
  const a = p.a, b = p.b, om = p.om, so = p.so;
  const s0 = Math.sin((1 - t) * om) / so, s1 = Math.sin(t * om) / so;
  const x = a[0] * s0 + b[0] * s1, y = a[1] * s0 + b[1] * s1, z = a[2] * s0 + b[2] * s1;
  return [Math.atan2(y, x) * R2D, Math.asin(Math.max(-1, Math.min(1, z))) * R2D];
}

// ------------------------------------- field samplers ---------------------------------------
export function makeSamplers(fields, getMonth) {
  const vec = (u, v) => (lon, lat, out) => {
    const ms = getMonth();
    const a = fields.climate(u, lon, lat, ms);
    if (Number.isNaN(a)) return false;
    out[0] = a; out[1] = fields.climate(v, lon, lat, ms);
    return true;
  };
  // lanes.png: R,G = cos/sin of twice the lane bearing x coherence; B = ridge strength (build/fields_human.py::step_lanes)
  const laneAt = (lon, lat) => {
    const f = fields.cpu.lanes; if (!f) return -1;
    const x = Math.min(f.w - 1, Math.max(0, Math.floor(((lon + 180) / 360) * f.w))), y = Math.min(f.h - 1, Math.max(0, Math.floor(((90 - lat) / 180) * f.h)));
    return (y * f.w + x) * 4;
  };
  const lanes = (lon, lat, out, dir, i) => {
    const k = laneAt(lon, lat); if (k < 0) return false;
    const d = fields.cpu.lanes.d;
    if (d[k + 2] < 36) return false;                                  // off the ridge: this tracer ends here
    const c2 = d[k] / 127.5 - 1, s2 = d[k + 1] / 127.5 - 1;
    const th = 0.5 * Math.atan2(s2, c2);                              // lane orientation in image coordinates (y south)
    let ex = Math.cos(th), ny = -Math.sin(th);                        // east, north
    // a lane has no sign; each tracer keeps the heading it started with
    if (dir[i * 2] === 0 && dir[i * 2 + 1] === 0) { if (rnd() < 0.5) { ex = -ex; ny = -ny; } dir[i * 2] = ex; dir[i * 2 + 1] = ny; }
    else if (ex * dir[i * 2] + ny * dir[i * 2 + 1] < 0) { ex = -ex; ny = -ny; }
    // blend with the previous heading: lanes bend smoothly, tensor noise does not
    const bx = dir[i * 2] * 0.6 + ex * 0.4, by = dir[i * 2 + 1] * 0.6 + ny * 0.4, bl = Math.hypot(bx, by) || 1;
    dir[i * 2] = bx / bl; dir[i * 2 + 1] = by / bl;
    out[0] = dir[i * 2]; out[1] = dir[i * 2 + 1];
    return true;
  };
  const laneAccept = (lon, lat) => {
    const k = laneAt(lon, lat); if (k < 0) return false;
    const r = fields.cpu.lanes.d[k + 2] / 255;
    return r > 0.2 && rnd() < r * 1.3;                        // tracers start on ridges, more on stronger ones
  };
  return { wind: vec('u10', 'v10'), jet: vec('u250', 'v250'), currents: vec('ucur', 'vcur'), lanes, laneAccept };
}
