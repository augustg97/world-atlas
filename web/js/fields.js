// The field store: one place that loads every raster, owns its GPU texture and (where the app
// needs to read values) its CPU copy. Everything that asks "what is the value here?" - the
// shader, the probe, the particles, the dashboard - reads the same field through this file.
//
// Binding tolerates absence: every sampler always has a valid texture (a placeholder until the
// real one lands) and `has.*` says which are real, so the first frame does not wait for 70 MB.

import { loadBitmap, texFromImage, texFromData, texSolid, packRG, texArrayFromPixels, pixelsOf, getJSON, stamped } from './gl.js';
import { monthState } from './astro.js';

export const UNIT = { albA: 0, albB: 1, relief: 2, waterNight: 3, elev: 4, clouds: 5, atmoA: 6, atmoB: 7, oceanA: 8, countries: 9, lens2D: 10, lut: 11, live: 12, aurora: 13,
  detAlb: 14, detElev: 15 };     // the focus window's streamed imagery and elevation (js/detail.js)
// SIXTEEN SAMPLERS IS THE LIMIT. WebGL 2 guarantees a fragment shader 16 texture units and no more, and that is what
// real hardware gives (Apple M5 Ultra on ANGLE Metal: MAX_TEXTURE_IMAGE_UNITS = 16); software GL allows 32, so a
// seventeenth sampler links in every headless check and blacks the page in a real browser. No sampler can be added to
// earth.frag.glsl without removing one. This is why the cloud-type atlas (cloudT) has no unit of its own: its twelve
// months ride in the atmoB array as layers 12-23. Check on hardware with scratchpad/detail_gpu_limits.py.
const ARRAYS = new Set(['atmoA', 'atmoB', 'oceanA']);                 // the units that hold a TEXTURE_2D_ARRAY
const F = 'fields/';
const pad = (m) => String(m + 1).padStart(2, '0');

export class Fields {
  constructor(gl, onChange) {
    this.gl = gl;
    this.onChange = onChange || (() => {});
    this.tex = {}; this.has = {}; this.cpu = {}; this.status = {}; this.meta = { climate: null, human: null };
    const black = texSolid(gl, [0, 0, 0, 255]), grey = texSolid(gl, [128, 128, 128, 255]);
    for (const k of ['albA', 'albB', 'waterNight', 'clouds', 'countries', 'lens2D', 'lut', 'live', 'aurora']) this.tex[k] = black;
    this.tex.relief = grey; this.tex.elev = texSolid(gl, [140, 204, 0, 255]);        // ~0 m
    for (const k of ['atmoA', 'atmoB', 'oceanA']) this.tex[k] = texArrayFromPixels(gl, 1, 1, 12, new Uint8Array(48).fill(128));
    // the focus window's samplers hold these until js/detail.js has a window, and again when it lets one go
    this.placeholder = { detAlb: black, detElev: black };
    this.tex.detAlb = black; this.tex.detElev = black;
    this.albedo = Array.from({ length: 12 }, () => ({ preview: null, full: null, loading: false, used: 0 }));
    this.lens = {};                       // name -> texture for the static lens fields
    this.bytes = 0;
  }

  _mark(name, state) { this.status[name] = state; this.onChange(name, state); }

  async _load(name, fn) {
    this._mark(name, 'loading');
    try { await fn(); this._mark(name, 'ready'); } catch (e) { console.error(`field ${name} failed`, e); this._mark(name, 'failed'); }
  }

  /** Everything the first frames need, in the order that makes the planet appear soonest. */
  async boot(tMs) {
    const gl = this.gl;
    const ms = monthState(tMs);
    const metas = Promise.all([getJSON(F + 'climate.json'), getJSON(F + 'human.json')])
      .then(([c, h]) => { this.meta.climate = c; this.meta.human = h; });
    const first = Promise.all([this._preview(ms.i0), this._preview(ms.i1)]);
    const water = this._load('water', async () => {
      const [w, n] = await Promise.all([loadBitmap(F + 'water.webp'), loadBitmap(F + 'night.webp')]);
      this.tex.waterNight = packRG(gl, w, n, w.width, w.height);
      const px = pixelsOf(w, 2048, 1024);
      const cw = new Uint8Array(2048 * 1024); for (let i = 0; i < cw.length; i++) cw[i] = px[i * 4];
      const pn = pixelsOf(n, 2048, 1024);
      const cn = new Uint8Array(2048 * 1024); for (let i = 0; i < cn.length; i++) cn[i] = pn[i * 4];
      this.cpu.water = { w: 2048, h: 1024, d: cw }; this.cpu.night = { w: 2048, h: 1024, d: cn };
      this.has.water = true; w.close(); n.close();
    });
    const climate = this._load('climate', async () => {
      await metas;
      const A = this.meta.climate.atlases;
      const names = ['atmoA', 'atmoB', 'atmoC', 'oceanA', 'oceanB'];
      if (A.cloudT) names.push('cloudT');                              // only once the build ships it
      const imgs = await Promise.all(names.map((k) => loadBitmap(F + A[k].file)));
      names.forEach((k, i) => {
        const { w, h } = A[k];
        const px = pixelsOf(imgs[i]);
        this.cpu[k] = { w, h, d: px, channels: A[k].channels };
        if (UNIT[k] !== undefined && k !== 'atmoB') this.tex[k] = texArrayFromPixels(gl, w, h, 12, px);
        imgs[i].close();
      });
      // atmoB's array carries the cloud-type atlas behind its own twelve months (layers 12-23) when the build ships one
      // on the same grid; the shader reads those layers only when uHasCloudT says they are there
      const b = this.cpu.atmoB, c = this.cpu.cloudT, joined = !!c && c.w === b.w && c.h === b.h && c.d.length === b.d.length;
      if (c && !joined) console.error(`cloudT is ${c.w} x ${c.h}, atmoB ${b.w} x ${b.h}: cloud types left out`);
      if (joined) { const both = new Uint8Array(b.d.length * 2); both.set(b.d, 0); both.set(c.d, b.d.length); this.tex.atmoB = texArrayFromPixels(gl, b.w, b.h, 24, both); }
      else this.tex.atmoB = texArrayFromPixels(gl, b.w, b.h, 12, b.d);
      this.has.climate = true; this.has.ocean = true; this.has.cloudT = joined;
    });
    const clouds = this._load('clouds', async () => { const b = await loadBitmap(F + 'clouds.jpg'); this.tex.clouds = texFromImage(gl, b, { format: 'r' }); b.close(); });
    await Promise.all([first, metas]);
    this._settle = Promise.all([water, climate, clouds]).then(() => this._second(ms));
    return this;
  }

  async _second(ms) {
    const gl = this.gl;
    await this._load('relief', async () => {
      const [x, y] = await Promise.all([loadBitmap(F + 'relief_x.webp'), loadBitmap(F + 'relief_y.webp')]);
      this.tex.relief = packRG(gl, x, y, x.width, x.height); this.has.relief = true; x.close(); y.close();
    });
    await this._load('countries', async () => {
      const b = await loadBitmap(F + 'countries.png');
      this.tex.countries = texFromImage(gl, b, { format: 'rgb', mips: false, filter: 'nearest' });
      const c = new OffscreenCanvas(4096, 2048); const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.imageSmoothingEnabled = false; ctx.drawImage(b, 0, 0, 4096, 2048);
      const px = ctx.getImageData(0, 0, 4096, 2048).data;
      const ids = new Uint8Array(4096 * 2048), dis = new Uint8Array(4096 * 2048);
      for (let i = 0; i < ids.length; i++) { ids[i] = px[i * 4]; dis[i] = px[i * 4 + 1]; }
      this.cpu.countries = { w: 4096, h: 2048, d: ids }; this.cpu.disputed = { w: 4096, h: 2048, d: dis };
      this.has.countries = true; b.close();
    });
    await this._load('elev', async () => {
      const b = await loadBitmap(F + 'elev.png');
      this.tex.elev = texFromImage(gl, b, { format: 'rg' });
      const px = pixelsOf(b);
      const e = new Uint16Array(b.width * b.height);
      for (let i = 0; i < e.length; i++) e[i] = (px[i * 4] << 8) | px[i * 4 + 1];
      this.cpu.elev = { w: b.width, h: b.height, d: e }; this.has.elev = true; b.close();
    });
    this._fullFor(ms.i0); this._fullFor(ms.i1);
    for (let m = 0; m < 12; m++) await this._preview(m);       // the whole year at preview quality, so scrubbing never shows a hole
    for (const k of ['pop', 'co2', 'ships']) await this.loadStatic(k);
    this._load('lanes', async () => { const b = await loadBitmap(F + 'lanes.png'); this.cpu.lanes = { w: b.width, h: b.height, d: pixelsOf(b) }; b.close(); });
    this._load('pop1', async () => { this.cpu.pop1 = new Float32Array(await (await fetch(stamped(F + 'pop_1deg.bin'))).arrayBuffer()); });
    this._load('co21', async () => { this.cpu.co21 = new Float32Array(await (await fetch(stamped(F + 'co2_1deg.bin'))).arrayBuffer()); });
  }

  async _preview(m) {
    const a = this.albedo[m];
    if (a.preview || a.pLoading) return a.pLoading;
    a.pLoading = (async () => {
      try { const b = await loadBitmap(`${F}albedo_${pad(m)}_p.webp`); a.preview = texFromImage(this.gl, b, { format: 'rgb' }); b.close(); this.onChange('albedo', 'preview'); }
      catch (e) { console.error('albedo preview', m, e); }
    })();
    return a.pLoading;
  }

  async _fullFor(m) {
    const a = this.albedo[m];
    a.used = performance.now();
    if (a.full || a.loading) return;
    a.loading = true;
    try {
      const b = await loadBitmap(`${F}albedo_${pad(m)}.webp`);
      a.full = texFromImage(this.gl, b, { format: 'rgb' }); b.close();
      // GPU residency is capped: keep the three most recently used full-resolution months
      const live = this.albedo.filter((x) => x.full).sort((p, q) => q.used - p.used);
      for (const old of live.slice(3)) { this.gl.deleteTexture(old.full); old.full = null; }
      this.onChange('albedo', 'full');
    } catch (e) { console.error('albedo full', m, e); }
    a.loading = false;
  }

  /** Point the two albedo samplers at the months bracketing t; fetch what is missing. */
  setMonths(ms, settled) {
    for (const [slot, m] of [['albA', ms.i0], ['albB', ms.i1]]) {
      const a = this.albedo[m];
      a.used = performance.now();
      if (!a.preview) this._preview(m);
      if (settled && !a.full) this._fullFor(m);
      const t = a.full || a.preview;
      if (t) this.tex[slot] = t;
    }
    const a0 = this.albedo[ms.i0], a1 = this.albedo[ms.i1];
    return { detail: a0.full && a1.full ? 'full' : (a0.preview && a1.preview ? 'preview' : 'none') };
  }

  async loadStatic(name) {
    if (this.lens[name] || this.status[name] === 'loading') return;
    await this._load(name, async () => {
      const m = this.meta.human[name];
      const b = await loadBitmap(F + m.file);
      this.lens[name] = texFromImage(this.gl, b, { format: 'r' });
      const px = pixelsOf(b);
      const d = new Uint8Array(b.width * b.height); for (let i = 0; i < d.length; i++) d[i] = px[i * 4];
      this.cpu[name] = { w: b.width, h: b.height, d, meta: m }; b.close();
    });
  }
  setLens2D(name) { if (this.lens[name]) this.tex.lens2D = this.lens[name]; }

  bind() {
    const gl = this.gl;
    for (const k in UNIT) {
      gl.activeTexture(gl.TEXTURE0 + UNIT[k]);
      gl.bindTexture(ARRAYS.has(k) ? gl.TEXTURE_2D_ARRAY : gl.TEXTURE_2D, this.tex[k]);
    }
    gl.activeTexture(gl.TEXTURE0);
  }

  // ------------------------------- reading values on the CPU -------------------------------
  _px(f, lon, lat) {
    const x = Math.min(f.w - 1, Math.max(0, Math.floor(((lon + 180) / 360) * f.w))) % f.w;
    const y = Math.min(f.h - 1, Math.max(0, Math.floor(((90 - lat) / 180) * f.h)));
    return y * f.w + x;
  }
  /** Bilinear sample of one channel of one month of a stacked atlas; returns the raw byte (float). */
  _atlas(f, ch, m, lon, lat) {
    const fx = ((lon + 180) / 360) * f.w - 0.5, fy = ((90 - lat) / 180) * f.h - 0.5;
    const x0 = Math.floor(fx), y0 = Math.max(0, Math.min(f.h - 1, Math.floor(fy)));
    const ax = fx - x0, ay = Math.max(0, Math.min(1, fy - y0));
    const xa = ((x0 % f.w) + f.w) % f.w, xb = (xa + 1) % f.w, yb = Math.min(f.h - 1, y0 + 1);
    const o = m * f.h * f.w * 4, d = f.d;
    const v00 = d[o + (y0 * f.w + xa) * 4 + ch], v10 = d[o + (y0 * f.w + xb) * 4 + ch];
    const v01 = d[o + (yb * f.w + xa) * 4 + ch], v11 = d[o + (yb * f.w + xb) * 4 + ch];
    return (v00 * (1 - ax) + v10 * ax) * (1 - ay) + (v01 * (1 - ax) + v11 * ax) * ay;
  }
  _decode(name, byte) {
    const e = this.meta.climate.encodings[name];
    let x = byte / 255;
    if (e.curve === 'sqrt') x = x * x;
    else if (e.curve === 'ssqrt') { const s = x * 2 - 1; x = 0.5 + 0.5 * Math.sign(s) * s * s; }
    return e.lo + (e.hi - e.lo) * x;
  }
  /** A climatological value at a place and month state. NaN where the field has no data. */
  climate(name, lon, lat, ms) {
    if (!this.has.climate) return NaN;
    const where = { u10: ['atmoA', 0], v10: ['atmoA', 1], t0: ['atmoA', 2], slp: ['atmoB', 0], cloud: ['atmoB', 1], precip: ['atmoB', 2],
      u250: ['atmoC', 0], v250: ['atmoC', 1], sst: ['oceanA', 0], ice: ['oceanA', 1], ucur: ['oceanB', 0], vcur: ['oceanB', 1],
      deck: ['cloudT', 0], cu: ['cloudT', 1], light: ['cloudT', 2] }[name];
    const f = this.cpu[where[0]];
    if (!f) return NaN;                                               // an atlas that has not shipped
    if (where[0].startsWith('ocean')) {
      const valid = f.d[ms.i0 * f.h * f.w * 4 + this._px(f, lon, lat) * 4 + 2];
      if (valid < 128) return NaN;
    }
    const a = this._atlas(f, where[1], ms.i0, lon, lat), b = this._atlas(f, where[1], ms.i1, lon, lat);
    // decode each month, then mix: the curves are not linear
    return this._decode(name, a) * (1 - ms.f) + this._decode(name, b) * ms.f;
  }
  elevation(lon, lat) {
    const f = this.cpu.elev; if (!f) return NaN;
    return (f.d[this._px(f, lon, lat)] / 65535) * 20000 - 11000;
  }
  waterFrac(lon, lat) { const f = this.cpu.water; return f ? f.d[this._px(f, lon, lat)] / 255 : NaN; }
  nightLight(lon, lat) { const f = this.cpu.night; if (!f) return NaN; const v = f.d[this._px(f, lon, lat)] / 255; return v * v; }
  countryId(lon, lat) { const f = this.cpu.countries; return f ? f.d[this._px(f, lon, lat)] : 0; }
  isDisputed(lon, lat) { const f = this.cpu.disputed; return f ? f.d[this._px(f, lon, lat)] > 127 : false; }
  /** A log-companded static field decoded to physical units (people/km2, t CO2/km2/yr, AIS positions). */
  staticValue(name, lon, lat) {
    const f = this.cpu[name]; if (!f) return NaN;
    const e = f.d[this._px(f, lon, lat)] / 255;
    return f.meta.x0 * Math.expm1(e * Math.log1p(f.meta.xmax / f.meta.x0));
  }
}
