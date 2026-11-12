// The year at a place: twelve monthly means read from the fields the page already holds, the Köppen-Geiger class
// they give by the standard rule, a few sentences written by rule, and a small chart. This is the atlas's OWN
// description of a location: it needs no network, and every number in it is computed here from the climatology
// (1991-2020) or from the Sun's geometry. Nothing is shown that was not computed: a place whose fields have not
// loaded, or where a field is silent, gets `ok: false` and a reason.
//
// The functions are pure (the field store is an argument) so that build/test_app_math.mjs can run them.

import { sun, dayLength } from './astro.js';

export const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];            // a typical year: February has 28
// The chart's two series. Checked for the dark panel with the dataviz validator (lightness band, colour-vision separation, contrast).
export const CHART = { temp: '#c0842c', rain: '#5b8fe0' };

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const sum = (a) => a.reduce((p, q) => p + q, 0);
const argmax = (a) => a.reduce((b, v, i) => (v > a[b] ? i : b), 0);
const argmin = (a) => a.reduce((b, v, i) => (v < a[b] ? i : b), 0);
const f1 = (v) => (Math.round(v * 10) / 10 === 0 ? 0 : v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).replace('-', '−');
const f0 = (v) => Math.round(v).toLocaleString('en-US');
/** A length of day in words. */
export const hoursText = (h) => { if (h >= 23.99) return '24 hours'; if (h <= 0.01) return 'none'; const m = Math.round(h * 60); return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} m`; };

const decs = new Map();          // year -> the Sun's declination at 12 UTC on each day of each month
/** Mean length of day in each month at a latitude, hours (sunrise and sunset at -0.833 deg, as dayLength). */
export function daylightMonthly(lat, year) {
  if (!decs.has(year)) decs.set(year, DAYS.map((n, m) => Array.from({ length: n }, (_, d) => sun(Date.UTC(year, m, d + 1, 12)).dec)));
  return decs.get(year).map((mo) => sum(mo.map((dec) => dayLength(lat, dec))) / mo.length);
}

/**
 * The twelve months at a point, from the field store. Air temperature is the field's sea-level value taken to
 * the ground's height with the same lapse rate as cards.airTemp() and the shader (the height is never below zero).
 * `water`: is this a place on water? A card that knows says so (a city on the shore sits in a water cell of the
 * 20 km mask and is still a city); left out, the water mask answers, as for a bare point.
 * Returns { ok: false, why } if any month of temperature or precipitation, or the elevation, is not in memory.
 */
export function monthlySeries(F, lon, lat, year, water = F.waterFrac(lon, lat) > 0.5) {
  if (!F.has || !F.has.climate || !F.meta || !F.meta.climate) return { ok: false, why: 'The climate fields are still loading.' };
  const zRaw = F.elevation(lon, lat);
  if (!Number.isFinite(zRaw)) return { ok: false, why: 'The elevation field is still loading.' };
  const z = Math.max(0, zRaw), lapse = F.meta.climate.lapse_K_per_km;
  const t = [], pday = [], sst = [];
  for (let m = 0; m < 12; m++) {
    const ms = { i0: m, i1: m, f: 0 };                               // the month's own keyframe, no blend
    const t0 = F.climate('t0', lon, lat, ms), p = F.climate('precip', lon, lat, ms);
    if (!Number.isFinite(t0) || !Number.isFinite(p)) return { ok: false, why: 'The climate fields hold no value at this point.' };
    t.push(t0 - lapse * z / 1000); pday.push(Math.max(0, p));
    sst.push(water ? F.climate('sst', lon, lat, ms) : NaN);
  }
  return { ok: true, lon, lat, z, water, t, pday, pmm: pday.map((v, m) => v * DAYS[m]), day: daylightMonthly(lat, year), sst: sst.every(Number.isFinite) ? sst : null };
}

/** A class's name in the words of Peel et al.'s table: the main group, the seasonal precipitation, the heat. */
export function koppenName(code) {
  const fixed = { Af: 'Tropical rainforest', Am: 'Tropical monsoon', Aw: 'Tropical savanna', BWh: 'Hot desert', BWk: 'Cold desert', BSh: 'Hot steppe', BSk: 'Cold steppe', ET: 'Polar tundra', EF: 'Polar ice cap' };
  if (fixed[code]) return fixed[code];
  const g = { C: 'Temperate', D: 'Cold' }[code[0]], p = { s: 'dry summer', w: 'dry winter', f: 'no dry season' }[code[1]];
  const h = { a: 'hot summer', b: 'warm summer', c: 'cold summer', d: 'very cold winter' }[code[2]];
  return g && p && h && code.length === 3 ? `${g}, ${p}, ${h}` : null;
}

/**
 * The Köppen-Geiger class of twelve monthly mean temperatures (deg C) and precipitation totals (mm), by the
 * criteria of Peel, Finlayson & McMahon (2007, Hydrol. Earth Syst. Sci. 11, 1633-1644, table 1): arid first, the
 * 0 deg C line between C and D, summer the warmer of April-September and October-March. Where a dry summer and a
 * dry winter both qualify, the drier half of the year names it.
 */
export function koppen(t, pmm) {
  if (!t || !pmm || t.length !== 12 || pmm.length !== 12 || ![...t, ...pmm].every(Number.isFinite)) return null;
  const mean = (a) => sum(a) / a.length, pick = (a, idx) => idx.map((i) => a[i]);
  const MAT = mean(t), Thot = Math.max(...t), Tcold = Math.min(...t), MAP = sum(pmm), Pdry = Math.min(...pmm);
  const AS = [3, 4, 5, 6, 7, 8], OM = [9, 10, 11, 0, 1, 2];
  const [su, wi] = mean(pick(t, AS)) >= mean(pick(t, OM)) ? [AS, OM] : [OM, AS];
  const Ps = sum(pick(pmm, su)), Pw = sum(pick(pmm, wi));
  const Pth = Pw >= 0.7 * MAP ? 2 * MAT : Ps >= 0.7 * MAP ? 2 * MAT + 28 : 2 * MAT + 14;
  let code;
  if (MAP < 10 * Pth) code = (MAP < 5 * Pth ? 'BW' : 'BS') + (MAT >= 18 ? 'h' : 'k');
  else if (Tcold >= 18) code = Pdry >= 60 ? 'Af' : Pdry >= 100 - MAP / 25 ? 'Am' : 'Aw';
  else if (Thot > 10) {
    const Psdry = Math.min(...pick(pmm, su)), Pswet = Math.max(...pick(pmm, su)), Pwdry = Math.min(...pick(pmm, wi)), Pwwet = Math.max(...pick(pmm, wi));
    let s = Psdry < 40 && Psdry < Pwwet / 3, w = Pwdry < Pswet / 10;
    if (s && w) { if (Ps > Pw) s = false; else w = false; }
    const n10 = t.filter((v) => v > 10).length, cold = Tcold <= 0;
    code = (cold ? 'D' : 'C') + (s ? 's' : w ? 'w' : 'f') + (Thot >= 22 ? 'a' : n10 >= 4 ? 'b' : cold && Tcold < -38 ? 'd' : 'c');
  } else code = Thot > 0 ? 'ET' : 'EF';
  return { code, name: koppenName(code) };
}

/** Two to four sentences about the year at a place, written by rule from a monthlySeries() result. */
export function yearSentences(s) {
  const out = [], M = MONTH_NAMES;
  const hot = argmax(s.t), cold = argmin(s.t);
  if (s.t[hot] - s.t[cold] >= 3) out.push(`${M[hot]} is the warmest month, with a mean air temperature of ${f1(s.t[hot])} °C; ${M[cold]} is the coldest, at ${f1(s.t[cold])} °C.`);
  else if (s.t[hot] - s.t[cold] < 0.05) out.push(`Mean air temperature is ${f1(s.t[hot])} °C in every month.`);
  else out.push(`Mean air temperature changes little through the year: ${f1(s.t[cold])} °C in ${M[cold]}, ${f1(s.t[hot])} °C in ${M[hot]}.`);
  const year = sum(s.pmm), wet = argmax(s.pmm), dry = argmin(s.pmm);
  // the precipitation field resolves about 250 km (GPCP, 2.5 degrees): the sentence says so, because a dry coast under wet mountains reads as their mean
  if (year < 25) out.push(`Almost no precipitation falls here: about ${f0(year)} mm in a typical year.`);
  else out.push(`About ${f0(year >= 200 ? Math.round(year / 10) * 10 : year)} mm of precipitation falls in a typical year, as a mean over some 250 km. ${M[wet]} is the wettest month (${f0(s.pmm[wet])} mm) and ${M[dry]} the driest (${f0(s.pmm[dry])} mm).`);
  const long = argmax(s.day), short = argmin(s.day);
  if (s.day[long] - s.day[short] < 0.5) out.push(`The day is close to ${hoursText((s.day[long] + s.day[short]) / 2)} long all year.`);
  else {
    const a = s.day[short] <= 0.01 ? `There is no daylight in ${M[short]} (polar night)` : `Daylight averages ${hoursText(s.day[short])} a day in ${M[short]}`;
    const b = s.day[long] >= 23.99 ? `the Sun does not set in ${M[long]}` : `${hoursText(s.day[long])} in ${M[long]}`;
    out.push(`${a} and ${b}.`);
  }
  if (s.sst) { const w = argmax(s.sst), c = argmin(s.sst); out.push(`The water’s surface is warmest in ${M[w]} (${f1(s.sst[w])} °C) and coldest in ${M[c]} (${f1(s.sst[c])} °C).`); }
  return out;
}

/** Round values inside [lo, hi] to label an axis with: about n of them, never fewer than one. */
export function ticks(lo, hi, n = 3) {
  const span = Math.max(hi - lo, 1e-9), raw = span / n, pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((v) => v >= raw * 0.999), out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + step * 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6 + 0);
  return out.length ? out : [Math.round(((lo + hi) / 2) * 10) / 10];
}

/**
 * The chart: two small panels on one row of months, each with its own scale and its own label: the mean air
 * temperature as a line above, the month's precipitation as bars below. `now`: the month to mark (0-11) or -1.
 * Every month carries its three values as a native tooltip. Returns an SVG string of numbers only.
 */
export function climateChart(s, now) {
  const W = 288, L = 30, R = 4, slot = (W - L - R) / 12, x = (m) => L + slot * (m + 0.5);
  const T0 = 16, T1 = 62, P0 = 86, P1 = 132;                         // the two panels' tops and bottoms
  // each panel's scale is its own data's range with a little air; the labelled values are round ones inside it
  const tmin = Math.min(...s.t), tmax = Math.max(...s.t), pad = Math.max(0.8, 0.12 * (tmax - tmin)), tlo = tmin - pad, thi = tmax + pad;
  const tt = ticks(tlo, thi, 3);
  const yT = (v) => T1 - ((v - tlo) / (thi - tlo)) * (T1 - T0);
  const phi = Math.max(...s.pmm, 1) * 1.06, pt = ticks(0, phi, 2);
  const yP = (v) => P1 - (v / phi) * (P1 - P0);
  const grid = (y) => `<line class="cg" x1="${L}" x2="${W - R}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/>`;
  const lab = (y, v) => `<text class="ct" x="${L - 5}" y="${(y + 3).toFixed(1)}" text-anchor="end">${esc(String(v).replace('-', '−'))}</text>`;
  let g = '';
  if (now >= 0) g += `<rect class="cnow" x="${(x(now) - slot / 2).toFixed(1)}" y="${T0 - 6}" width="${slot.toFixed(1)}" height="${P1 - T0 + 12}" rx="3"/>`;
  g += `<rect x="${L}" y="3" width="8" height="2.5" rx="1" fill="${CHART.temp}"/><text class="ch" x="${L + 12}" y="7">Mean air temperature, °C</text>`;
  g += `<rect x="${L}" y="${P0 - 13}" width="8" height="6" rx="1.5" fill="${CHART.rain}"/><text class="ch" x="${L + 12}" y="${P0 - 7}">Precipitation, mm a month</text>`;
  for (const v of tt) g += grid(yT(v)) + lab(yT(v), v);
  for (const v of pt) g += grid(yP(v)) + lab(yP(v), v);
  const bw = Math.min(24, slot - 5);
  for (let m = 0; m < 12; m++) {
    const h = P1 - yP(s.pmm[m]), r = Math.min(4, h, bw / 2), x0 = x(m) - bw / 2;
    if (h > 0.2) g += `<path fill="${CHART.rain}" d="M${x0.toFixed(1)} ${P1}v${(-(h - r)).toFixed(1)}q0 ${(-r).toFixed(1)} ${r.toFixed(1)} ${(-r).toFixed(1)}h${(bw - 2 * r).toFixed(1)}q${r.toFixed(1)} 0 ${r.toFixed(1)} ${r.toFixed(1)}v${(h - r).toFixed(1)}z"/>`;
  }
  g += `<polyline fill="none" stroke="${CHART.temp}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="${s.t.map((v, m) => `${x(m).toFixed(1)},${yT(v).toFixed(1)}`).join(' ')}"/>`;
  if (now >= 0) g += `<circle class="cdot" cx="${x(now).toFixed(1)}" cy="${yT(s.t[now]).toFixed(1)}" r="4" fill="${CHART.temp}"/>`;
  for (let m = 0; m < 12; m++) {
    g += `<text class="${m === now ? 'cm on' : 'cm'}" x="${x(m).toFixed(1)}" y="${P1 + 12}" text-anchor="middle">${MONTH_NAMES[m][0]}</text>`;
    g += `<rect class="chit" x="${(x(m) - slot / 2).toFixed(1)}" y="${T0 - 6}" width="${slot.toFixed(1)}" height="${P1 - T0 + 20}"><title>${MONTH_NAMES[m]}: ${f1(s.t[m])} °C, ${f0(s.pmm[m])} mm, ${hoursText(s.day[m])} of daylight</title></rect>`;
  }
  return `<svg class="clim" viewBox="0 0 ${W} ${P1 + 16}" role="img" aria-label="Mean air temperature and precipitation in each month of a typical year">${g}</svg>`;
}

/** The same twelve months as a table: every number the chart draws, and the length of day. */
export function climateTable(s, now) {
  return `<details class="climtab"><summary>The twelve months as a table</summary><table><thead><tr><th>Month</th><th>°C</th><th>mm</th><th>Daylight</th></tr></thead><tbody>${
    MONTH_NAMES.map((n, m) => `<tr${m === now ? ' class="on"' : ''}><td>${n}</td><td>${f1(s.t[m])}</td><td>${f0(s.pmm[m])}</td><td>${hoursText(s.day[m])}</td></tr>`).join('')}</tbody></table></details>`;
}
