// Sun and Moon from the clock. Low-precision ephemerides (Astronomical Almanac / Meeus):
// Sun to about 0.01 deg, Moon to about 0.3 deg - both far below a pixel of terminator at any
// shipped scale. Scored against JPL Horizons by Research/modeling/audit_sun.py.
//
// Everything is returned in the Earth-fixed frame the renderer uses:
//   +x through (lon 0, lat 0), +y through (lon 90E, lat 0), +z through the north pole.

const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const norm360 = (a) => ((a % 360) + 360) % 360;
const norm180 = (a) => norm360(a + 180) - 180;

export function julianDay(tMs) { return tMs / 86400000 + 2440587.5; }

/** Greenwich mean sidereal time, degrees. */
export function gmstDeg(tMs) {
  const n = julianDay(tMs) - 2451545.0;
  return norm360(280.46061837 + 360.98564736629 * n);
}

export function lonLatToVec(lonDeg, latDeg) {
  const l = lonDeg * D2R, p = latDeg * D2R, c = Math.cos(p);
  return [c * Math.cos(l), c * Math.sin(l), Math.sin(p)];
}

/** The Sun: sub-solar point (deg), declination, equation of time (minutes), distance (AU). */
export function sun(tMs) {
  const n = julianDay(tMs) - 2451545.0;
  const L = norm360(280.460 + 0.9856474 * n);
  const g = norm360(357.528 + 0.9856003 * n) * D2R;
  const lam = (L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * D2R;
  const eps = (23.439 - 0.0000004 * n) * D2R;
  const ra = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam)) * R2D;
  const dec = Math.asin(Math.sin(eps) * Math.sin(lam)) * R2D;
  const lon = norm180(ra - gmstDeg(tMs));
  const eot = norm180(L - norm360(ra)) * 4;       // minutes; apparent minus mean solar time
  const dist = 1.00014 - 0.01671 * Math.cos(g) - 0.00014 * Math.cos(2 * g);
  return { lon, lat: dec, dec, ra: norm360(ra), eot, dist, eclLon: norm360(lam * R2D), vec: lonLatToVec(lon, dec) };
}

/** The Moon: sub-lunar point (deg), illuminated fraction, phase angle and name. */
export function moon(tMs) {
  const T = (julianDay(tMs) - 2451545.0) / 36525;
  const s = (a) => Math.sin(a * D2R);
  const lam = 218.32 + 481267.881 * T + 6.29 * s(135.0 + 477198.87 * T) - 1.27 * s(259.3 - 413335.36 * T)
    + 0.66 * s(235.7 + 890534.22 * T) + 0.21 * s(269.9 + 954397.74 * T) - 0.19 * s(357.5 + 35999.05 * T)
    - 0.11 * s(186.5 + 966404.03 * T);
  const beta = 5.13 * s(93.3 + 483202.02 * T) + 0.28 * s(228.2 + 960400.89 * T) - 0.28 * s(318.3 + 6003.15 * T)
    - 0.17 * s(217.6 - 407332.21 * T);
  const eps = (23.439 - 0.013 * T) * D2R;
  const l = lam * D2R, b = beta * D2R;
  const x = Math.cos(b) * Math.cos(l);
  const y = Math.cos(eps) * Math.cos(b) * Math.sin(l) - Math.sin(eps) * Math.sin(b);
  const z = Math.sin(eps) * Math.cos(b) * Math.sin(l) + Math.cos(eps) * Math.sin(b);
  const ra = Math.atan2(y, x) * R2D, dec = Math.asin(z) * R2D;
  const lon = norm180(ra - gmstDeg(tMs));
  const sn = sun(tMs);
  const elong = norm360(lam - sn.eclLon);          // 0 new, 180 full
  const lit = (1 - Math.cos(elong * D2R)) / 2;
  const names = ['New Moon', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full Moon', 'Waning gibbous', 'Last quarter', 'Waning crescent'];
  const name = names[Math.round(elong / 45) % 8];
  return { lon, lat: dec, lit, elong, name, vec: lonLatToVec(lon, dec) };
}

/** Solar elevation (deg) at a place, given a sun() result. */
export function sunElevation(s, lonDeg, latDeg) {
  const p = lonLatToVec(lonDeg, latDeg);
  return Math.asin(Math.max(-1, Math.min(1, p[0] * s.vec[0] + p[1] * s.vec[1] + p[2] * s.vec[2]))) * R2D;
}

/** Local apparent solar time in hours (0-24) at a longitude. */
export function localSolarTime(s, lonDeg) {
  return (((12 + (lonDeg - s.lon) / 15) % 24) + 24) % 24;
}

/** Hours of daylight at a latitude for a solar declination (sunrise at -0.833 deg). 0 or 24 in polar night / day. */
export function dayLength(latDeg, decDeg) {
  const p = latDeg * D2R, d = decDeg * D2R;
  const c = (Math.sin(-0.833 * D2R) - Math.sin(p) * Math.sin(d)) / (Math.cos(p) * Math.cos(d));
  if (c >= 1) return 0;
  if (c <= -1) return 24;
  return 2 * Math.acos(c) * R2D / 15;
}

/** Fractional month state for the cyclic monthly keyframes (keyframes sit at mid-month). */
export function monthState(tMs) {
  const d = new Date(tMs);
  const y = d.getUTCFullYear();
  const start = Date.UTC(y, 0, 1), end = Date.UTC(y + 1, 0, 1);
  const m = ((tMs - start) / (end - start)) * 12 - 0.5;       // 0 = mid-January
  const i0 = ((Math.floor(m) % 12) + 12) % 12;
  return { i0, i1: (i0 + 1) % 12, f: m - Math.floor(m), yearFrac: (tMs - start) / (end - start) };
}

export function seasonName(decDeg, tMs) {
  const s = sun(tMs).eclLon;       // 0 = March equinox
  const q = Math.floor(s / 90);
  return [['Northern spring', 'Southern autumn'], ['Northern summer', 'Southern winter'],
    ['Northern autumn', 'Southern spring'], ['Northern winter', 'Southern summer']][q];
}

export { D2R, R2D, norm180, norm360 };
