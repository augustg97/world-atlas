// World Atlas - entry point. One scalar (state.t, UTC ms) plus the toggles drives every pixel:
//   state = { t, clock, style, lens, layers{} }  ->  render(state)
// The substrate is drawn into a cache whenever state or camera changes; things that move
// (tracers, aircraft, satellites, pulses) are drawn over it every frame.

import { Camera, R_KM } from './camera.js?v=20261112T020725Z';
import { Fields, UNIT } from './fields.js?v=20261112T020725Z';
import { Earth, LENSES } from './earth.js?v=20261112T020725Z';
import { Detail } from './detail.js?v=20261112T020725Z';
import { sun, moon, monthState, seasonName, D2R } from './astro.js?v=20261112T020725Z';
import { program, setUniforms, texFromImage, loadVersion } from './gl.js?v=20261112T020725Z';
import { LineBatch, PointBatch, Labels, segmentsFromLines, deq, graticule, parallels } from './overlays.js?v=20261112T020725Z';
import { FlowTracers, Flights, makeSamplers, seedRandom } from './particles.js?v=20261112T020725Z';
import { SYSTEMS, LAYERS, paletteCanvas, FUEL_COLORS } from './catalog.js?v=20261112T020725Z';
import { Data } from './data.js?v=20261112T020725Z';
import { INSETS, Inset, insetAlpha, INSET_PAD } from './insets.js?v=20261112T020725Z';
import { Live, HOUR, DAY } from './live.js?v=20261112T020725Z';
import { UI, SPEEDS } from './ui.js?v=20261112T020725Z';
import * as Cards from './cards.js?v=20261112T020725Z';
import { peopleBySun, iceExtents, meanTemps, mixMonth } from './dash.js?v=20261112T020725Z';

const canvas = document.getElementById('gl');
const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: true });
const bootMsg = (s) => { document.getElementById('boot-msg').textContent = s; };
if (!gl) { bootMsg('This atlas needs WebGL 2, which this browser does not provide.'); throw new Error('no webgl2'); }

// ?frozen=1 is the deterministic mode the visual ratchet needs (Research/baselines/frames.json):
// the clock is pinned to #t=, nothing is driven by requestAnimationFrame or the wall clock, the
// tracers run a fixed number of seeded steps, and window.__FRAME_READY goes true when the frame
// on screen is final. Two loads of the same URL then give the same pixels.
const FROZEN = new URLSearchParams(location.search).has('frozen');
const FROZEN_T = Date.UTC(2026, 5, 21, 12, 0, 0);
const FROZEN_STEPS = 240;
if (FROZEN) seedRandom(20261109);

const cam = new Camera();
const state = {
  t: Date.now(), clock: 'live', speed: 'real', style: 'space', lens: 'none', selCountry: 0,
  layers: Object.fromEntries(Object.values(LAYERS).map((l) => [l.id, !!l.on])),
};
let earthDirty = true, labelsDirty = true, lastEarthDraw = 0, selection = null, card = null, hashTimer = 0;
const fields = new Fields(gl, () => { earthDirty = true; });
const earth = new Earth(gl, fields);
const data = new Data();
const live = new Live(gl, fields, (k, s) => { earthDirty = true; feedStatus(); });
// finer imagery and elevation for the part of the Earth in view, streamed when close in (register A2)
const detail = new Detail(gl, fields, () => { earthDirty = true; window.__DETAIL_ERROR = detail.error || undefined; feedStatus(); }, { frozen: FROZEN });
const labels = new Labels(document.getElementById('labels'));
// Insets of the whole-Earth sheet: second views of the same atlas over open water (insets.js). Each has its own
// camera and its own label layer, which draws into its frame on the main layer's canvas.
const insets = INSETS.map((def) => { const I = new Inset(def); I.labels = new Labels(labels.canvas, true); return I; });
// The interface's panels, as rectangles of the window. No name is set under one and no inset is put under one.
const PANELS = ['top', 'left', 'left-open', 'card', 'dash', 'legend', 'hud', 'time'], PANEL_PAD = 4;
let panelRects = [], panelSig = '';
const astro = { sun: sun(state.t), moon: moon(state.t), month: monthState(state.t) };
let progs = {}, batches = {}, tracers = {}, flights = null, samplers = null, cache = null, dashCache = {}, ui = null;

const hexRgb = (h) => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255];
const isNow = () => !FROZEN && (state.clock === 'live' || Math.abs(state.t - Date.now()) < HOUR);

// ------------------------------------------------------------------------------------ app API
const app = {
  state, cam, fields, earth, data, live, detail,
  setLayer(id, on) {
    state.layers[id] = on; earthDirty = labelsDirty = true;
    if (on) ensureLayer(id);
    ui.syncControls(); feedStatus(); saveHash();
  },
  setLens(id) {
    state.lens = id; earthDirty = true;
    const L = LENSES[id]; if (L && L.static) { pending.add('lens'); fields.loadStatic(L.static).then(() => { pending.delete('lens'); earthDirty = true; }); }
    ui.syncControls(); saveHash();
  },
  setView(v) { cam.setView(v); earthDirty = labelsDirty = true; resetTracers(); ui.syncControls(); saveHash(); },
  setStyle(s) { state.style = s; earthDirty = labelsDirty = true; buildStatic(); ui.syncControls(); saveHash(); },
  setTime(t) { state.t = t; state.clock = 'paused'; timeChanged(); },
  goLive() { state.t = Date.now(); state.clock = 'live'; state.speed = 'real'; timeChanged(); ui.syncControls(); },
  togglePlay() { state.clock = state.clock === 'paused' ? 'run' : 'paused'; ui.clock(); },
  setSpeed(id) { state.speed = id; if (state.clock !== 'paused') state.clock = id === 'real' && Math.abs(state.t - Date.now()) < 5000 ? 'live' : 'run'; ui.clock(); },
  search: (q) => data.search(q),
  pick(hit) { flyTo(hit.lon, hit.lat, Math.min(cam.kmPerPx(), hit.km)); openRef(hit.ref); },
  openRef(s) {
    const [k, v] = [s.slice(0, s.indexOf(':')), s.slice(s.indexOf(':') + 1)];
    if (k === 'country') { const c = data.countryByA3[v]; if (c) openRef(['country', c]); }
    else if (k === 'dispute') { const [name, note] = v.split('|'); const d = data.political.disputes.find((x) => x.name === name && x.note === note); if (d) { openRef(['dispute', d]); flyTo(d.lon, d.lat, Math.min(cam.kmPerPx(), 3)); } }
  },
  openLayerCard(id, isLens) { selection = null; state.selCountry = 0; card = { build: () => Cards.layerCard(id, isLens) }; refreshCard(); labelsDirty = earthDirty = true; },
  closeCard() { card = null; selection = null; state.selCountry = 0; ui.showCard(null); labelsDirty = earthDirty = true; },
  flyToSelection() { if (selection) flyTo(selection.lon, selection.lat, Math.min(cam.kmPerPx(), 4)); },
};

function ctx() { return { F: fields, D: data, astro, t: state.t }; }
function openRef(ref) {
  const [kind, obj, extra] = ref;
  const build = {
    country: () => Cards.countryCard(ctx(), obj), city: () => Cards.cityCard(ctx(), obj), feature: () => Cards.featureCard(ctx(), obj),
    dispute: () => Cards.disputeCard(ctx(), obj), quake: () => Cards.quakeCard(ctx(), obj, extra), volcano: () => Cards.volcanoCard(ctx(), obj),
    plant: () => Cards.plantCard(ctx(), data.power, obj), airport: () => Cards.airportCard(ctx(), obj, data.air), probe: () => Cards.probeCard(ctx(), obj[0], obj[1]),
    sat: () => ({ kind: 'sat', lon: obj.lon, lat: obj.lat, html: `<div class="eyebrow">Satellite · ${obj.kind}</div><h2>${obj.name}</h2><div class="tierhead">Propagated from published orbital elements</div><div class="sec"><div class="row"><span class="k">Altitude</span><span class="v">${Math.round(obj.km).toLocaleString('en-US')} km</span></div><div class="row"><span class="k">Over</span><span class="v">${Cards.coord(obj.lon, obj.lat)}</span></div></div><div class="note">${live.note.sats || ''}. Positions are computed with SGP4 and are good for about two weeks either side of the element date.</div>` }),
  }[kind];
  if (!build) return;
  card = { build };
  refreshCard();
  state.selCountry = kind === 'country' ? obj.id : 0;
  earthDirty = labelsDirty = true;
}
function refreshCard() {
  if (!card) return;
  const c = card.build();
  selection = c.lon !== undefined ? { lon: c.lon, lat: c.lat } : null;
  ui.showCard(c);
}

let fly = null;
const pending = new Set();       // lazy data still on its way; a frozen frame waits for it
function flyTo(lon, lat, km) {
  const c = cam.center();
  fly = { t0: performance.now(), from: [c[0], c[1], cam.kmPerPx()], to: [lon, lat, km] };
  // The flight takes 0.9 s and where it ends is known now: the focus window for the destination is asked for at once,
  // with the camera put there for the asking and put back, so the finer ground is on its way before the view arrives.
  if (state.layers.detail) {
    cam.setKmPerPx(km); cam.lookAt(lon, lat);
    detail.update(cam, true, true, state.layers.lights && state.layers.daylight ? astro.sun : null, true, true);
    cam.setKmPerPx(fly.from[2]); cam.lookAt(fly.from[0], fly.from[1]);
  }
}

function timeChanged() { astroUpdate(); earthDirty = labelsDirty = true; ui.clock(); if (state.layers.today) live.loadToday(state.t); feedStatus(); refreshCardSoon(); saveHash(); }
let cardTimer = 0;
function refreshCardSoon() { clearTimeout(cardTimer); cardTimer = setTimeout(() => { refreshCard(); updateDash(true); }, 120); }
function astroUpdate() { astro.sun = sun(state.t); astro.moon = moon(state.t); astro.month = monthState(state.t); }

// ----------------------------------------------------------------------------- layer plumbing
function ensureLayer(id) {
  const lazy = { plates: 'plates', quakes: 'quakes', volcanoes: 'volcanoes', power: 'power', flights: 'air' }[id];
  if (lazy) pending.add(lazy), data.loadLazy(lazy).then(() => { pending.delete(lazy); buildStatic(); if (id === 'flights' && !flights) flights = new Flights(gl, progs.lines, data.air); });
  if (id === 'quakesLive') live.loadQuakes();
  if (id === 'aurora') live.loadAurora();
  if (id === 'today') live.loadToday(state.t);
  if (id === 'sats') live.loadSats();
}

function feedStatus() {
  if (!ui) return;
  const now = isNow();
  const s = (id, feed, offText) => {
    if (!state.layers[id]) return ui.layerStatus(id, '');
    const st = live.status[feed];
    if (feed !== 'today' && feed !== 'sats' && !now) return ui.layerStatus(id, offText || 'Off: the clock is away from the present.', 'warn');
    ui.layerStatus(id, st === 'loading' ? 'Fetching…' : live.note[feed] || '', st === 'ready' ? 'ok' : st === 'unavailable' || st === 'none' ? 'warn' : '');
  };
  s('quakesLive', 'quakes'); s('aurora', 'aurora'); s('today', 'today'); s('sats', 'sats');
  ui.layerStatus('detail', state.layers.detail ? detail.note : '', detail.state === 'ready' ? 'ok' : detail.state === 'partial' || detail.state === 'failed' ? 'warn' : '');
  if (state.layers.sats && live.sats && Math.abs(state.t - live.satEpoch) > 14 * DAY) ui.layerStatus('sats', 'Clock is more than two weeks from the elements’ date: positions would be invented, so none are drawn.', 'warn');
}

/** Static line and point batches. Rebuilt when the style changes (colours) or lazy data lands. */
function buildStatic() {
  const atlas = state.style === 'atlas';
  const mk = (name, lines, color, width) => { (batches[name] ||= new LineBatch(gl, progs.lines)).set(segmentsFromLines(lines, color, width)); };
  const pts = (name, arr) => { (batches[name] ||= new PointBatch(gl, progs.points)).set(new Float32Array(arr)); };
  const P = data.political;
  if (P) {
    mk('borders', P.borders.international.map(deq), atlas ? [0.36, 0.26, 0.36, 0.8] : [1, 1, 1, 0.34], atlas ? 1.1 : 0.9);
    mk('disputed', [...P.borders.disputed, ...P.borders.claim].map(deq), atlas ? [0.62, 0.18, 0.30, 0.9] : [1, 0.62, 0.68, 0.75], 1.2);
    mk('rivers', data.physical.rivers.flatMap((r) => r.lines.map(deq)), atlas ? [0.25, 0.48, 0.72, 0.85] : [0.55, 0.78, 1.0, 0.5], 0.9);
  }
  mk('graticule', graticule(15), atlas ? [0.2, 0.3, 0.45, 0.28] : [1, 1, 1, 0.13], 0.7);
  mk('circles', parallels([23.4364, -23.4364, 66.5636, -66.5636]), atlas ? [0.55, 0.35, 0.1, 0.6] : [1, 0.85, 0.5, 0.42], 0.9);
  mk('equator', parallels([0]), atlas ? [0.3, 0.3, 0.35, 0.45] : [1, 1, 1, 0.26], 0.9);
  if (data.plates) {
    const b = data.plates.boundaries;
    mk('plates', b.filter((x) => !x.subduction).map((x) => deq(x.line)), [1.0, 0.45, 0.2, 0.75], 1.2);
    mk('subduction', b.filter((x) => x.subduction).map((x) => deq(x.line)), [1.0, 0.25, 0.25, 0.9], 2.2);
  }
  if (data.quakes) {
    const a = [];
    for (const [, lon, lat, depth, mag] of data.quakes.rows) {
      const c = depth < 70 ? [1.0, 0.42, 0.2] : depth < 300 ? [1.0, 0.82, 0.4] : [0.3, 0.79, 0.94];
      a.push(lon * D2R, lat * D2R, 0, ...c, 0.6, 2.2 + (mag - 6) * 3.6, 1);
    }
    pts('quakes', a);
  }
  if (data.volcanoes) { const a = []; for (const v of data.volcanoes.rows) a.push(v[1] * D2R, v[2] * D2R, 0, 0.95, 0.3, 0.16, 0.9, 3.6, 2); pts('volcanoes', a); }
  if (data.power) {
    const big = [], all = [], W = data.power;
    for (let i = 0; i < W.mw.length; i++) {
      const c = hexRgb(FUEL_COLORS[W.fuels[W.fuel[i]]]);
      const row = [W.lon[i] * D2R, W.lat[i] * D2R, 0, ...c, 0.9, 1.6 + Math.sqrt(W.mw[i]) / 24, 3];
      all.push(...row); if (W.mw[i] >= 1000) big.push(...row);
    }
    pts('powerBig', big); pts('powerAll', all);
  }
  if (data.air) { const a = []; for (const p of data.air.airports) a.push(p.lon * D2R, p.lat * D2R, 0, 1, 1, 1, 0.85, 2.2, 0); pts('airports', a); }
}

function resetTracers() { for (const k in tracers) { tracers[k].age.fill(1e9); } }
function buildTracers() {
  const area = Math.min(2.2, (cam.w * cam.h) / (1440 * 900));
  const space = () => state.style !== 'atlas';
  tracers.wind = new FlowTracers(gl, progs.lines, Math.round(5200 * area), 9, { pxPerUnit: 0.17, life: 95, vmax: 13, width: 1.0,
    color: (s) => (space() ? [0.85 + 0.15 * s, 0.94, 1.0, 0.16 + 0.5 * s] : [0.12, 0.25 + 0.2 * s, 0.5, 0.25 + 0.5 * s]) });
  tracers.jet = new FlowTracers(gl, progs.lines, Math.round(2600 * area), 12, { pxPerUnit: 0.04, life: 110, vmax: 60, width: 1.3, height: 0.0017,
    color: (s) => (space() ? [1.0, 0.72 + 0.2 * s, 0.9, 0.12 + 0.6 * s] : [0.6, 0.15, 0.5, 0.2 + 0.6 * s]) });
  tracers.currents = new FlowTracers(gl, progs.lines, Math.round(4600 * area), 10, { pxPerUnit: 3.6, life: 120, vmax: 0.6, width: 1.3,
    color: (s) => (space() ? [0.45 + 0.5 * s, 0.97, 1.0, 0.3 + 0.7 * Math.sqrt(s)] : [0.05, 0.4 + 0.3 * s, 0.55, 0.3 + 0.5 * Math.sqrt(s)]) });
  tracers.ships = new FlowTracers(gl, progs.lines, Math.round(3600 * area), 6, { pxPerUnit: 0.7, life: 200, vmax: 1, width: 1.3, tries: 40, accept: samplers.laneAccept,
    color: () => (space() ? [1.0, 0.78, 0.42, 0.85] : [0.65, 0.25, 0.05, 0.9]) });
}

// ------------------------------------------------------------------------------------ drawing
function makeCache() {
  if (cache) { gl.deleteFramebuffer(cache.fb); gl.deleteTexture(cache.tex); }
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, canvas.width, canvas.height);
  const fb = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  cache = { fb, tex, w: canvas.width, h: canvas.height };
}

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = window.innerWidth, h = window.innerHeight;
  if (w < 8 || h < 8) return;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  cam.resize(w, h, dpr); labels.resize(w, h, dpr);
  makeCache(); earthDirty = labelsDirty = true;
}

let lastFrame = performance.now(), settledAt = 0, dynPts = null;
const fs = {};      // per-frame scratch state shared with picking and the label pass
function frame(now) { requestAnimationFrame(frame); tick(now); }
/** One frame. Also callable directly (ATLAS.step) so a hidden or headless page can still be rendered and inspected. */
function tick(now) {
  const dt = Math.max(0, Math.min(100, now - lastFrame)); lastFrame = Math.max(lastFrame, now);
  if (!cache || cam.w < 8) return;

  // 1. the clock
  if (state.clock === 'live') { const t = Date.now(); if (Math.floor(t / 1000) !== Math.floor(state.t / 1000)) { state.t = t; astroUpdate(); } }
  else if (state.clock === 'run') {
    const sp = SPEEDS.find((s) => s.id === state.speed);
    if (sp.days) { fs.acc = (fs.acc || 0) + (dt / 1000) * sp.days; if (fs.acc >= 1) { const n = Math.floor(fs.acc); fs.acc -= n; state.t += n * DAY; timeChanged(); } }
    else { state.t += dt * sp.rate; astroUpdate(); if (sp.rate > 30) earthDirty = labelsDirty = true; }
  }
  if (now - lastEarthDraw > 2500) earthDirty = true;                 // the terminator creeps even in real time

  // 2. camera animation
  if (fly) {
    const u = Math.max(0, Math.min(1, (now - fly.t0) / 900)), e = u < 0.5 ? 2 * u * u : 1 - 2 * (1 - u) * (1 - u);
    let dl = fly.to[0] - fly.from[0]; if (dl > 180) dl -= 360; if (dl < -180) dl += 360;
    cam.setKmPerPx(Math.exp(Math.log(fly.from[2]) * (1 - e) + Math.log(fly.to[2]) * e));
    cam.lookAt(fly.from[0] + dl * e, fly.from[1] + (fly.to[1] - fly.from[1]) * e);
    earthDirty = labelsDirty = true;
    if (u >= 1) { fly = null; saveHash(); }
  }

  // 2b. what is not map: the panels as they stand now, then the insets in the open water that is left
  measurePanels();
  layoutInsets();

  // 3. the substrate, into the cache
  const settled = now - settledAt > 350;
  const det = fields.setMonths(astro.month, settled);
  // the focus window is asked for sooner than the full month is (120 ms after the last movement against 350): a request that turns
  // out early costs a few tiles and is stopped, and a late one is half a second of blur
  detail.update(cam, now - settledAt > 120 && !fly, !!state.layers.detail, state.layers.lights && state.layers.daylight ? astro.sun : null, !!fly);
  if (detail.fading(performance.now())) earthDirty = true;           // a window that has just arrived fades in
  if (earthDirty) {
    earthDirty = false; lastEarthDraw = now; state.atNow = isNow();
    gl.bindFramebuffer(gl.FRAMEBUFFER, cache.fb);
    gl.viewport(0, 0, cache.w, cache.h);
    earth.draw(state, cam, astro, detail);
    // each inset: the same shader through the inset's own camera, into a target of its own
    const relief = earth.relief;
    for (const I of insets) if (I.rect) { insetTarget(I); gl.bindFramebuffer(gl.FRAMEBUFFER, I.fb); gl.viewport(0, 0, I.pw, I.ph); earth.draw(state, I.cam, astro, null); }
    earth.relief = relief;                                             // the About panel states the main map's exaggeration
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }
  gl.bindFramebuffer(gl.READ_FRAMEBUFFER, cache.fb);
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, null);
  gl.blitFramebuffer(0, 0, cache.w, cache.h, 0, 0, canvas.width, canvas.height, gl.COLOR_BUFFER_BIT, gl.NEAREST);
  gl.bindFramebuffer(gl.READ_FRAMEBUFFER, null);
  gl.viewport(0, 0, canvas.width, canvas.height);

  // 4. what sits on it
  const L = state.layers, camU = cam.uniforms(), k = cam.kmPerPx(), atlas = state.style === 'atlas', dpr = cam.dpr;
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  drawLines(camU, k, 1);
  const f = fs.still ? 0 : Math.min(3, dt / 16.7);                    // still: draw the tracers where they are (see frozenFrame)
  if (samplers && !fs.hold) {
    if (L.currents && fields.has.ocean) { if (f) tracers.currents.step(cam, samplers.currents, f); tracers.currents.draw(camU, 1); }
    if (L.wind && fields.has.climate) { if (f) tracers.wind.step(cam, samplers.wind, f); tracers.wind.draw(camU, atlas ? 0.9 : 0.75); }
    if (L.jet && fields.has.climate) { if (f) tracers.jet.step(cam, samplers.jet, f); tracers.jet.draw(camU, 0.9); }
    if (L.ships && fields.cpu.lanes) { if (f) tracers.ships.step(cam, samplers.lanes, f); tracers.ships.draw(camU, atlas ? 0.9 : 0.62); }
  }
  if (L.flights && flights) dashCache.aloft = flights.draw(camU, state.t, astro.sun, Math.max(0.62, Math.min(1, k / 8)), k);
  drawPoints(camU, k, 1);

  // dynamic points: live quakes, satellites, the Sun and Moon marks, the selection
  const dp = [];
  if (L.quakesLive && live.quakes && isNow()) {
    for (const q of live.quakes.rows) {
      const age = (state.t - q[6]) / DAY; if (age < 0 || age > 30) continue;
      const fresh = Math.max(0, 1 - age / 2), r = 1.8 + (q[4] - 4.5) * 2.2;
      dp.push(q[1] * D2R, q[2] * D2R, 0, 1.0, 0.55 - 0.25 * fresh, 0.15, 0.2 + 0.6 * Math.exp(-age / 5), r, 0);
      if (fresh > 0) { const ph = (now / 1400 + q[6] % 7) % 1; dp.push(q[1] * D2R, q[2] * D2R, 0, 1.0, 0.8, 0.4, (1 - ph) * fresh, r + 14 * ph, 1); }
    }
  }
  if (L.sats && live.sats && Math.abs(state.t - live.satEpoch) <= 14 * DAY) {
    fs.sats = live.satPositions(state.t);
    for (const s of fs.sats) { const c = s.kind === 'station' ? [1, 0.95, 0.6] : s.kind === 'navigation' ? [0.6, 0.85, 1] : [0.9, 0.9, 0.95]; dp.push(s.lon * D2R, s.lat * D2R, s.h, ...c, 0.95, s.kind === 'station' ? 3.4 : 2.0, 0); }
  } else fs.sats = null;
  if (L.marks) {
    dp.push(astro.sun.lon * D2R, astro.sun.lat * D2R, 0, 1.0, 0.86, 0.35, 0.55, 15, 4, astro.sun.lon * D2R, astro.sun.lat * D2R, 0, 1.0, 0.9, 0.5, 1, 3.5, 0);
    dp.push(astro.moon.lon * D2R, astro.moon.lat * D2R, 0, 0.8, 0.85, 0.95, 1, 3.5, 1);
  }
  if (selection) { const ph = (now / 1600) % 1; dp.push(selection.lon * D2R, selection.lat * D2R, 0, 1.0, 0.85, 0.35, 1, 7, 1, selection.lon * D2R, selection.lat * D2R, 0, 1.0, 0.85, 0.35, 0.6 * (1 - ph), 7 + 12 * ph, 1); }
  if (dp.length) { (dynPts ||= new PointBatch(gl, progs.points, true)).set(new Float32Array(dp)); dynPts.draw(camU, { sizeScale: dpr }); }

  // 4b. the insets, over everything the main map drew: ground, then the same lines and points through their cameras.
  // Tracers and aircraft are the main map's only (they are seeded and stepped for one camera).
  for (const I of insets) {
    if (!I.rect || !I.fb) continue;
    if (I.alpha >= 0.999) {
      gl.bindFramebuffer(gl.READ_FRAMEBUFFER, I.fb);
      gl.blitFramebuffer(0, 0, I.pw, I.ph, I.vx, I.vy, I.vx + I.pw, I.vy + I.ph, gl.COLOR_BUFFER_BIT, gl.NEAREST);
      gl.bindFramebuffer(gl.READ_FRAMEBUFFER, null);
    }
    gl.viewport(I.vx, I.vy, I.pw, I.ph); gl.enable(gl.SCISSOR_TEST); gl.scissor(I.vx, I.vy, I.pw, I.ph);
    if (I.alpha < 0.999) {                                             // fading: composed straight over the map at that strength
      const relief = earth.relief;
      gl.enable(gl.BLEND); gl.blendColor(0, 0, 0, I.alpha); gl.blendFunc(gl.CONSTANT_ALPHA, gl.ONE_MINUS_CONSTANT_ALPHA);
      earth.draw(state, I.cam, astro, null, true);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); earth.relief = relief;
    }
    const iu = I.cam.uniforms();
    drawLines(iu, I.k, I.alpha); drawPoints(iu, I.k, I.alpha);
    if (dp.length) dynPts.draw(iu, { sizeScale: dpr, alpha: I.alpha });
    gl.disable(gl.SCISSOR_TEST);
  }
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.disable(gl.BLEND);

  // 5. names
  if (labelsDirty) { labelsDirty = false; drawNames(); }
  // 6. panels
  fs.detail = det.detail;
  if (now - (fs.uiAt || 0) > 250) { fs.uiAt = now; ui.clock(); ui.hud(k, hover, det.detail === 'full' ? (detail.busy ? 'fetching finer tiles…' : '') : det.detail === 'preview' ? 'refining detail…' : 'loading terrain…', state.layers.detail && detail.cur && detail.uniforms(performance.now()).uDetAlbW > 0 ? detail.cur.credit : null); }
  if (now - (fs.dashAt || 0) > 1000) { fs.dashAt = now; updateDash(false); if (state.clock !== 'paused' && card) refreshCard(); }
}

/** Lines that lie on the ground, through any camera of the atlas (the main map's, an inset's). a: overall strength. */
function drawLines(camU, k, a) {
  const L = state.layers, dpr = cam.dpr;
  const line = (name, o = {}) => batches[name] && batches[name].draw(camU, { widthScale: dpr, ...o, alpha: (o.alpha === undefined ? 1 : o.alpha) * a });
  if (L.graticule) { line('graticule'); line('equator'); }
  if (L.marks) line('circles', { dashKm: k * 14, duty: 0.55 });
  if (L.rivers) line('rivers', { alpha: Math.min(1, 14 / k) });
  if (L.borders) { line('borders', { alpha: Math.min(1, 0.55 + 6 / k) }); line('disputed', { dashKm: Math.max(18, k * 9), duty: 0.55 }); }
  if (L.plates) { line('plates'); line('subduction'); }
}
/** The same for the catalogued points. */
function drawPoints(camU, k, a) {
  const L = state.layers, dpr = cam.dpr;
  const point = (name, o = {}) => batches[name] && batches[name].draw(camU, { sizeScale: dpr, ...o, alpha: (o.alpha === undefined ? 1 : o.alpha) * a });
  if (L.flights && k < 5) point('airports', { alpha: Math.min(1, (5 - k) / 2) });
  if (L.quakes) point('quakes');
  if (L.volcanoes) point('volcanoes', { alpha: Math.min(1, 0.45 + 5 / k) });
  if (L.power) point(k < 6 ? 'powerAll' : 'powerBig');
}

/** Read the panels' rectangles from the page. True when one moved, opened or closed (the names are then set again). */
function measurePanels() {
  const out = [];
  for (const id of PANELS) {
    const e = document.getElementById(id), r = e && e.getBoundingClientRect();
    if (r && r.width >= 2 && r.height >= 2) out.push([r.left - PANEL_PAD, r.top - PANEL_PAD, r.right + PANEL_PAD, r.bottom + PANEL_PAD]);
  }
  const sig = out.map((r) => r.map(Math.round).join(',')).join(';');
  if (sig === panelSig) return false;
  panelSig = sig; panelRects = out; labelsDirty = true;
  return true;
}

/** Where each inset goes this frame, or that it does not show: only on the sheet, only with names on, only near
 *  the whole-Earth scale (insets.js), each clear of the panels and of the one before it. */
function layoutInsets() {
  const alpha = cam.view === 'sheet' && state.layers.labels && data.political ? insetAlpha(cam.kmPerPx()) : 0;
  const taken = panelRects.slice();
  let changed = false;
  for (const I of insets) {
    if (I.layout(cam, alpha > 0 ? taken : null, alpha, cam.dpr)) changed = true;
    if (I.rect) taken.push([I.rect.x - INSET_PAD, I.rect.y - INSET_PAD, I.rect.x + I.rect.w + INSET_PAD, I.rect.y + I.rect.h + INSET_PAD]);
  }
  if (changed) earthDirty = labelsDirty = true;
}
/** An inset's own render target, the size of its frame in device pixels, and where that frame is in the drawing buffer. */
function insetTarget(I) {
  const pw = Math.round(I.rect.w * cam.dpr), ph = Math.round(I.rect.h * cam.dpr);
  if (!I.fb || I.pw !== pw || I.ph !== ph) {
    if (I.fb) { gl.deleteFramebuffer(I.fb); gl.deleteTexture(I.tex); }
    I.tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, I.tex); gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, pw, ph);
    I.fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, I.fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, I.tex, 0);
    I.pw = pw; I.ph = ph;
  }
  I.vx = Math.round(I.rect.x * cam.dpr); I.vy = canvas.height - Math.round(I.rect.y * cam.dpr) - ph;
}

const INSET_FONT = '600 9px -apple-system, "Helvetica Neue", "Segoe UI", system-ui, sans-serif';
/** Every name: the main map's, set clear of the panels and of the insets' frames; then each inset's own, by the same
 *  machinery through the inset's camera; then the frames. */
function drawNames() {
  const show = state.layers.labels, shown = insets.filter((I) => I.rect);
  labels.setBlocked(panelRects.concat(shown.map((I) => [I.rect.x - 3, I.rect.y - 3, I.rect.x + I.rect.w + 3, I.rect.y + I.rect.h + 3])));
  // under the main map's names: a thin outline around the ground each inset magnifies
  labels.underlay = shown.length ? (c, atlas) => { for (const I of shown) { const s = I.source(cam); c.globalAlpha = I.alpha; rule(c, atlas, s[0], s[1], s[2] - s[0], s[3] - s[1]); } c.globalAlpha = 1; } : null;
  labels.draw(cam, state.style, show);
  const c = labels.ctx, atlas = state.style === 'atlas';
  for (const I of insets) {
    if (!I.rect || !show) { I.labels.placed = []; continue; }
    // the title sits in the frame's top-left corner; the inset's names keep clear of it
    c.setTransform(labels.dpr, 0, 0, labels.dpr, 0, 0); c.font = INSET_FONT;
    if ('letterSpacing' in c) c.letterSpacing = '1.2px';
    const title = I.def.title.toUpperCase(), tw = Math.ceil(c.measureText(title).width) + 9, th = 14;
    if ('letterSpacing' in c) c.letterSpacing = '0px';
    I.tab = [0, 0, tw, th];
    I.labels.place(I.rect.x, I.rect.y, I.rect.w, I.rect.h, labels.dpr);
    I.labels.setBlocked([[0, 0, tw + 2, th + 2]]);
    I.labels.alpha = I.alpha;
    I.labels.draw(I.cam, state.style, true);
    c.setTransform(labels.dpr, 0, 0, labels.dpr, 0, 0); c.globalAlpha = I.alpha;
    c.fillStyle = atlas ? 'rgba(255,255,255,.86)' : 'rgba(4,10,20,.78)'; c.fillRect(I.rect.x, I.rect.y, tw, th);
    c.font = INSET_FONT; c.textBaseline = 'middle'; c.fillStyle = atlas ? 'rgba(28,26,30,.92)' : 'rgba(255,255,255,.9)';
    if ('letterSpacing' in c) c.letterSpacing = '1.2px';
    c.fillText(title, I.rect.x + 5, I.rect.y + th / 2 + 0.5);
    if ('letterSpacing' in c) c.letterSpacing = '0px';
    rule(c, atlas, I.rect.x - 0.5, I.rect.y - 0.5, I.rect.w + 1, I.rect.h + 1);
    c.globalAlpha = 1;
  }
  drawMarks();
}
/** The thin rule of an inset's frame and of its outline on the main map: one weight, one ink. */
function rule(c, atlas, x, y, w, h) {
  c.lineJoin = 'miter';
  c.lineWidth = 2.6; c.strokeStyle = atlas ? 'rgba(255,255,255,.55)' : 'rgba(0,6,16,.5)'; c.strokeRect(x, y, w, h);
  c.lineWidth = 1; c.strokeStyle = atlas ? 'rgba(28,26,30,.85)' : 'rgba(255,255,255,.85)'; c.strokeRect(x, y, w, h);
}

function drawMarks() {
  if (!state.layers.marks) return;
  const c = labels.ctx; c.setTransform(labels.dpr, 0, 0, labels.dpr, 0, 0);
  c.font = '600 10.5px -apple-system, "Helvetica Neue", sans-serif'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.lineWidth = 3; c.strokeStyle = 'rgba(0,6,16,.8)';
  const put = (lon, lat, text, col) => { const p = cam.project(lon, lat); if (!p) return; c.strokeText(text, p[0] + 10, p[1]); c.fillStyle = col; c.fillText(text, p[0] + 10, p[1]); };
  put(astro.sun.lon, astro.sun.lat, 'Sun overhead', '#ffd66b');
  put(astro.moon.lon, astro.moon.lat, 'Moon overhead', '#cfd8ea');
  if (fs.sats) for (const s of fs.sats) if (s.kind === 'station' && /^(ISS \(ZARYA\)|CSS \(TIANHE\))/.test(s.name)) { const p = cam.project(s.lon, s.lat, s.h); if (p) { c.strokeText(s.name.replace(/ \(.*/, ''), p[0] + 7, p[1]); c.fillStyle = '#ffeaa0'; c.fillText(s.name.replace(/ \(.*/, ''), p[0] + 7, p[1]); } }
}

function updateDash(force) {
  if (!ui) return;
  const d = { sun: astro.sun, moon: astro.moon, season: seasonName(astro.sun.dec, state.t), aloft: state.layers.flights ? dashCache.aloft : NaN };
  const nc = data.places ? nearestBig(astro.sun.lon, astro.sun.lat) : null; d.sunPlace = nc;
  if (fields.cpu.pop1) d.people = peopleBySun(fields.cpu.pop1, astro.sun);
  if (fields.has.ocean && fields.meta.climate) { dashCache.ice ||= iceExtents(fields); d.ice = { n: mixMonth(dashCache.ice.n, astro.month), s: mixMonth(dashCache.ice.s, astro.month) }; }
  if (fields.has.climate && fields.cpu.elev) { dashCache.temps ||= meanTemps(fields); d.meanT = mixMonth(dashCache.temps, astro.month); }
  if (fields.meta.human && fields.meta.human.co2) { const tot = fields.meta.human.co2.total_t; d.co2 = { perSec: tot / (365.25 * 86400), soFar: tot * astro.month.yearFrac }; }
  if (live.quakes && isNow()) {
    const rows = live.quakes.rows, t = state.t;
    const wk = rows.filter((q) => t - q[6] < 7 * DAY && t >= q[6]);
    d.quakes = { day: rows.filter((q) => t - q[6] < DAY && t >= q[6]).length, week: wk.length, top: wk.sort((a, b) => b[4] - a[4])[0] };
  } else d.quakeNote = live.status.quakes === 'unavailable' ? 'feed unavailable' : isNow() ? 'fetching…' : 'shown only at the present';
  ui.dashboard(d);
}
function nearestBig(lon, lat) {
  let best = null, bd = 900;
  for (const r of data.places.rows) { if (r[4] > 3) break; const dd = Cards.kmBetween(lon, lat, r[1], r[2]); if (dd < bd) { bd = dd; best = r[0]; } }
  return best;
}

// --------------------------------------------------------------------------------- interaction
let drag = null, hover = '', moved = 0;
canvas.addEventListener('pointerdown', (e) => { drag = [e.clientX, e.clientY]; moved = 0; canvas.setPointerCapture(e.pointerId); canvas.classList.add('dragging'); fly = null; });
canvas.addEventListener('pointermove', (e) => {
  if (drag) { const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; moved += Math.abs(dx) + Math.abs(dy); cam.pan(dx, dy); drag = [e.clientX, e.clientY]; earthDirty = labelsDirty = true; settledAt = performance.now(); }
  const V = viewAt(e.clientX, e.clientY), ll = V.cam.unproject(V.x, V.y);
  if (ll) { const z = fields.elevation(ll[0], ll[1]); hover = `${Cards.coord(ll[0], ll[1])}${Number.isFinite(z) ? ` · ${Math.round(z).toLocaleString('en-US')} m` : ''}`; } else hover = '';
});
canvas.addEventListener('pointerup', (e) => { canvas.classList.remove('dragging'); if (drag && moved < 5) click(e.clientX, e.clientY); drag = null; saveHash(); });
canvas.addEventListener('wheel', (e) => { e.preventDefault(); fly = null; cam.zoom(Math.exp(e.deltaY * (e.ctrlKey ? 0.01 : 0.0016)), e.clientX, e.clientY); earthDirty = labelsDirty = true; settledAt = performance.now(); saveHash(); }, { passive: false });
canvas.addEventListener('dblclick', (e) => { const V = viewAt(e.clientX, e.clientY), ll = V.cam.unproject(V.x, V.y); if (ll) flyTo(ll[0], ll[1], cam.kmPerPx() / 2.5); });

/** Which view of the atlas a window point is in: an inset that is showing, or the main map. x, y: the point in that view's own coordinates. */
function viewAt(x, y) {
  for (const I of insets) if (I.alpha > 0.5 && I.holds(x, y)) return { cam: I.cam, labels: I.labels, x: x - I.rect.x, y: y - I.rect.y, inset: I };
  return { cam, labels, x, y, inset: null };
}
/** What a click at a window point selects: the reference its card opens from (openRef), or null off the Earth.
 *  The same rule in every view: a name, then a marked point, then the ground. */
function pick(wx, wy) {
  const L = state.layers, V = viewAt(wx, wy), vc = V.cam, x = V.x, y = V.y, vk = vc.kmPerPx();
  const lab = L.labels ? V.labels.hit(x, y) : null;
  if (lab) return lab.ref;
  vc.beginFrame();
  let best = null, bd = 10;
  const near = (lon, lat, h, ref) => { const p = vc.project(lon, lat, h); if (!p) return; const d = Math.hypot(p[0] - x, p[1] - y); if (d < bd) { bd = d; best = ref; } };
  if (L.quakesLive && live.quakes && isNow()) for (const q of live.quakes.rows) near(q[1], q[2], 0, ['quake', q, true]);
  if (L.quakes && data.quakes) for (const q of data.quakes.rows) near(q[1], q[2], 0, ['quake', q, false]);
  if (L.volcanoes && data.volcanoes) for (const v of data.volcanoes.rows) near(v[1], v[2], 0, ['volcano', v]);
  if (L.power && data.power) { const W = data.power, min = vk < 6 ? 0 : 1000; for (let i = 0; i < W.mw.length; i++) if (W.mw[i] >= min) near(W.lon[i], W.lat[i], 0, ['plant', i]); }
  if (L.flights && data.air && vk < 5) for (const a of data.air.airports) near(a.lon, a.lat, 0, ['airport', a]);
  if (fs.sats) for (const s of fs.sats) near(s.lon, s.lat, s.h, ['sat', s]);
  if (best) return best;
  const ll = vc.unproject(x, y);
  if (!ll) return null;
  // the ground: a state's card on the political sheet seen from afar, the probe otherwise. An inset belongs to the
  // whole-Earth sheet, so its ground answers as the main map's does at that moment.
  if (state.style === 'atlas' && cam.kmPerPx() > 9) { const c = data.countryAt(ll[0], ll[1]); if (c) return ['country', c]; }
  return ['probe', ll];
}
function click(x, y) { const ref = pick(x, y); if (ref) openRef(ref); else app.closeCard(); }

// ---------------------------------------------------------------------------------- URL state
function saveHash() {
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const c = cam.center(), p = new URLSearchParams();
    if (state.clock !== 'live') p.set('t', new Date(state.t).toISOString().slice(0, 16) + 'Z');
    p.set('v', cam.view); p.set('s', state.style); p.set('ll', `${c[0].toFixed(2)},${c[1].toFixed(2)}`); p.set('km', cam.kmPerPx().toFixed(2));
    if (state.lens !== 'none') p.set('lens', state.lens);
    p.set('on', Object.keys(state.layers).filter((k) => state.layers[k]).join(','));
    history.replaceState(null, '', '#' + p.toString().replace(/%2C/g, ',').replace(/%3A/g, ':'));
  }, 400);
}
function loadHash() {
  const p = new URLSearchParams((location.hash || '').slice(1) || location.search.slice(1));
  if (FROZEN) { state.t = FROZEN_T; state.clock = 'paused'; }
  if (p.get('t')) { const t = Date.parse(p.get('t')); if (Number.isFinite(t)) { state.t = t; state.clock = 'paused'; } }
  if (p.get('s') === 'atlas') state.style = 'atlas';
  if (p.get('lens') && LENSES[p.get('lens')]) state.lens = p.get('lens');
  if (p.get('on') !== null) { const on = new Set(p.get('on').split(',')); for (const k in state.layers) state.layers[k] = on.has(k); }
  return p;
}

/** Development aid: composite the GL canvas and the label canvas and post the frame to build/serve.py. */
async function shot(name = 'frame.jpg', crop) {
  const c = document.createElement('canvas');
  const [x, y, w, h] = crop ? crop.map((v) => Math.round(v * cam.dpr)) : [0, 0, canvas.width, canvas.height];
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.drawImage(canvas, x, y, w, h, 0, 0, w, h); g.drawImage(labels.canvas, x, y, w, h, 0, 0, w, h);
  const r = await fetch('/__shot/' + name, { method: 'POST', body: c.toDataURL('image/jpeg', 0.9) });
  return `${await r.text()} ${w}x${h} dpr ${cam.dpr}`;
}

/** The names an inset can show: every country (a state is placed by its own geometry wherever it is), and the
 *  seas, cities and landforms near its ground. Fresh objects: a label layer keeps its working state on its items. */
function insetItems(def) {
  const all = data.labelItems(), dLat = def.spanKm[1] / 222.4 + 4, dLon = def.spanKm[0] / 222.4 / Math.max(0.2, Math.cos(def.center[1] * D2R)) + 6;
  const out = all.filter((it) => it.cls === 'country' || (Math.abs(it.lat - def.center[1]) < dLat && Math.abs(((it.lon - def.center[0] + 540) % 360) - 180) < dLon));
  out.geo = all.geo;
  return out;
}

/** Every field and every lazy table the current layers need has arrived, the focus window included when its layer is on. */
function allLoaded() {
  const h = fields.has;
  if (state.layers.detail) detail.update(cam, !fly, true, state.layers.lights && state.layers.daylight ? astro.sun : null, !!fly);            // the view may have moved since the last frame
  return h.water && h.climate && h.ocean && h.relief && h.elev && h.countries && !!fields.cpu.lanes && !!fields.cpu.pop1 && !!fields.cpu.co21 && pending.size === 0
    && !(state.layers.detail && detail.busy);
}

/** The frozen frame: wait for the data, then run a fixed number of seeded steps and stop. */
async function frozenFrame() {
  let now = lastFrame + 1e6;                                   // far past any "settled" timer
  const deadline = performance.now() + 120000;
  for (;;) {
    fs.hold = true; tick(now += 1000);                         // hold: nothing random is consumed while waiting
    if (fs.detail === 'full' && allLoaded()) break;
    if (performance.now() > deadline) throw new Error('frozen frame: the fields never finished loading');
    await new Promise((r) => setTimeout(r, 150));
  }
  await document.fonts.ready;
  // advance the tracers without drawing (a software renderer takes half a second a frame), then draw once
  resetTracers();
  const L = state.layers;
  for (let i = 0; i < FROZEN_STEPS; i++) {
    if (L.currents) tracers.currents.step(cam, samplers.currents, 1);
    if (L.wind) tracers.wind.step(cam, samplers.wind, 1);
    if (L.jet) tracers.jet.step(cam, samplers.jet, 1);
    if (L.ships) tracers.ships.step(cam, samplers.lanes, 1);
  }
  fs.hold = false; earthDirty = labelsDirty = true; fs.uiAt = fs.dashAt = 0;
  tick(now += 16.7);
  // the last tick wrote the panels after it set the names: if a panel changed size in it, set them once more
  // (tracers drawn where they stand, not stepped, so the frame stays the same frame)
  for (let i = 0; i < 3 && measurePanels(); i++) { fs.still = true; earthDirty = labelsDirty = true; fs.uiAt = fs.dashAt = 0; tick(now += 16.7); fs.still = false; }
  window.__FRAME_READY = true;
}

// --------------------------------------------------------------------------------------- boot
(async () => {
  try {
    const p = loadHash();
    if (p.get('v') === 'sheet') cam.view = 'sheet';
    window.addEventListener('resize', resize);
    resize(); cam.home();
    astroUpdate();
    // open on the daylit side with dusk in view: the first frame should show day, night and the line between them
    if (p.get('ll')) { const [lo, la] = p.get('ll').split(',').map(Number); cam.lookAt(lo, la); }
    else if (cam.view === 'globe') { cam.lon = ((astro.sun.lon + 42 + 540) % 360) - 180; cam.lat = 18; }
    if (p.get('km')) cam.setKmPerPx(+p.get('km'));
    astroUpdate();
    ui = new UI(app);
    ui.syncControls(); ui.clock();
    await loadVersion();
    bootMsg('Compiling the planet…');
    [progs.lines, progs.points] = await Promise.all([program(gl, 'lines'), program(gl, 'points'), earth.init()]);
    bootMsg('Reading the fields…');
    await Promise.all([fields.boot(state.t), data.loadCore()]);
    const lut = paletteCanvas();
    fields.tex.lut = texFromImage(gl, lut, { format: 'rgb', mips: false });
    gl.bindTexture(gl.TEXTURE_2D, fields.tex.lut); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    samplers = makeSamplers(fields, () => astro.month);
    buildStatic(); buildTracers();
    labels.setItems(data.labelItems());
    for (const I of insets) I.labels.setItems(insetItems(I.def));
    for (const id in state.layers) if (state.layers[id]) ensureLayer(id);
    if (LENSES[state.lens] && LENSES[state.lens].static) { pending.add('lens'); fields.loadStatic(LENSES[state.lens].static).then(() => { pending.delete('lens'); earthDirty = true; }); }
    ui.syncControls(); feedStatus();
    const boot = document.getElementById('boot'); boot.classList.add('gone'); setTimeout(() => boot.remove(), FROZEN ? 0 : 900);
    if (!FROZEN) setInterval(() => { if (state.layers.quakesLive && isNow()) live.loadQuakes(); if (state.layers.aurora && isNow()) live.loadAurora(); }, 10 * 60000);
    window.ATLAS = { ...app, gl, astro, labels, tracers, batches, shot, insets, pickAt: pick, panels: () => panelRects, step: (n = 1) => { for (let i = 0; i < n; i++) tick(Math.max(lastFrame + 16.7, FROZEN ? 0 : performance.now())); return n; }, get flights() { return flights; }, redraw: () => { earthDirty = labelsDirty = true; } };
    window.ATLAS.refView = (lon, lat, dist, discFrac) => { cam.refView(lon, lat, dist, discFrac); earthDirty = labelsDirty = true; resetTracers(); };
    window.ATLAS.stdView = () => { cam.stdView(); earthDirty = labelsDirty = true; resetTracers(); };
    window.ATLAS.settled = () => fs.detail === 'full' && allLoaded();
    if (FROZEN) await frozenFrame(); else requestAnimationFrame(frame);
    try { sessionStorage.removeItem('atlas-gl-retry'); } catch (e) { /* storage may be unavailable */ }
  } catch (e) {
    // A browser can take the GL context away (GPU process restart, a software renderer starting
    // up). Nothing drawn so far can be trusted, so start again; three tries, then say so.
    if (gl.isContextLost() && retryAfterContextLoss()) return;
    bootMsg(String(e.message || e)); console.error(e);
  }
})();

function retryAfterContextLoss() {
  let n = 0;
  try { n = +(sessionStorage.getItem('atlas-gl-retry') || 0); sessionStorage.setItem('atlas-gl-retry', String(n + 1)); } catch (e) { return false; }
  if (n >= 3) return false;
  bootMsg('The graphics context was lost. Starting again…');
  setTimeout(() => location.reload(), 400 + 600 * n);
  return true;
}
canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); });
canvas.addEventListener('webglcontextrestored', () => location.reload());
