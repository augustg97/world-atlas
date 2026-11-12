// Draws the substrate: one full-screen triangle through shaders/earth.frag.glsl.

import { program, setUniforms } from './gl.js?v=20261112T020725Z';
import { UNIT } from './fields.js?v=20261112T020725Z';
import { gmstDeg, D2R } from './astro.js?v=20261112T020725Z';

export const LENSES = {
  none: { id: 0 },
  temp: { id: 1, row: 0, alpha: 0.80 }, precip: { id: 2, row: 1, alpha: 0.80 }, slp: { id: 3, row: 2, alpha: 0.72 },
  wind: { id: 4, row: 3, alpha: 0.72 }, cloud: { id: 5, row: 4, alpha: 0.75 }, sst: { id: 6, row: 5, alpha: 0.88 },
  ice: { id: 7, row: 6, alpha: 0.90 }, pop: { id: 8, row: 7, alpha: 0.92, static: 'pop' }, co2: { id: 9, row: 8, alpha: 0.92, static: 'co2' },
  ships: { id: 10, row: 9, alpha: 0.95, static: 'ships' }, elev: { id: 11, row: 10, alpha: 0.85 }, green: { id: 12, row: 11, alpha: 0.85 },
  solar: { id: 13, row: 12, alpha: 0.55 }, lights: { id: 14, row: 13, alpha: 0.95 },
};

export class Earth {
  constructor(gl, fields) { this.gl = gl; this.fields = fields; }
  async init() {
    this.prog = await program(this.gl, 'earth');
    this.vao = this.gl.createVertexArray();
    return this;
  }

  /** Vertical exaggeration of the relief shading at this zoom. Stated in the About panel. */
  static reliefK(kmPerPx, style) {
    // the slope field is a 5 km mean; from orbit real slopes are invisible without exaggeration,
    // close in they need much less
    const t = Math.max(0, Math.min(1, Math.log(kmPerPx / 1.5) / Math.log(20 / 1.5)));
    const land = 5 + 9 * t;
    return { land, sea: style === 'atlas' ? land * 0.75 : 0 };
  }

  /** blend: leave the caller's blending on (an inset fading in over the map); the substrate is otherwise drawn opaque. */
  draw(state, cam, astro, detail, blend = false) {
    const gl = this.gl, f = this.fields, p = this.prog;
    gl.useProgram(p.p);
    f.bind();
    const enc = f.meta.climate ? f.meta.climate.encodings : null;
    const e = (k) => (enc && enc[k] ? [enc[k].lo, enc[k].hi] : [0, 1]);
    const lens = LENSES[state.lens] || LENSES.none;
    if (lens.static) f.setLens2D(lens.static);
    const k = Earth.reliefK(cam.kmPerPx(), state.style);
    this.relief = k;
    const L = state.layers;
    const u = {
      ...cam.uniforms(),
      uAlbA: UNIT.albA, uAlbB: UNIT.albB, uRelief: UNIT.relief, uWaterNight: UNIT.waterNight, uElev: UNIT.elev, uClouds: UNIT.clouds,
      uAtmoA: UNIT.atmoA, uAtmoB: UNIT.atmoB, uOceanA: UNIT.oceanA, uCountries: UNIT.countries, uLens2D: UNIT.lens2D, uLut: UNIT.lut,
      uLive: UNIT.live, uAurora: UNIT.aurora,
      uAlbMix: astro.month.f, uMonth: [astro.month.i0, astro.month.f, astro.month.i1],
      uSun: astro.sun.vec, uMoon: astro.moon.vec, uMoonLit: astro.moon.lit,
      uHours: (state.t / 3600000) % 100000, uGmst: gmstDeg(state.t) * D2R,
      uStyle: state.style === 'atlas' ? 1 : 0,
      uLens: lens.id, uLensAlpha: lens.alpha || 0, uLensRow: lens.row || 0,
      uHasRelief: f.has.relief ? 1 : 0, uHasElev: f.has.elev ? 1 : 0, uHasLive: f.has.live && L.today ? 1 : 0,
      uHasClimate: f.has.climate ? 1 : 0, uHasOcean: f.has.ocean ? 1 : 0, uHasCountries: f.has.countries ? 1 : 0,
      uHasWater: f.has.water ? 1 : 0, uHasAurora: f.has.aurora && L.aurora && state.atNow ? 1 : 0, uHasCloudT: f.has.cloudT ? 1 : 0, uHasGrain: f.has.cloudGrain ? 1 : 0, uHasGrain2: f.has.cloudGrain2 ? 1 : 0,
      uCloudsOn: L.clouds ? 1 : 0, uNightOn: L.lights ? 1 : 0, uAtmoOn: L.air ? 1 : 0, uDaylightOn: L.daylight ? 1 : 0, uIceOn: L.ice ? 1 : 0,
      uReliefLand: k.land, uReliefSea: k.sea,
      uLapse: f.meta.climate ? f.meta.climate.lapse_K_per_km : 6.5,
      uSelCountry: state.selCountry || 0,
      uE_u10: e('u10'), uE_v10: e('v10'), uE_t0: e('t0'), uE_slp: e('slp'), uE_cloud: e('cloud'), uE_precip: e('precip'), uE_sst: e('sst'), uE_ice: e('ice'),
      uE_deck: e('deck'), uE_cu: e('cu'), uE_light: e('light'),
      // the focus window: both weights are 0 unless the layer is on and a window has loaded
      ...(detail ? detail.uniforms(performance.now()) : { uDetAlb: UNIT.detAlb, uDetElev: UNIT.detElev, uDetWin: [0, 0, 1, 1], uDetAlbW: 0, uDetElevW: 0, uDetNightW: 0, uDetWaterW: 0, uDetWaterC: [0.10, 0.15, 0.20], uDetS2: 0, uDetAlbLod: 0, uDetElevPx: [1, 1], uDetElevM: [1000, 1000] }),
    };
    setUniforms(gl, p, u);
    gl.bindVertexArray(this.vao);
    if (!blend) gl.disable(gl.BLEND);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}
