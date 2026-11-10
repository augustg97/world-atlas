// Tests for the app's own mathematics.   node build/test_app_math.mjs
// The ephemeris is checked against published almanac values (not against itself), the
// projection by round trip, and the camera by projecting and unprojecting the same point.
import { sun, moon, dayLength, monthState, gmstDeg } from '../web/js/astro.js';
import { wtForward, wtInverse, Camera } from '../web/js/camera.js';

let bad = 0;
const ok = (name, cond, detail = '') => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${name} ${detail}`); if (!cond) bad++; };
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const T = (s) => Date.parse(s);

// Sun: equinoxes and solstices of 2026 (USNO): 20 Mar 14:46, 21 Jun 08:24, 23 Sep 00:05, 21 Dec 20:50 UTC
ok('March equinox: declination 0', near(sun(T('2026-03-20T14:46:00Z')).dec, 0, 0.02), sun(T('2026-03-20T14:46:00Z')).dec.toFixed(4));
ok('June solstice: declination +23.44', near(sun(T('2026-06-21T08:24:00Z')).dec, 23.437, 0.01), sun(T('2026-06-21T08:24:00Z')).dec.toFixed(4));
ok('September equinox: declination 0', near(sun(T('2026-09-23T00:05:00Z')).dec, 0, 0.02), sun(T('2026-09-23T00:05:00Z')).dec.toFixed(4));
ok('December solstice: declination -23.44', near(sun(T('2026-12-21T20:50:00Z')).dec, -23.437, 0.01), sun(T('2026-12-21T20:50:00Z')).dec.toFixed(4));
// equation of time: about +16.4 min on 3 Nov, -14.2 min on 11 Feb, 0 near 15 Apr
ok('equation of time, 3 Nov ~ +16.4 min', near(sun(T('2026-11-03T12:00:00Z')).eot, 16.4, 0.3), sun(T('2026-11-03T12:00:00Z')).eot.toFixed(2));
ok('equation of time, 11 Feb ~ -14.2 min', near(sun(T('2026-02-11T12:00:00Z')).eot, -14.2, 0.3), sun(T('2026-02-11T12:00:00Z')).eot.toFixed(2));
// at 12:00 UTC the Sun is over the Greenwich meridian, displaced west by the equation of time (15' of arc per minute)
{ const s = sun(T('2026-11-03T12:00:00Z')); ok('sub-solar longitude at 12 UTC = -EoT/4 deg', near(s.lon, -s.eot / 4, 0.02), `${s.lon.toFixed(3)} vs ${(-s.eot / 4).toFixed(3)}`); }
ok('Earth-Sun distance: perihelion ~0.9833 AU (early Jan)', near(sun(T('2026-01-03T12:00:00Z')).dist, 0.9833, 0.0005));
// GMST at J2000.0 (2000-01-01 12:00 TT ~ UTC) is 280.4606 deg
ok('GMST at J2000', near(gmstDeg(T('2000-01-01T12:00:00Z')), 280.4606, 0.01));
// Moon: full on 2026-03-03 11:38 UTC (total lunar eclipse), new on 2026-08-12 17:37 UTC (total solar eclipse)
ok('full Moon 3 Mar 2026', moon(T('2026-03-03T11:38:00Z')).lit > 0.995, moon(T('2026-03-03T11:38:00Z')).lit.toFixed(4));
ok('new Moon 12 Aug 2026', moon(T('2026-08-12T17:37:00Z')).lit < 0.005, moon(T('2026-08-12T17:37:00Z')).lit.toFixed(4));
{ // at a total solar eclipse the sub-lunar and sub-solar points nearly coincide
  const t = T('2026-08-12T17:46:00Z'), s = sun(t), m = moon(t);
  const sep = Math.acos(s.vec[0] * m.vec[0] + s.vec[1] * m.vec[1] + s.vec[2] * m.vec[2]) * 180 / Math.PI;
  ok('Sun-Moon separation at the 12 Aug 2026 eclipse < 1.5 deg', sep < 1.5, sep.toFixed(2));
}
ok('day length at the equator ~12.1 h', near(dayLength(0, 0), 12.11, 0.05));
ok('polar night and midnight sun', dayLength(80, -23.4) === 0 && dayLength(80, 23.4) === 24);
{ const m = monthState(T('2026-01-16T12:00:00Z')); ok('mid-January is keyframe 0 exactly', m.i0 === 0 && m.f < 0.02, `${m.i0} ${m.f.toFixed(3)}`); }
{ const m = monthState(T('2026-12-31T23:00:00Z')); ok('year end wraps December -> January', m.i0 === 11 && m.i1 === 0 && near(m.f, 0.5, 0.02)); }

// Winkel Tripel: round trip over the whole sheet, including the corners and the cut meridian
let worst = 0, fails = 0;
for (let lat = -89; lat <= 89; lat += 3.7) for (let lon = -179.5; lon <= 179.5; lon += 4.3) {
  const xy = wtForward(lon * Math.PI / 180, lat * Math.PI / 180), ll = wtInverse(xy[0], xy[1]);
  if (!ll) { fails++; continue; }
  worst = Math.max(worst, Math.hypot((ll[0] * 180 / Math.PI - lon) * Math.cos(lat * Math.PI / 180), ll[1] * 180 / Math.PI - lat));
}
ok('Winkel Tripel inverse(forward) everywhere', fails === 0 && worst < 1e-3, `worst ${worst.toExponential(2)} deg, ${fails} failures`);
ok('Winkel Tripel: outside the sheet is outside', wtInverse(2.5, 1.5) === null && wtInverse(0, 1.6) === null);
{ const e = wtForward(Math.PI, 0); ok('sheet half-width = 1 + pi/2', near(e[0], 1 + Math.PI / 2, 1e-9)); }

// cameras: unproject(project(p)) = p
for (const view of ['globe', 'sheet']) {
  const c = new Camera(); c.view = view; c.resize(1440, 900, 2); c.home(); c.lookAt(31, 30); c.setKmPerPx(4);
  let w = 0;
  for (const [lon, lat] of [[31.2, 30.0], [29, 31.5], [35.5, 27.2], [31, 30]]) { const p = c.project(lon, lat); const b = c.unproject(p[0], p[1]); w = Math.max(w, Math.hypot(b[0] - lon, b[1] - lat)); }
  ok(`${view}: unproject(project(p)) = p`, w < 1e-6, `worst ${w.toExponential(2)} deg`);
  ok(`${view}: km per pixel is what was asked`, near(c.kmPerPx(), 4, 1e-6));
}
{ const c = new Camera(); c.resize(1440, 900, 2); c.home(); c.lookAt(0, 0); ok('globe: the far side is hidden', c.project(180, 0) === null && c.project(0, 0) !== null); }

console.log(bad ? `\napp math: ${bad} FAILURES` : '\napp math: ALL PASS');
process.exit(bad ? 1 : 0);
