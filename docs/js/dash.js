// Derived indicators for the "Planet now" panel. Each is an integral of fields the atlas
// already shows - the population field under the terminator, the ice field over the sea -
// so the panel cannot disagree with the globe.

import { D2R } from './astro.js?v=20261110T205316Z';
import { R_KM } from './camera.js?v=20261110T205316Z';

/** People in daylight / twilight / night, and in waking hours, from 1-degree population counts. */
export function peopleBySun(pop1, sunNow) {
  const out = { day: 0, twilight: 0, night: 0, awake: 0, total: 0 };
  const [sx, sy, sz] = sunNow.vec;
  for (let j = 0; j < 180; j++) {
    const lat = (89.5 - j) * D2R, cl = Math.cos(lat), sl = Math.sin(lat);
    for (let i = 0; i < 360; i++) {
      const p = pop1[j * 360 + i];
      if (!p) continue;
      const lonDeg = -179.5 + i, lon = lonDeg * D2R;
      const mu = cl * Math.cos(lon) * sx + cl * Math.sin(lon) * sy + sl * sz;
      if (mu > 0) out.day += p; else if (mu > -0.309) out.twilight += p; else out.night += p;      // sin(-18 deg)
      const lst = (((12 + (lonDeg - sunNow.lon) / 15) % 24) + 24) % 24;
      if (lst >= 7 && lst < 23) out.awake += p;
      out.total += p;
    }
  }
  return out;
}

/** Sea-ice extent (million km2, cells with >= 15% cover) per month and hemisphere, from the shipped field.
 *  The valid channel is 255 for the sea and 200 for inland water (the Great Lakes, the Caspian): lake ice
 *  is drawn but not counted, because the NSIDC index this is held against is a sea-ice index. */
export function iceExtents(fields) {
  const f = fields.cpu.oceanA, enc = fields.meta.climate.encodings.ice;
  const thr = ((0.15 - enc.lo) / (enc.hi - enc.lo)) * 255;
  const cellLat = Math.PI / f.h, cellLon = (2 * Math.PI) / f.w;
  const n = new Float64Array(12), s = new Float64Array(12);
  for (let m = 0; m < 12; m++) {
    for (let j = 0; j < f.h; j++) {
      const lat = Math.PI / 2 - (j + 0.5) * cellLat;
      const area = R_KM * R_KM * cellLon * (Math.sin(lat + cellLat / 2) - Math.sin(lat - cellLat / 2));
      let c = 0;
      const o = (m * f.h + j) * f.w * 4;
      for (let i = 0; i < f.w; i++) if (f.d[o + i * 4 + 2] > 227 && f.d[o + i * 4 + 1] >= thr) c++;
      if (lat > 0) n[m] += c * area; else s[m] += c * area;
    }
    n[m] /= 1e6; s[m] /= 1e6;
  }
  return { n, s };
}

/** Area-weighted global mean 2 m air temperature per month, from the same field and lapse correction the shader uses. */
export function meanTemps(fields) {
  const f = fields.cpu.atmoA, enc = fields.meta.climate.encodings.t0, lapse = fields.meta.climate.lapse_K_per_km;
  const out = new Float64Array(12);
  // the terrain as the 1-degree temperature field sees it: the mean of the fine elevation over each cell
  const E = fields.cpu.elev, z = new Float32Array(f.w * f.h), sx = E.w / f.w, sy = E.h / f.h;
  for (let j = 0; j < f.h; j++) for (let i = 0; i < f.w; i++) {
    let acc = 0, cnt = 0;
    for (let y = Math.floor(j * sy); y < (j + 1) * sy; y += 2) for (let x = Math.floor(i * sx); x < (i + 1) * sx; x += 2) { acc += Math.max(0, (E.d[y * E.w + x] / 65535) * 20000 - 11000); cnt++; }
    z[j * f.w + i] = acc / cnt;
  }
  for (let m = 0; m < 12; m++) {
    let num = 0, den = 0;
    for (let j = 0; j < f.h; j++) {
      const w = Math.cos((89.5 - j) * D2R);
      for (let i = 0; i < f.w; i++) {
        const t0 = enc.lo + (enc.hi - enc.lo) * f.d[((m * f.h + j) * f.w + i) * 4 + 2] / 255;
        num += (t0 - lapse * z[j * f.w + i] / 1000) * w; den += w;
      }
    }
    out[m] = num / den;
  }
  return out;
}

export const mixMonth = (arr, ms) => arr[ms.i0] * (1 - ms.f) + arr[ms.i1] * ms.f;
