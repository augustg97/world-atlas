// Feature overlays that sit ON the rendered world: instanced lines and points (projected in
// the vertex shader by the same camera code as the substrate) and a 2D canvas for labels.

import { program, setUniforms } from './gl.js';
import { D2R } from './astro.js';
import { R_KM } from './camera.js';

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
const SERIF = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif';
const SANS = '-apple-system, "Helvetica Neue", "Segoe UI", system-ui, sans-serif';

export class Labels {
  constructor(canvas) { this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.items = []; this.placed = []; }
  resize(w, h, dpr) { this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr); this.w = w; this.h = h; this.dpr = dpr; }

  /** items: {text, lon, lat, cls, prio, minKm, maxKm, ref} - lower prio draws first and wins collisions. */
  setItems(items) { this.items = items.slice().sort((a, b) => a.prio - b.prio); }

  draw(cam, style, show) {
    const ctx = this.ctx, k = cam.kmPerPx();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.w, this.h);
    this.placed = [];
    if (!show) return;
    const atlas = style === 'atlas';
    const cell = 26, cols = Math.ceil(this.w / cell) + 1, rows = Math.ceil(this.h / cell) + 1;
    const occ = new Uint8Array(cols * rows);
    const free = (x0, y0, x1, y1) => {
      for (let cy = Math.max(0, Math.floor(y0 / cell)); cy <= Math.min(rows - 1, Math.floor(y1 / cell)); cy++)
        for (let cx = Math.max(0, Math.floor(x0 / cell)); cx <= Math.min(cols - 1, Math.floor(x1 / cell)); cx++) if (occ[cy * cols + cx]) return false;
      return true;
    };
    const take = (x0, y0, x1, y1) => {
      for (let cy = Math.max(0, Math.floor(y0 / cell)); cy <= Math.min(rows - 1, Math.floor(y1 / cell)); cy++)
        for (let cx = Math.max(0, Math.floor(x0 / cell)); cx <= Math.min(cols - 1, Math.floor(x1 / cell)); cx++) occ[cy * cols + cx] = 1;
    };
    cam.beginFrame();
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    for (const it of this.items) {
      if (k > it.maxKm || k < (it.minKm || 0)) continue;
      const p = cam.project(it.lon, it.lat);
      if (!p || p[0] < -40 || p[0] > this.w + 40 || p[1] < -20 || p[1] > this.h + 20) continue;
      const st = STYLES[it.cls](it, k, atlas);
      ctx.font = st.font;
      const text = st.upper ? it.text.toUpperCase() : it.text;
      if ('letterSpacing' in ctx) ctx.letterSpacing = st.spacing || '0px';
      const tw = ctx.measureText(text).width, th = st.size * 1.15;
      let x = p[0], y = p[1];
      if (st.dot) x += st.dot + 4; else x -= tw / 2;
      const x0 = x - 3, y0 = y - th / 2 - 1, x1 = x + tw + 3, y1 = y + th / 2 + 1;
      if (!free(x0, y0, x1, y1)) continue;
      take(x0, y0, x1, y1);
      if (st.dot) {
        ctx.beginPath(); ctx.arc(p[0], p[1], st.dot, 0, 6.2832);
        ctx.fillStyle = atlas ? '#fff' : 'rgba(255,255,255,.92)'; ctx.fill();
        ctx.lineWidth = 1.2; ctx.strokeStyle = atlas ? '#2a2a2a' : 'rgba(0,0,0,.75)'; ctx.stroke();
        if (st.capital) { ctx.beginPath(); ctx.arc(p[0], p[1], st.dot * 0.42, 0, 6.2832); ctx.fillStyle = atlas ? '#2a2a2a' : 'rgba(0,0,0,.85)'; ctx.fill(); }
      }
      ctx.lineWidth = st.halo;
      ctx.strokeStyle = st.haloColor; ctx.strokeText(text, x, y);
      ctx.fillStyle = st.color; ctx.fillText(text, x, y);
      this.placed.push({ x0, y0, x1, y1, it, px: p[0], py: p[1] });
    }
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
  }

  /** The label under a screen point, if any. */
  hit(x, y) {
    for (let i = this.placed.length - 1; i >= 0; i--) { const p = this.placed[i]; if (x >= p.x0 - 2 && x <= p.x1 + 2 && y >= p.y0 - 3 && y <= p.y1 + 3) return p.it; if (Math.hypot(x - p.px, y - p.py) < 7) return p.it; }
    return null;
  }
}

const halo = (atlas) => (atlas ? 'rgba(255,255,255,.85)' : 'rgba(0,6,16,.72)');
const STYLES = {
  continent: (it, k, a) => ({ font: `600 ${k > 12 ? 15 : 17}px ${SANS}`, size: 16, upper: true, spacing: '6px', color: a ? 'rgba(52,48,60,.78)' : 'rgba(255,255,255,.55)', halo: a ? 2 : 3, haloColor: a ? 'rgba(255,255,255,.5)' : halo(a) }),
  ocean: (it, k, a) => ({ font: `italic 400 ${it.rank <= 0 ? 17 : it.rank <= 2 ? 13.5 : 12}px ${SERIF}`, size: 15, upper: it.rank <= 0, spacing: it.rank <= 0 ? '5px' : '1.5px', color: a ? 'rgba(24,74,128,.9)' : 'rgba(150,195,235,.85)', halo: 2.5, haloColor: a ? 'rgba(255,255,255,.55)' : 'rgba(0,10,24,.6)' }),
  country: (it, k, a) => { const s = it.rank <= 2 ? 12 : it.rank <= 3 ? 11 : it.rank <= 4 ? 10.5 : 10; return { font: `${a ? 600 : 500} ${s}px ${SANS}`, size: s, upper: true, spacing: '1.8px', color: a ? 'rgba(28,26,30,.92)' : 'rgba(255,255,255,.88)', halo: 2.6, haloColor: halo(a) }; },
  city: (it, k, a) => { const big = it.pop > 5e6, s = big ? 12.5 : it.pop > 1e6 ? 11.5 : 10.5; return { font: `${it.capital ? 600 : 400} ${s}px ${SANS}`, size: s, dot: big ? 3.2 : 2.5, capital: it.capital, color: a ? 'rgba(20,20,24,.95)' : 'rgba(255,255,255,.95)', halo: 2.8, haloColor: halo(a) }; },
  feature: (it, k, a) => ({ font: `italic 400 ${it.rank <= 2 ? 12.5 : 11.5}px ${SERIF}`, size: 12, spacing: '1px', color: a ? 'rgba(84,58,30,.9)' : 'rgba(235,222,196,.85)', halo: 2.5, haloColor: halo(a) }),
  peak: (it, k, a) => ({ font: `italic 400 10.5px ${SERIF}`, size: 10.5, dot: 1.8, color: a ? 'rgba(84,58,30,.95)' : 'rgba(240,228,205,.9)', halo: 2.5, haloColor: halo(a) }),
  mark: (it, k, a) => ({ font: `600 11px ${SANS}`, size: 11, dot: 0, spacing: '1px', color: it.color || '#ffd66b', halo: 3, haloColor: 'rgba(0,6,16,.8)' }),
};
