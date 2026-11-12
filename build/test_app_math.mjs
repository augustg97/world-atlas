// Tests for the app's own mathematics.   node build/test_app_math.mjs
// The ephemeris is checked against published almanac values (not against itself), the
// projection by round trip, and the camera by projecting and unprojecting the same point.
import { sun, moon, dayLength, monthState, gmstDeg } from '../web/js/astro.js';
import { wtForward, wtInverse, Camera } from '../web/js/camera.js';
import { GIBS, gibsTileDeg, gibsTexelDeg, gibsMatrix, gibsPixel, gibsLonLat, gibsTile, gibsTileBounds, TERRAIN, mercY, mercLat, terrPixel, terrLonLat, terrTile,
  terrTileBounds, terrDecode, terrTexelDeg, terrTexelKm, tentTaps, compositeElevation, shippedElevation, planDetail, viewBox, windowHolds, windowUniforms, PLAN, KM_PER_DEG, nightLight, NIGHT_SHIPPED, despike, S2, s2TileDeg, s2TexelDeg, s2Matrix, s2Tile, s2TileBounds, maskPlan, sampleMask, boxMean, waterFlag, JRC, resampleMercator, quickPlan, waterColour, jrcCovers } from '../web/js/detail.js';
import { INSETS, Inset, freeRect, fitInset, insetAlpha, INSET_FULL, INSET_GONE, INSET_PAD, MIN_GAIN } from '../web/js/insets.js';
import { inflateSync } from 'node:zlib';
import { readFileSync, existsSync } from 'node:fs';

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
// An independent witness for where the Sun is over the turning Earth: NASA EPIC publishes, with every
// frame, the J2000 positions of the Sun and of the spacecraft and the longitude under the spacecraft.
// From those alone (no sidereal-time formula of ours) the sub-solar point follows; see
// Research/modeling/epic_compare.py, sub_solar(). EPIC's own timing is good to about a minute (0.25 deg).
for (const [t, lon, lat] of [
  ['2025-03-20T10:56:46Z', 17.727, 0.031], ['2025-03-20T18:08:57Z', -90.193, 0.150], ['2025-06-21T05:07:44Z', 103.632, 23.436],
  ['2025-06-21T22:35:03Z', -158.156, 23.434], ['2024-09-22T06:28:44Z', 81.075, 0.104], ['2024-09-22T22:41:07Z', -162.089, -0.158],
  ['2025-12-21T10:04:47Z', 28.471, -23.436], ['2025-12-21T17:16:56Z', -79.500, -23.436]]) {
  const s = sun(T(t));
  ok(`sub-solar point vs EPIC, ${t.slice(0, 16)}`, near(s.lon, lon, 0.25) && near(s.lat, lat, 0.02), `lon ${s.lon.toFixed(3)} vs ${lon}, lat ${s.lat.toFixed(3)} vs ${lat}`);
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


// ------------------------------------------------------------------ the focus window (js/detail.js)
// Two tilings are converted into the canonical frame here: NASA GIBS (EPSG:4326, already
// equirectangular) and the AWS Terrain Tiles (Web Mercator). The arithmetic is checked against each
// service's own published numbers, by round trip, against an analytic surface, and then against the
// data: a real tile must hold Mount Everest and the Dead Sea where the arithmetic says they are, and
// streamed heights averaged onto the shipped elevation grid must match it with no shift.

// GIBS "500m" tile matrix set, as its WMTSCapabilities.xml states it (read 2026-11-10)
{
  const caps = [[2, 1], [3, 2], [5, 3], [10, 5], [20, 10], [40, 20], [80, 40], [160, 80]];
  ok('GIBS 500m: matrix sizes of levels 0-7 are the capabilities document\'s', caps.every(([w, h], L) => gibsMatrix(L).w === w && gibsMatrix(L).h === h));
  // ScaleDenominator of level 7 is 1747132.075089743: metres per pixel / 0.28 mm, at 111319.4908 m per degree
  ok('GIBS 500m: level 7 pixel is the capabilities document\'s scale', near(gibsTexelDeg(7) * 111319.49079327358 / 0.00028, 1747132.075089743, 1e-3), (gibsTexelDeg(7) * 111319.49079327358 / 0.00028).toFixed(4));
  ok('GIBS 500m: levels 3-7 tile the sphere exactly', [3, 4, 5, 6, 7].every((L) => 360 / gibsTileDeg(L) === gibsMatrix(L).w && 180 / gibsTileDeg(L) === gibsMatrix(L).h));
  // Cairo, 31.24 E 30.04 N. Level 6 tiles are 4.5 degrees: column floor(211.24 / 4.5) = 46, row floor(59.96 / 4.5) = 13
  const c = gibsTile(31.24, 30.04, 6), b = gibsTileBounds(c.col, c.row, 6);
  ok('GIBS: Cairo is in level 6 tile row 13, column 46', c.col === 46 && c.row === 13, `${c.row}/${c.col} px ${c.px},${c.py}`);
  ok('GIBS: that tile\'s bounds hold Cairo', b.west <= 31.24 && 31.24 < b.east && b.south < 30.04 && 30.04 <= b.north, JSON.stringify(b));
  ok('GIBS: the north-west corner is tile 0/0 pixel 0,0; the south-east corner is the last pixel of the last tile',
    gibsTile(-180, 90, 6).col === 0 && gibsTile(-180, 90, 6).row === 0 && gibsTile(-180, 90, 6).px === 0 && gibsTile(179.9999, -89.9999, 6).col === 79 && gibsTile(179.9999, -89.9999, 6).row === 39 && gibsTile(179.9999, -89.9999, 6).px === 511 && gibsTile(179.9999, -89.9999, 6).py === 511);
  let w = 0; for (let lat = -88; lat <= 88; lat += 7.3) for (let lon = -179; lon <= 179; lon += 11.7) { const g = gibsPixel(lon, lat, 6), ll = gibsLonLat(g[0], g[1], 6); w = Math.max(w, Math.abs(ll[0] - lon), Math.abs(ll[1] - lat)); }
  ok('GIBS: lon/lat -> pixel -> lon/lat', w < 1e-10, `worst ${w.toExponential(2)} deg`);
  // a level-6 texel is a fifth of the shipped albedo's (8192 px), a level-5 texel two fifths: the shipped grid's edges are on both
  ok('GIBS: level 6 and 5 texels divide the shipped 8192 px grid', near((360 / 8192) / gibsTexelDeg(6), 5, 1e-12) && near((360 / 8192) / gibsTexelDeg(5), 2.5, 1e-12));
}

// Web Mercator (EPSG:3857), the terrain tiles' frame
{
  ok('Mercator: the equator is the middle row, 85.0511 N the top', near(mercY(0), 0.5, 1e-15) && near(mercY(TERRAIN.latMax), 0, 1e-12) && near(mercY(-TERRAIN.latMax), 1, 1e-12));
  let w = 0; for (let lat = -85; lat <= 85; lat += 0.37) w = Math.max(w, Math.abs(mercLat(mercY(lat)) - lat));
  ok('Mercator: lat -> y -> lat', w < 1e-11, `worst ${w.toExponential(2)} deg`);
  // The dataset's own table (joerd docs/data-sources.md): zoom 7 is 1223.0 m a pixel at the equator, 864.8 at 45, 611.5 at 60,
  // on the WGS84 equatorial radius. The atlas's sphere is 6371.0088 km, 0.11% smaller.
  const k = 6378.137 / 6371.0088;
  ok('terrain: ground resolution matches the dataset\'s table', near(terrTexelKm(0, 7) * k, 1.2230, 5e-4) && near(terrTexelKm(45, 7) * k, 0.8648, 5e-4) && near(terrTexelKm(60, 7) * k, 0.6115, 5e-4) && near(terrTexelKm(0, 0) * k, 156.5430, 5e-3),
    `${(terrTexelKm(0, 7) * k).toFixed(4)} ${(terrTexelKm(45, 7) * k).toFixed(4)} ${(terrTexelKm(60, 7) * k).toFixed(4)}`);
  // The dataset's own worked example (docs/formats.md): rgb(137, 219, 68) is 2523.265625 m; its range is rgb(85, 8, 0) to rgb(162, 198, 0)
  ok('terrarium decode: the dataset\'s worked example', terrDecode(137, 219, 68) === 2523.265625 && terrDecode(85, 8, 0) === -11000 && terrDecode(162, 198, 0) === 8902 && terrDecode(128, 0, 0) === 0);
  // Mount Everest, 86.9250 E 27.9881 N: zoom 7 tile 94/53. That tile's own header lists its sources as SRTM N27-N29, E084-E087.
  const e = terrTile(86.9250, 27.9881, 7), b = terrTileBounds(94, 53, 7);
  ok('terrain: Everest is in zoom 7 tile x 94, y 53', e.x === 94 && e.y === 53, `${e.x}/${e.y} px ${e.px},${e.py}`);
  ok('terrain: tile 7/94/53 spans 84.375-87.1875 E, 27.06-29.54 N', near(b.west, 84.375, 1e-9) && near(b.east, 87.1875, 1e-9) && near(b.south, 27.0591, 1e-3) && near(b.north, 29.5352, 1e-3), `${b.south.toFixed(4)} ${b.north.toFixed(4)}`);
  ok('terrain: 0 E 0 N is the first pixel of tile 1/1 at zoom 1; -180 E, 85.05 N of tile 0/0', terrTile(0, 0, 1).x === 1 && terrTile(0, 0, 1).y === 1 && terrTile(0, 0, 1).px === 0 && terrTile(0, 0, 1).py === 0 && terrTile(-180, 85.05, 3).x === 0 && terrTile(-180, 85.05, 3).y === 0);
  ok('terrain: longitude wraps and latitude clamps', terrTile(181, 0, 4).x === terrTile(-179, 0, 4).x && terrTile(0, 89, 4).y === 0 && terrTile(0, -89, 4).y === 15);
  w = 0; for (let lat = -84; lat <= 84; lat += 5.1) for (let lon = -179; lon <= 179; lon += 13.3) { const g = terrPixel(lon, lat, 9), ll = terrLonLat(g[0], g[1], 9); w = Math.max(w, Math.abs(ll[0] - lon), Math.abs(ll[1] - lat)); }
  ok('terrain: lon/lat -> pixel -> lon/lat', w < 1e-10, `worst ${w.toExponential(2)} deg`);
  { const t = terrTile(35.5, 31.5, 9), bb = terrTileBounds(t.x, t.y, 9); ok('terrain: a tile\'s bounds hold the place that named it', bb.west <= 35.5 && 35.5 < bb.east && bb.south < 31.5 && 31.5 <= bb.north); }
}

// the resampling filter
{
  const sum = (t) => t.reduce((a, v, i) => a + (i & 1 ? v : 0), 0), mean = (t) => { let m = 0; for (let i = 0; i < t.length; i += 2) m += (t[i] + 0.5) * t[i + 1]; return m; };
  const a = tentTaps(10.5, 1), b = tentTaps(10.75, 1), c = tentTaps(10.3, 2.7), d = tentTaps(11, 1);
  ok('tent filter: on a pixel centre at scale 1 it is that pixel', a.length === 2 && a[0] === 10 && a[1] === 1);
  ok('tent filter: between centres at scale 1 it is linear interpolation', b.length === 4 && b[0] === 10 && near(b[1], 0.75, 1e-12) && b[2] === 11 && near(b[3], 0.25, 1e-12) && d.length === 4 && near(d[1], 0.5, 1e-12));
  ok('tent filter: minifying, weights sum to 1, centre on the sample exactly and span the footprint', near(sum(c), 1, 1e-12) && near(mean(c), 10.3, 1e-12) && c.length / 2 >= 5, `${c.length / 2} taps, centroid ${mean(c).toFixed(6)}`);
}

// Mercator tiles -> equirectangular grid, against a surface known analytically. The tiles are synthesised: each
// Mercator pixel holds the surface at its own centre. A half-pixel error anywhere in the chain is 11 m here.
{
  const z = 6, surf = (lon, lat) => 1000 * lat + 400 * Math.sin(lon * Math.PI / 180) + 250 * Math.cos(lat * Math.PI / 45);
  const tiles = new Map();
  const getTile = (x, y) => {
    const k = x + '/' + y; if (tiles.has(k)) return tiles.get(k);
    const d = new Float32Array(65536);
    for (let j = 0; j < 256; j++) for (let i = 0; i < 256; i++) { const ll = terrLonLat(x * 256 + i + 0.5, y * 256 + j + 0.5, z); d[j * 256 + i] = surf(ll[0], ll[1]); }
    tiles.set(k, d); return d;
  };
  const run = (win, w, h, tol, name, ship) => {
    const out = compositeElevation(win, z, w, h, getTile, ship || null);
    let worst = 0, at = '';
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      const lon = win.west + (i + 0.5) * win.lonSpan / w, lat = win.north - (j + 0.5) * win.latSpan / h;
      if (Math.abs(lat) > 83.9) continue;
      const e = Math.abs(out[j * w + i] - surf(lon, lat)); if (e > worst) { worst = e; at = `${lon.toFixed(2)},${lat.toFixed(2)}`; }
    }
    ok(name, worst < tol, `worst ${worst.toFixed(3)} m at ${at}; half a source pixel would be ${(500 * terrTexelDeg(z)).toFixed(1)} m`);
    return out;
  };
  // the source's own column spacing, rows as fine as the source at the low-latitude edge: nothing but interpolation error
  run({ west: 80.013, north: 34.007, lonSpan: 400 * terrTexelDeg(z), latSpan: 8 }, 400, Math.round(8 / (terrTexelDeg(z) * Math.cos(26 * Math.PI / 180))), 0.3, 'composite: mid-latitude window reproduces the surface');
  run({ west: 172.3, north: -10.2, lonSpan: 16, latSpan: 12 }, Math.round(16 / terrTexelDeg(z)), Math.round(12 / terrTexelDeg(z)), 0.3, 'composite: across the antimeridian (172 E to 188 E)');
  run({ west: -8, north: 6, lonSpan: 16, latSpan: 12 }, Math.round(16 / terrTexelDeg(z)), Math.round(12 / terrTexelDeg(z)), 0.3, 'composite: across the equator and the prime meridian');
  // a coarser output than the source (each output texel 2.5 source pixels): an area average, still centred
  run({ west: 5, north: 50, lonSpan: 12, latSpan: 8 }, Math.round(12 / terrTexelDeg(z) / 2.5), Math.round(8 / terrTexelDeg(z) / 2.5), 0.8, 'composite: minified 2.5x stays centred');
  // the polar cap: beyond the Mercator square the height is the shipped field's
  const out = run({ west: 10, north: 90, lonSpan: 8, latSpan: 10 }, 200, 250, 1.5, 'composite: a window to the pole is right up to 84 N', () => -7777);
  const row = (lat) => Math.floor((90 - lat) / (10 / 250));
  ok('composite: beyond 85.05 N the grid holds the shipped field, not a stretched last row', out[row(88) * 200 + 50] === -7777 && out[row(85.2) * 200 + 50] === -7777 && out[row(82) * 200 + 50] !== -7777, `${out[row(88) * 200 + 50]} at 88 N, ${out[row(82) * 200 + 50].toFixed(0)} at 82 N`);
  // the sea: where the water mask says water and the tiles are below sea level, the shipped field; land below sea level stays the tiles'
  {
    const flat = () => new Float32Array(65536).fill(-400), win = { west: 20, north: 10, lonSpan: 4, latSpan: 4 };
    const own = new Float32Array(10000), g = compositeElevation(win, z, 100, 100, flat, () => -3000, (lon) => (lon > 22 ? 1 : 0), own);
    ok('composite: below sea level under the water mask is the shipped field; below sea level on land is the tiles\'', g[50 * 100 + 90] === -3000 && g[50 * 100 + 10] === -400, `${g[50 * 100 + 90]} m in the water, ${g[50 * 100 + 10]} m on land`);
    ok('composite: the second channel says whose height each texel is (1 the tiles\', 0 the shipped field\'s)', own[50 * 100 + 90] === 0 && own[50 * 100 + 10] === 1);
    const lake = compositeElevation(win, z, 100, 100, () => new Float32Array(65536).fill(179), () => -200, () => 1);
    ok('composite: a lake above sea level keeps the tiles\' surface', lake[5050] === 179);
  }
  let threw = false; try { compositeElevation({ west: 0, north: 10, lonSpan: 4, latSpan: 4 }, z, 100, 100, () => null, null); } catch (e) { threw = true; }
  ok('composite: a missing tile is an error, never a hole', threw);
}

// the window planner
{
  const views = { Himalaya: [86, 28], Alps: [10, 46.5], 'Nile delta': [31, 30.5], 'Grand Canyon': [-112.5, 36.2], 'Fiji (antimeridian)': [179, -17], Svalbard: [15, 78] };
  for (const [name, [lon, lat]] of Object.entries(views)) for (const k of [2, 3]) {
    const c = new Camera(); c.resize(1440, 900, 1); c.home(); c.lookAt(lon, lat); c.setKmPerPx(k);
    const v = viewBox(c), p = planDetail(v, k);
    if (!p) { ok(`plan: ${name} at ${k} km/px`, lat > 70, 'no plan'); continue; }
    const W = p.win, a = p.alb, e = p.elev, m6 = a ? gibsMatrix(a.L) : null;
    const within = (!a || (a.count <= PLAN.maxTiles && a.tiles.length === a.count)) && (!e || (e.count <= PLAN.maxElevTiles && e.tiles.length === e.count));
    const rowsExist = (!a || a.tiles.every((t) => t.row >= 0 && t.row < m6.h && t.col >= 0 && t.col < m6.w)) && (!e || e.tiles.every((t) => t.y >= 0 && t.y < 2 ** e.z && t.x >= 0 && t.x < 2 ** e.z));
    // every pixel of the imagery canvas is under exactly one tile, at whole-pixel offsets
    let covered = !a;
    if (a) { const xs = new Set(a.tiles.map((t) => t.dx)), ys = new Set(a.tiles.map((t) => t.dy)); covered = Math.min(...xs) <= 0 && Math.max(...xs) + 512 >= a.w && Math.min(...ys) <= 0 && Math.max(...ys) + 512 >= a.h && xs.size * ys.size === a.tiles.length && a.tiles.every((t) => Number.isInteger(t.dx) && Number.isInteger(t.dy)) && Number.isInteger(a.w) && near(a.w * a.texelDeg, W.lonSpan, 1e-9) && near(a.h * a.texelDeg, W.latSpan, 1e-9); }
    // the first imagery tile's north-west corner, through its offset, is where the tile bounds say it is
    let placed = !a;
    if (a) { const t = a.tiles[0], b = gibsTileBounds(t.col, t.row, a.L); let dl = (W.west + t.dx * a.texelDeg) - b.west; dl -= Math.round(dl / 360) * 360; placed = Math.abs(dl) < 1e-9 && near(W.north - t.dy * a.texelDeg, b.north, 1e-9); }
    const fine = (!a || a.texelKm <= PLAN.gainKm) && (!e || terrTexelKm(lat, e.z) <= PLAN.gainKm);
    ok(`plan: ${name} at ${k} km/px`, within && rowsExist && covered && placed && fine && windowHolds(W, v, p.margin - 1e-6) && W.north <= 90 && W.north - W.latSpan >= -90 && W.lonSpan <= 360,
      `margin ${p.margin}, ${W.lonSpan.toFixed(1)} x ${W.latSpan.toFixed(1)} deg; imagery ${a ? `L${a.L} ${a.count} tiles ${a.texelKm.toFixed(2)} km` : 'none'}; elevation ${e ? `z${e.z} ${e.count} tiles ${terrTexelKm(lat, e.z).toFixed(2)} km` : 'none'}`);
    if (name.startsWith('Fiji') && k === 2) {
      const u = windowUniforms(p).uDetWin, cols = a.tiles.map((t) => t.col), xs = e.tiles.map((t) => t.x);
      ok('plan: the antimeridian window takes tiles from both ends of the row', Math.min(...cols) === 0 && Math.max(...cols) === m6.w - 1 && Math.min(...xs) === 0 && Math.max(...xs) === 2 ** e.z - 1, `imagery columns ${Math.min(...cols)}..${Math.max(...cols)}, elevation x ${Math.min(...xs)}..${Math.max(...xs)}`);
      // the shader's own arithmetic: position in the window of 179 E and of 179 W (= 181 E), 17 S
      const dwx = (lon2) => { const x = (lon2 / 360 + 0.5) - u[0]; return (x - Math.floor(x)) / u[2]; };
      ok('plan: 179 E and 179 W are both inside the window, in order, 2 degrees apart', dwx(179) > 0.06 && dwx(-179) < 0.94 && near((dwx(-179) - dwx(179)) * W.lonSpan, 2, 1e-9), `${dwx(179).toFixed(4)} ${dwx(-179).toFixed(4)}`);
    }
    if (name === 'Himalaya' && k === 2) {
      const u = windowUniforms(p);
      ok('uniforms: window corners in canonical uv', near(u.uDetWin[0], W.west / 360 + 0.5, 1e-12) && near(u.uDetWin[1], 0.5 - W.north / 180, 1e-12) && near(u.uDetWin[0] + u.uDetWin[2], (W.west + W.lonSpan) / 360 + 0.5, 1e-12) && near(u.uDetWin[1] + u.uDetWin[3], 0.5 - (W.north - W.latSpan) / 180, 1e-12));
      ok('uniforms: the mip whose texel is the shipped albedo\'s', near(2 ** u.uDetAlbLod * a.texelDeg, 360 / 8192, 1e-12), `lod ${u.uDetAlbLod.toFixed(3)} at L${a.L}`);
      ok('uniforms: elevation texel in window units and in metres', near(u.uDetElevPx[0] * e.w, 1, 1e-12) && near(u.uDetElevM[0] * e.w, W.lonSpan * KM_PER_DEG * 1000, 1e-6) && near(u.uDetElevM[1] * e.h, W.latSpan * KM_PER_DEG * 1000, 1e-6), `${u.uDetElevM[0].toFixed(0)} m x ${u.uDetElevM[1].toFixed(0)} m`);
    }
  }
  const far = new Camera(); far.resize(1440, 900, 1); far.home(); far.lookAt(86, 28); far.setKmPerPx(6);
  ok('plan: nothing is streamed at 6 km a pixel', planDetail(viewBox(far), 6) === null);
  const pole = new Camera(); pole.resize(1440, 900, 1); pole.home(); pole.lookAt(0, 89); pole.setKmPerPx(2);
  { const v = viewBox(pole), p = planDetail(v, 2); ok('plan: with a pole on screen the view is every longitude, and no row beyond the pole is asked for', v.full && v.north === 90 && (!p || ((!p.alb || p.alb.tiles.every((t) => t.row >= 0)) && p.win.north <= 90)), p ? 'a plan' : 'no plan'); }
}

// ---- the data itself (network). Offline, these print a line and are skipped. ----
function png(buf) {                                   // 8-bit RGB or RGBA, non-interlaced: all this test needs
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20), depth = buf[24], ct = buf[25], bpp = ct === 2 ? 3 : ct === 6 ? 4 : 0;
  if (depth !== 8 || !bpp || buf[28] !== 0) throw new Error(`png: unsupported (depth ${depth}, colour type ${ct}, interlace ${buf[28]})`);
  const parts = []; let o = 8;
  while (o < buf.length) { const n = buf.readUInt32BE(o), type = buf.toString('latin1', o + 4, o + 8); if (type === 'IDAT') parts.push(buf.subarray(o + 8, o + 8 + n)); o += 12 + n; }
  const raw = inflateSync(Buffer.concat(parts)), line = w * bpp, out = new Uint8Array(line * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (line + 1)], src = y * (line + 1) + 1, dst = y * line;
    for (let x = 0; x < line; x++) {
      const a = x >= bpp ? out[dst + x - bpp] : 0, b = y ? out[dst - line + x] : 0, c = x >= bpp && y ? out[dst - line + x - bpp] : 0;
      let v = raw[src + x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      out[dst + x] = v;
    }
  }
  return { w, h, bpp, d: out };
}
const tileCache = new Map();
async function terrainTile(z, x, y) {
  const k = `${z}/${x}/${y}`; if (tileCache.has(k)) return tileCache.get(k);
  const r = await fetch(TERRAIN.url(z, x, y), { signal: AbortSignal.timeout(20000) });
  if (!r.ok) throw new Error(`${k}: HTTP ${r.status}`);
  const p = png(Buffer.from(await r.arrayBuffer())), d = new Float32Array(65536);
  if (p.w !== 256 || p.h !== 256) throw new Error(`${k}: ${p.w} x ${p.h}`);
  for (let i = 0; i < 65536; i++) d[i] = terrDecode(p.d[i * p.bpp], p.d[i * p.bpp + 1], p.d[i * p.bpp + 2]);
  tileCache.set(k, d); return d;
}
let online = true;
try { await terrainTile(0, 0, 0); } catch (e) { online = false; console.log(`  skip the terrain tiles could not be reached (${e.cause ? e.cause.code || e.cause.message : e.message}): real-value and registration checks not run`); }
if (online) {
  // Mount Everest, 86.9250 E 27.9881 N, 8849 m. At zoom 10 a pixel is 135 m: the summit pixel reads a little under the summit.
  // Mount Everest, 86.9250 E 27.9881 N, 8849 m. The tiles are SRTM there, which reads the summit about 100 m low (8751 m at
  // zoom 13) and 40-130 m north-east of the surveyed point. At zoom 9 a pixel is 270 m and the summit pixel holds 8704 m.
  { const z = 9, t = terrTile(86.9250, 27.9881, z), d = await terrainTile(z, t.x, t.y);
    let mx = -1e9, mi = 0; for (let i = 0; i < 65536; i++) if (d[i] > mx) { mx = d[i]; mi = i; }
    const here = d[t.py * 256 + t.px], dist = Math.hypot((mi % 256) - t.px, Math.floor(mi / 256) - t.py);
    ok('real tile: Mount Everest\'s pixel reads 8,600-8,850 m', here > 8600 && here < 8850, `${here.toFixed(0)} m at ${z}/${t.x}/${t.y} pixel ${t.px},${t.py}`);
    ok('real tile: the highest pixel of that tile is the one Everest was predicted in', dist <= 1 && mx < 8850, `max ${mx.toFixed(0)} m, ${dist.toFixed(1)} px from the predicted pixel`); }
  // The Dead Sea, 35.50 E 31.50 N: its surface was about -415 m when SRTM flew (2000) and is about -440 m now.
  { const z = 9, t = terrTile(35.5, 31.5, z), d = await terrainTile(z, t.x, t.y), here = d[t.py * 256 + t.px];
    ok('real tile: the Dead Sea reads about -400 m', here > -445 && here < -390, `${here.toFixed(1)} m at ${z}/${t.x}/${t.y} pixel ${t.px},${t.py}`); }
  // Open ocean: the tiles hold bathymetry (ETOPO1). The Challenger Deep, 142.2 E 11.35 N, is about -10,900 m.
  { const z = 7, t = terrTile(142.2, 11.35, z), d = await terrainTile(z, t.x, t.y); let mn = 1e9; for (let i = 0; i < 65536; i++) mn = Math.min(mn, d[i]);
    ok('real tile: the sea floor is in the tiles (Mariana Trench below -10,000 m)', mn < -10000 && mn > -11100, `deepest pixel ${mn.toFixed(0)} m in ${z}/${t.x}/${t.y}`); }

  // Registration against the shipped elevation field (web/fields/elev.png, ETOPO 2022 on a 4096 x 2048 grid, 9.8 km).
  // Streamed tiles are composited at a quarter of a shipped cell, averaged 4 x 4 onto the shipped cells and compared;
  // then the same with the streamed grid slid east-west and north-south in quarter-cell steps. The misfit must be
  // least at no shift. A half-cell (4.9 km) error in either conversion costs hundreds of metres here.
  const elevPng = new URL('../web/fields/elev.png', import.meta.url);
  if (!existsSync(elevPng)) console.log('  skip web/fields/elev.png is not built: registration against the shipped field not run');
  else {
    const p = png(readFileSync(elevPng)), ship = { w: p.w, h: p.h, d: new Uint16Array(p.w * p.h) };
    for (let i = 0; i < ship.d.length; i++) ship.d[i] = (p.d[i * p.bpp] << 8) | p.d[i * p.bpp + 1];
    const cell = 360 / ship.w, S = 4, B = 4;                       // S streamed texels per shipped cell, B texels of border for the slide
    for (const [name, lon0, lat1, nx, ny, z, sea] of [['Himalaya', 80, 32, 136, 68, 6], ['Alps', 5, 48.5, 114, 46, 6], ['Grand Canyon and Rockies', -116, 40, 114, 68, 6], ['Andes (southern hemisphere)', -72, -14, 91, 114, 6],
      ['the sea floor off Fiji, across the antimeridian', 174, -12, 136, 114, 6, true]]) {
      const cx0 = Math.round((lon0 + 180) / cell), cy0 = Math.round((90 - lat1) / cell);             // whole shipped cells
      const win = { west: cx0 * cell - 180 - B * cell / S, north: 90 - cy0 * cell + B * cell / S, lonSpan: (nx * S + 2 * B) * cell / S, latSpan: (ny * S + 2 * B) * cell / S };
      const w = nx * S + 2 * B, h = ny * S + 2 * B;
      const n = 2 ** z, need = new Set();
      for (let j = 0; j < h; j += 8) for (let i = 0; i < w; i += 8) { const t = terrTile(win.west + (i + 0.5) * cell / S, win.north - (j + 0.5) * cell / S, z); for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) need.add(`${(t.x + dx + n) % n}/${Math.max(0, Math.min(n - 1, t.y + dy))}`); }
      const got = new Map(); for (const k of need) { const [x, y] = k.split('/').map(Number); got.set(k, await terrainTile(z, x, y)); }
      // the tiles alone: no shipped field and no water mask go into this grid, or the match would be by construction
      const g = compositeElevation(win, z, w, h, (x, y) => got.get(`${x}/${y}`), null, null);
      const shipAt = (cx, cy) => (ship.d[(cy0 + cy) * ship.w + ((cx0 + cx) % ship.w + ship.w) % ship.w] / 65535) * 20000 - 11000;
      // land cells: the shipped cell and its eight neighbours are above sea level (so no sea floor is in any slid average)
      const use = new Uint8Array(nx * ny); let cells = 0;
      for (let cy = 1; cy < ny - 1; cy++) for (let cx = 1; cx < nx - 1; cx++) { let land = true, wet = true; for (const dy of [-1, 0, 1]) for (const dx of [-1, 0, 1]) { const v = shipAt(cx + dx, cy + dy); if (v <= 0) land = false; if (v > -200) wet = false; } if (sea ? wet : land) { use[cy * nx + cx] = 1; cells++; } }
      const fit = (sx, sy) => {                                    // streamed slid by (sx, sy) texels: positive = its content moved east / south
        let se = 0, sb = 0, m = 0;
        for (let cy = 0; cy < ny; cy++) for (let cx = 0; cx < nx; cx++) {
          if (!use[cy * nx + cx]) continue;
          let a = 0; for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) a += g[(B + cy * S + j - sy) * w + (B + cx * S + i - sx)];
          a /= S * S;
          const s = shipAt(cx, cy);
          se += (a - s) ** 2; sb += a - s; m++;
        }
        return { rms: Math.sqrt(se / m), bias: sb / m };
      };
      const at0 = fit(0, 0);
      let best = [0, 0], br = at0.rms; const prof = { x: [], y: [] };
      for (let s = -B; s <= B; s++) { const fx = fit(s, 0).rms, fy = fit(0, s).rms; prof.x.push(fx); prof.y.push(fy); if (fx < br) { br = fx; best = [s, 0]; } if (fy < br) { br = fy; best = [0, s]; } }
      // the minimum of each profile to a fraction of a step, by a parabola through its three lowest points
      const sub = (pr) => { let i = pr.indexOf(Math.min(...pr)); i = Math.max(1, Math.min(pr.length - 2, i)); const [a, b, c] = [pr[i - 1], pr[i], pr[i + 1]]; return (i - B + 0.5 * (a - c) / (a - 2 * b + c)) / S; };
      const dx = sub(prof.x), dy = sub(prof.y), half = fit(S / 2, 0).rms;
      const line = `rms ${at0.rms.toFixed(1)} m, bias ${at0.bias.toFixed(1)} m over ${cells} cells of ${(cell * KM_PER_DEG).toFixed(1)} km; best shift ${(dx * cell * KM_PER_DEG).toFixed(2)} km east, ${(dy * cell * KM_PER_DEG).toFixed(2)} km south (${dx.toFixed(3)}, ${dy.toFixed(3)} cell); slid half a cell: rms ${half.toFixed(0)} m; ${need.size} tiles`;
      if (!sea) ok(`registration, ${name}: streamed land = shipped land at no shift`, best[0] === 0 && best[1] === 0 && Math.abs(dx) < 0.05 && Math.abs(dy) < 0.05 && at0.rms < 60 && Math.abs(at0.bias) < 15, line);
      // Not a pass or fail: the reason compositeElevation keeps the shipped field under water. The tiles' sea floor (ETOPO1) is
      // NOT in the shipped field's frame. If this line ever reads rms under 60 m at no shift, the tiles were rebuilt: reconsider.
      else console.log(`  note ${name}: the tiles' sea floor against the shipped one, ${line}`);
    }
  }
}

// Insets (register F1): the geometry of a second view of the sheet. The panels are the ones the page has at 1440 x 900
// and at 1100 x 700 (read from the page by Research/modeling/audit_labels.py; padded by 4 px as main.js pads them).
{
  const same = (a, b) => !!a && a.length === b.length && a.every((v, i) => Math.abs(v - b[i]) < 1e-9);
  ok('inset room: beside a panel', same(freeRect([0, 0, 300, 200], [[-10, -10, 100, 300]], [1, 1]), [100, 0, 300, 200]));
  ok('inset room: none under a panel', freeRect([0, 0, 100, 100], [[-1, -1, 101, 101]], [1, 1]) === null);
  ok('inset room: the part that holds the larger frame of the given shape', same(freeRect([0, 0, 300, 300], [[150, 0, 300, 100]], [1, 2]), [0, 0, 150, 300]));
  const P1440 = [[6, 6, 1434, 70], [6, 72, 282, 792], [1108, 72, 1434, 713], [895, 755, 1106, 792], [6, 794, 1434, 894]];
  const P1100 = [[6, 6, 1094, 70], [6, 72, 282, 592], [806, 72, 1094, 592], [593, 555, 804, 592], [6, 594, 1094, 694]];
  const sheet = (w, h) => { const c = new Camera(); c.view = 'sheet'; c.resize(w, h, 1); c.home(); return c; };
  const hits = (r, q) => r[0] < q[2] && r[2] > q[0] && r[1] < q[3] && r[3] > q[1];
  const cam = sheet(1440, 900), taken = P1440.slice();
  for (const def of INSETS) {
    const I = new Inset(def);
    I.layout(cam, taken, 1, 1);
    const r = I.rect, box = r && [r.x, r.y, r.x + r.w, r.y + r.h];
    ok(`inset ${def.id}: has room on the whole-Earth sheet at 1440 x 900, clear of every panel`, !!r && !taken.some((q) => hits(box, q)) && r.x >= 0 && r.y >= 0 && r.x + r.w <= 1440 && r.y + r.h <= 900, r ? `${r.w} x ${r.h} at ${r.x}, ${r.y}; ${I.k.toFixed(2)} km/px` : 'not drawn');
    if (!r) continue;
    const step = Math.log(I.k) / Math.log(1.05);
    ok(`inset ${def.id}: scale within its limits, on the label layer's ladder, and worth its frame`, I.k >= def.kMin - 1e-9 && I.k <= def.kMax + 1e-9 && Math.abs(step - Math.round(step)) < 1e-6 && cam.kmPerPx() / I.k >= MIN_GAIN, `${(cam.kmPerPx() / I.k).toFixed(2)} x`);
    // it is the same sheet, magnified: the middle of the frame is the inset's centre, and a place keeps its position
    // within the frame as within the outline drawn on the main map
    const mid = I.cam.unproject(r.w / 2, r.h / 2);
    ok(`inset ${def.id}: the middle of its frame is its centre`, near(mid[0], def.center[0], 1e-6) && near(mid[1], def.center[1], 1e-6));
    const s = I.source(cam);
    let worstIn = 0;
    for (const [fx, fy] of [[0.1, 0.1], [0.9, 0.2], [0.5, 0.5], [0.3, 0.85], [0.95, 0.95]]) {
      const ll = I.cam.unproject(r.w * fx, r.h * fy), m = cam.project(ll[0], ll[1]), back = I.cam.project(ll[0], ll[1]);
      worstIn = Math.max(worstIn, Math.abs((m[0] - s[0]) / (s[2] - s[0]) - fx), Math.abs((m[1] - s[1]) / (s[3] - s[1]) - fy), Math.abs(back[0] - r.w * fx) / r.w, Math.abs(back[1] - r.h * fy) / r.h);
    }
    ok(`inset ${def.id}: frame and outline show the same ground`, worstIn < 1e-6, `worst ${worstIn.toExponential(2)} of the frame`);
    // its sea must be sea: the frame's own outline on the main map does not reach the frame (they are different places)
    ok(`inset ${def.id}: the frame is not on the ground it shows`, !hits(box, s));
    taken.push([r.x - INSET_PAD, r.y - INSET_PAD, r.x + r.w + INSET_PAD, r.y + r.h + INSET_PAD]);
  }
  { // a smaller window: the same seas are smaller on the screen; an inset is drawn only if it still fits, never under a panel
    const c2 = sheet(1100, 700), t2 = P1100.slice();
    for (const def of INSETS) {
      const f = fitInset(def, c2, t2);
      ok(`inset ${def.id} at 1100 x 700: fits clear of the panels within its scale limits, or is not drawn`, !f || (f.k <= def.kMax + 1e-9 && !t2.some((q) => hits([f.x, f.y, f.x + f.w, f.y + f.h], q))), f ? `${f.w} x ${f.h}, ${f.k.toFixed(2)} km/px` : 'not drawn');
      if (f) t2.push([f.x - INSET_PAD, f.y - INSET_PAD, f.x + f.w + INSET_PAD, f.y + f.h + INSET_PAD]);
    }
  }
  { // dragged until its sea is under the left panel: gone, not squeezed past its coarsest scale
    const c3 = sheet(1440, 900); c3.pan(-120, 0);
    ok('inset europe: no room once its sea is under the panel', fitInset(INSETS[0], c3, P1440) === null);
  }
  ok('insets fade with the main map: whole at the whole-Earth scale, gone close in', insetAlpha(25.9) === 1 && insetAlpha(INSET_FULL) === 1 && insetAlpha(INSET_GONE) === 0 && insetAlpha(6) === 0 && insetAlpha((INSET_FULL + INSET_GONE) / 2) === 0.5);
}

// The streamed night lights (detail.js nightLight) against the rule the shipped field was built with
// (build/fields_surface.py step_night): Black Marble's own run of colours, from its moonlit base to a white core.
{
  const shipped = (r, g, b) => Math.max(0, Math.min(1, ((r + g) * 0.5 - 0.62 * b - 2) / 95));
  const run = [[82, 69, 72], [128, 103, 91], [174, 138, 111], [232, 199, 160], [248, 202, 146], [255, 240, 215], [255, 255, 255]];
  const v = run.map((c) => nightLight(...c));
  ok('lights: brightness rises all the way from a dim street to a white core', v.every((x, i) => i === 0 || x > v[i - 1]) && v[v.length - 1] === 1, v.map((x) => x.toFixed(2)).join(' '));
  ok('lights: moonlit desert, sea and snow are not light', [[37, 34, 62], [5, 5, 15], [25, 23, 46], [60, 62, 95]].every((c) => nightLight(...c) < 0.005));
  const worst = Math.max(...run.slice(0, 3).map((c) => Math.abs(Math.min(1, nightLight(...c) / NIGHT_SHIPPED) - shipped(...c))));
  ok('lights: below full scale the streamed value is the shipped field\'s, within 0.06', worst < 0.06, `worst ${worst.toFixed(3)}`);
  ok('lights: where the shipped field is at full scale, so is the streamed one read back', run.slice(3).every((c) => Math.min(1, nightLight(...c) / NIGHT_SHIPPED) > 0.97));
  const cam = new Camera(); cam.resize(1280, 800, 2); cam.lookAt(-117.6, 33.9); cam.setKmPerPx(0.6);
  const p = planDetail(viewBox(cam), 0.6, { night: true }), q = planDetail(viewBox(cam), 0.6);
  ok('plan: at 0.6 km a pixel the imagery is Blue Marble\'s last level, 0.49 km, with the lights on the same tiles', p && p.alb.src === 'bm' && p.alb.L === GIBS.maxLevel && Math.abs(p.alb.texelKm - 0.489) < 0.01 && p.night && !q.night && p.key !== q.key, p ? `${p.alb.count} tiles` : 'no plan');
  // Sentinel-2 cloudless (EOX): the tiling, and the plans that use it
  ok('s2: level 0 is two tiles of 180 degrees; level 13 is the 10 m mosaic', s2TileDeg(0) === 180 && s2Matrix(0).w === 2 && s2Matrix(0).h === 1 && Math.abs(s2TexelDeg(13) * KM_PER_DEG - 0.00954) < 0.0001, `${(s2TexelDeg(13) * KM_PER_DEG * 1000).toFixed(2)} m`);
  { const t = s2Tile(-118.25, 34.05, 11), bb = s2TileBounds(t.col, t.row, 11);
    ok('s2: downtown Los Angeles is in tile 11/636/702, and inside that tile\'s bounds', t.row === 636 && t.col === 702 && bb.west <= -118.25 && bb.east > -118.25 && bb.south <= 34.05 && bb.north > 34.05, `${t.row}/${t.col}`);
    ok('s2: the tile address is row then column', S2.url(11, t.row, t.col).endsWith('/WGS84/11/636/702.jpg')); }
  for (const [k, zWant] of [[0.4, 8], [0.2, 9], [0.1, 10], [0.05, 11]]) {
    cam.setKmPerPx(k);
    const v = viewBox(cam), r = planDetail(v, k, { night: true });
    ok(`plan: at ${k} km a pixel the imagery is Sentinel-2 level ${zWant}, no coarser than 0.8 of a pixel, within its request budget, and covers the view`,
      r && r.alb.src === 's2' && r.alb.L === zWant && r.alb.texelKm <= 0.8 * k * 1.001 && r.alb.count <= PLAN.maxS2Tiles && r.alb.tiles.length === r.alb.count && windowHolds(r.win, v, 0) && r.alb.tiles.every((t) => Number.isInteger(t.dx) && Number.isInteger(t.dy)),
      r ? `level ${r.alb.L}, ${(r.alb.texelKm * 1000).toFixed(0)} m, ${r.alb.count} tiles, ${r.alb.w} x ${r.alb.h}, elevation zoom ${r.elev.z} (${r.elev.count} tiles), margin ${r.margin}` : 'no plan');
    ok(`plan: at ${k} km a pixel, with Sentinel-2 refused, it is Blue Marble's last level`, (() => { const b = planDetail(v, k, { noS2: true }); return b && b.alb.src === 'bm' && b.alb.L === GIBS.maxLevel; })());
  }
  { cam.lookAt(25, 62); cam.setKmPerPx(0.05); const v = viewBox(cam), r = planDetail(v, 0.05);
    ok('plan: at 62 N, where a tile is half as wide on the ground, the Sentinel-2 plan still fits its budget', r && r.alb.src === 's2' && r.alb.count <= PLAN.maxS2Tiles && r.elev.count <= PLAN.maxElevTiles, r ? `level ${r.alb.L}, ${r.alb.count} tiles, margin ${r.margin}` : 'no plan'); }
  ok('plan: the lights\' tiles are the imagery\'s own rows and columns', GIBS.nightUrl(7, 24, 27).endsWith('/500m/7/24/27.png') && GIBS.url(7, 24, 27).endsWith('/500m/7/24/27.jpeg'));
}

// despike: bad heights in the terrain tiles go, terrain stays
{
  const w = 60, h = 50, g = new Float32Array(w * h);
  // a 45 degree slope at 30 m a texel, with a sharp ridge crest down the middle and a gully across it
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) g[y * w + x] = 2000 - 30 * Math.abs(x - 30) - 20 * Math.abs(y - 25);
  const clean = Float32Array.from(g);
  ok('despike: a 45 degree ridge and gully at 30 m a texel are left alone', despike(g, w, h, 40) === 0 && g.every((v, i) => v === clean[i]));
  g[10 * w + 12] = -1895; g[30 * w + 40] -= 300; g[30 * w + 41] -= 300; g[40 * w + 20] += 500;       // Manhattan's pit, a pit two texels wide, a spike
  const n = despike(g, w, h, 40);
  let worst = 0; for (let i = 0; i < g.length; i++) worst = Math.max(worst, Math.abs(g[i] - clean[i]));
  ok('despike: a 1900 m pit, a pit two texels wide and a spike are taken out, to within the slope across a texel', n >= 4 && n <= 8 && worst <= 30, `${n} texels changed, worst left ${worst.toFixed(0)} m`);
}

// land or water in the window: the mask's tiles, its sampling, and the rule (scored on real places by audit_closewater.py)
{
  ok('water mask: the tiles are the "250m" set, one level past Blue Marble', GIBS.waterUrl(8, 44, 96).endsWith('/MODIS_Water_Mask/default/250m/8/44/96.png') && Math.abs(gibsTexelDeg(8) * KM_PER_DEG - 0.2443) < 1e-3);
  const cam = new Camera(); cam.resize(1440, 900); cam.setView('globe'); cam.lookAt(-73.99, 40.75); cam.setKmPerPx(0.05);
  const plan = planDetail(viewBox(cam), 0.05), mp = maskPlan(plan.win, plan.elev);
  const holds = mp.win.west <= plan.win.west + 1e-9 && mp.win.north >= plan.win.north - 1e-9 && mp.win.west + mp.win.lonSpan >= plan.win.west + plan.win.lonSpan - 1e-9 && mp.win.north - mp.win.latSpan <= plan.win.north - plan.win.latSpan + 1e-9;
  ok('water mask: at 50 m a pixel it is level 8, a handful of tiles, and holds the window', mp.L === 8 && mp.count <= 4 && mp.tiles.length === mp.count && holds, `level ${mp.L}, ${mp.count} tiles, ${mp.w} x ${mp.h}`);
  cam.setKmPerPx(3); const far = planDetail(viewBox(cam), 3), mf = maskPlan(far.win, far.elev);
  ok('water mask: at 3 km a pixel its texel is no coarser than the grid it is sampled to, within the request budget', mf.texelDeg <= far.elev.texelDeg[1] * 1.0001 || mf.count === PLAN.maxTiles ? mf.count <= PLAN.maxTiles : false, `level ${mf.L}, ${mf.count} tiles`);
  // sampling: a mosaic whose west half is water, read at the centres of a finer grid over a window inside it
  const m = { w: 8, h: 4, texelDeg: 0.5, win: { west: 10, north: 50, lonSpan: 4, latSpan: 2 } }, px = new Uint8ClampedArray(8 * 4 * 4);
  for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) px[(y * 8 + x) * 4 + 3] = 255;
  const sm = sampleMask(px, m, { west: 11, north: 49.5, lonSpan: 2, latSpan: 1 }, 20, 10);
  ok('water mask: sampled where it is, the shore at the right longitude', sm.every((v, i) => v === ((i % 20) < 10 ? 1 : 0)));
  const bm = boxMean(Uint8Array.from({ length: 100 }, (_, i) => ((i % 10) < 5 ? 1 : 0)), 10, 10, 3);
  ok('boxMean: a 3 x 3 mean, edges repeated', Math.abs(bm[0] - 1) < 1e-6 && Math.abs(bm[4] - 2 / 3) < 1e-6 && Math.abs(bm[5] - 1 / 3) < 1e-6 && Math.abs(bm[99]) < 1e-6);
  // the rule: sea west of column 60; the mask puts the shore at column 66; land is green fields
  const w = 160, h = 120, rgba = new Uint8ClampedArray(w * h * 4), mask = new Uint8Array(w * h), elev = new Float32Array(w * h);
  let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff - 0.5; };
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const o = y * w + x, sea = x < 60, c = sea ? [22, 40, 62] : [120, 125, 90], a = sea ? 8 : 28;
    for (let k = 0; k < 3; k++) rgba[o * 4 + k] = c[k] + a * rnd();
    rgba[o * 4 + 3] = 255; mask[o] = x < 66 ? 1 : 0; elev[o] = sea ? 0 : 10 + 3 * rnd();
  }
  const info = {}, f = waterFlag({ w, h, rgba, elev, mask, ship: null, mx: 19, my: 19, cell: 13 }, info);
  let wrong = 0; for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (f[y * w + x] !== (x < 60 ? 1 : 0)) wrong++;
  ok('waterFlag: the shore is where the picture has it, six texels from where the mask has it', wrong <= 0.002 * w * h && info.seedWater > 1000 && info.seedLand > 1000, `${wrong} texels of ${w * h} wrong`);
  ok('waterFlag: with no picture the mask is the answer', waterFlag({ w, h, rgba: null, elev, mask, mx: 19, my: 19, cell: 13 }).every((v, i) => v === mask[i]));
  ok('waterFlag: a window the mask has no water in has none', waterFlag({ w, h, rgba, elev, mask: new Uint8Array(w * h), mx: 19, my: 19, cell: 13 }).every((v) => v === 0));
}

// the water record's tiles (JRC), the quick first pass, and the window's water colour
{
  ok('water record: the tiles are Web Mercator x/y like the terrain, to zoom 13', JRC.url(12, 1206, 1539).endsWith('/tiles2021/occurrence/12/1206/1539.png') && JRC.maxZoom === 13);
  // a tile whose west half is water (alpha 250), resampled onto an equirectangular grid inside it: the shore stays at the tile's middle longitude
  const z = 10, tx = 301, ty = 384, b = terrTileBounds(tx, ty, z), tile = new Uint8Array(65536);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 128; x++) tile[y * 256 + x] = 250;
  const win = { west: b.west + (b.east - b.west) * 0.25, north: b.north - (b.north - b.south) * 0.25, lonSpan: (b.east - b.west) * 0.5, latSpan: (b.north - b.south) * 0.5 };
  const g = resampleMercator(win, z, 100, 60, (x, y) => (x === tx && y === ty ? tile : null));
  let bad = 0; for (let j = 0; j < 60; j++) for (let i = 0; i < 100; i++) { const v = g[j * 100 + i]; if (i < 49 ? Math.abs(v - 250) > 1e-3 : i > 50 ? Math.abs(v) > 1e-3 : !(v >= 0 && v <= 250)) bad++; }
  ok('water record: resampled through the elevation\'s own frame conversion, the shore is where the tile has it', bad === 0 && g[30 * 100 + 49] > g[30 * 100 + 50], `${bad} texels off`);
  // the quick pass: the same rectangle, two levels coarser in both layers, on whole texels of both
  const cam = new Camera(); cam.resize(1440, 900); cam.setView('globe'); cam.lookAt(2.35, 48.86); cam.setKmPerPx(0.02);
  const p = planDetail(viewBox(cam), 0.02), q = quickPlan(p);
  const whole = (v) => Math.abs(v - Math.round(v)) < 1e-6;
  ok('quick pass: one rectangle for both passes, two levels coarser, a sixteenth of the imagery requests or fewer plus the edge', q && q.win === p.win && q.alb.L === p.alb.L - 2 && q.alb.src === p.alb.src && q.elev.z === p.elev.z - 2
    && whole(p.win.lonSpan / q.alb.texelDeg) && whole(p.win.latSpan / q.alb.texelDeg) && q.alb.w * 4 === p.alb.w && q.alb.h * 4 === p.alb.h && q.alb.count <= p.alb.count / 16 + 12 && q.night === p.night,
  q ? `full ${p.alb.count} + ${p.elev.count} requests (${p.alb.w} x ${p.alb.h}), quick ${q.alb.count} + ${q.elev.count} (${q.alb.w} x ${q.alb.h})` : 'no quick plan');
  { const c2 = new Camera(); c2.resize(1440, 900); c2.setView('globe'); c2.setKmPerPx(0.3);
    const at = (lon, lat) => { c2.lookAt(lon, lat); return jrcCovers(planDetail(viewBox(c2), 0.3).elev); };
    ok('water record: asked for at Paris and Tierra del Fuego, not on Svalbard or the Antarctic Peninsula', at(2.35, 48.86) && at(-68.3, -54.8) && !at(16, 78.6) && !at(-62.9, -64.8)); }
  cam.setKmPerPx(4.5); const far = planDetail(viewBox(cam), 4.5);
  ok('quick pass: a window of few requests has none', far && (far.alb.count + far.elev.count >= PLAN.quickLeast || quickPlan(far) === null) && quickPlan({ ...p, streets: null, alb: { ...p.alb, count: 4 }, elev: { ...p.elev, count: 4 } }) === null);
  ok('quick pass: a window with streets always has one, so the picture is up before they are drawn', !!p.streets && quickPlan({ ...p, alb: { ...p.alb, count: 4 }, elev: { ...p.elev, count: 4 } }) !== null && quickPlan(p).streets === null);
  // the window's water colour: the mean of the picture where the flag is water, however the two grids differ
  const th = { w: 8, h: 4, d: new Uint8ClampedArray(8 * 4 * 4) }, fl = new Uint8Array(16 * 12);
  for (let j = 0; j < 4; j++) for (let i = 0; i < 8; i++) { const o = (j * 8 + i) * 4, wat = i < 4; th.d[o] = wat ? 20 : 200; th.d[o + 1] = wat ? 40 : 180; th.d[o + 2] = wat ? 60 : 150; th.d[o + 3] = 255; }
  for (let j = 0; j < 12; j++) for (let i = 0; i < 16; i++) fl[j * 16 + i] = i < 8 ? 1 : 0;
  const wc = waterColour({ w: 80, h: 40, d: (() => { const d = new Uint8ClampedArray(80 * 40 * 4); for (let j = 0; j < 40; j++) for (let i = 0; i < 80; i++) { const o = (j * 80 + i) * 4, s = (Math.floor(j / 10) * 8 + Math.floor(i / 10)) * 4; d[o] = th.d[s]; d[o + 1] = th.d[s + 1]; d[o + 2] = th.d[s + 2]; d[o + 3] = 255; } return d; })() }, fl, 16, 12);
  ok('water colour: the picture\'s mean where the flag is water, and nothing for a window with no water', wc && Math.abs(wc[0] - 20 / 255) < 1e-6 && Math.abs(wc[1] - 40 / 255) < 1e-6 && Math.abs(wc[2] - 60 / 255) < 1e-6 && waterColour(th, new Uint8Array(16 * 12), 16, 12) === null);
}

// ------------------------------------------------------------------ the cards' text: the year at a place, and Wikipedia's lead
{
  const { koppen, yearSentences, monthlySeries, daylightMonthly, hoursText, climateChart, climateTable, ticks, koppenName } = await import('../web/js/climate.js');
  const { wikiKey, articleFor, trimLead, sentenceEnds, parseLead, leadUrl, articleUrl, LEAD_CAP } = await import('../web/js/wiki.js');
  // Köppen-Geiger on twelve synthetic months whose class is known (station normals, rounded; the class is each station's published one)
  const K = [
    ['Af', 'a wet equatorial year', [26.5, 27, 27.5, 28, 28.3, 28.3, 27.9, 27.9, 27.6, 27.6, 27, 26.4], [240, 110, 170, 150, 170, 130, 150, 150, 160, 160, 250, 250]],
    ['Am', 'a short dry season under a very wet year', [27, 27.5, 28.5, 29, 28.5, 26.5, 26, 26, 26.5, 27, 27.5, 27], [20, 25, 40, 110, 300, 700, 600, 350, 250, 300, 150, 40]],
    ['Aw', 'a monsoon with a rainless winter', [24, 24.5, 27, 28.5, 30, 29, 27.5, 27, 27.5, 28.5, 27.5, 25.5], [1, 1, 0, 1, 15, 520, 850, 500, 320, 75, 15, 3]],
    ['BWh', 'a hot desert', [14, 15, 17.5, 21.5, 25, 27.5, 28, 28, 26.5, 23.5, 19, 15], [5, 4, 4, 1, 0.5, 0, 0, 0, 0, 1, 4, 6]],
    ['BSk', 'a cold steppe with summer rain', [-1, 0.5, 4.5, 9, 14, 19.5, 23, 22, 17, 10.5, 4, -0.5], [12, 12, 30, 45, 60, 45, 50, 45, 30, 25, 18, 12]],
    ['Csa', 'a hot dry summer and a wet winter', [8, 9, 11, 14, 18, 22, 25, 25, 21, 17, 12, 9], [70, 70, 60, 60, 40, 20, 15, 25, 70, 100, 110, 90]],
    ['Csb', 'the same in the southern hemisphere, with a warm summer', [21, 20, 18, 15, 12, 9.5, 9, 10.5, 12.5, 15, 17.5, 20], [0.5, 1, 3, 13, 58, 80, 73, 52, 24, 13, 6, 2]],
    ['Cfb', 'a mild wet ocean climate', [5, 5.5, 7, 10, 13, 16, 18.4, 18, 15, 12, 8, 5.5], [55, 40, 42, 44, 49, 45, 45, 50, 49, 69, 59, 55]],
    ['Cfa', 'a hot humid summer', [6, 7, 10, 15, 20, 24, 27, 26.5, 23, 17, 11, 7], [50, 60, 110, 130, 140, 170, 150, 170, 210, 200, 90, 50]],
    ['Cwa', 'a subtropical dry winter', [14, 16.5, 21.5, 26, 28, 28.5, 28, 27.5, 27, 24.5, 19.5, 15], [18, 20, 15, 30, 60, 220, 330, 300, 190, 60, 8, 8]],
    ['Dfb', 'a continental year with a warm summer', [-6.5, -6.7, -1, 6.7, 13.2, 17, 19.2, 17, 11.3, 5.6, -1.2, -5.2], [52, 41, 35, 37, 49, 80, 85, 82, 68, 71, 55, 52]],
    ['Dwa', 'a continental year with a dry winter and a hot summer', [-3, 0, 6, 14, 20, 24.5, 26.5, 25, 20, 13, 5, -1], [3, 5, 8, 21, 34, 78, 185, 160, 45, 22, 7, 3]],
    ['Dfc', 'a subarctic year', [-23, -20, -12, -2, 7, 14, 16, 13, 6.5, -3, -15, -21], [20, 15, 15, 15, 30, 50, 65, 60, 45, 35, 30, 25]],
    ['Dfd', 'the coldest winters on Earth outside the ice', [-38.6, -33.8, -20.1, -4.8, 7.5, 16.4, 19.5, 15.2, 6.1, -7.8, -27, -37.6], [9, 8, 7, 9, 20, 37, 39, 38, 29, 19, 16, 10]],
    ['ET', 'tundra', [-25, -26, -24, -16, -6, 2, 6, 5, 0.5, -8, -17, -22], [8, 7, 7, 8, 9, 12, 25, 28, 20, 18, 10, 8]],
    ['EF', 'an ice cap', [-28, -40, -54, -57, -58, -58, -60, -60, -59, -51, -38, -28], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]],
  ];
  const wrong = K.filter(([code, , t, p]) => (koppen(t, p) || {}).code !== code).map(([code, , t, p]) => `${code} came out ${(koppen(t, p) || {}).code}`);
  ok(`Köppen-Geiger: ${K.length} synthetic years of known class`, wrong.length === 0, wrong.join('; '));
  ok('Köppen-Geiger: every class it can return has a name, and a year with a missing month has no class', K.every(([code]) => koppenName(code)) && koppenName('Cfb') === 'Temperate, no dry season, warm summer' && koppenName('Dwd') === 'Cold, dry winter, very cold winter' && koppenName('Xx') === null && koppen([1, 2, 3], [1, 2, 3]) === null && koppen(K[0][2], K[0][3].map((v, i) => (i === 4 ? NaN : v))) === null);
  // the sentences, on a known year
  const yr = { t: K[7][2], pmm: K[7][3], day: [8.5, 10, 12, 14, 15.5, 16.5, 16, 14.5, 12.5, 10.5, 9, 8], sst: null };
  const st = yearSentences(yr);
  ok('year sentences: warmest and coldest month with their values', st[0] === 'July is the warmest month, with a mean air temperature of 18.4 °C; January is the coldest, at 5.0 °C.', st[0]);
  ok('year sentences: the year\'s precipitation, its wettest and driest months', st[1] === 'About 600 mm of precipitation falls in a typical year, as a mean over some 250 km. October is the wettest month (69 mm) and February the driest (40 mm).', st[1]);
  ok('year sentences: the range of daylight', st[2] === 'Daylight averages 8 h 00 m a day in December and 16 h 30 m in June.' && st.length === 3, st[2]);
  const flat = yearSentences({ t: K[0][2].map(() => 27), pmm: Array(12).fill(1), day: Array(12).fill(12.1), sst: [28, 28.5, 29, 29, 28.5, 28, 27.5, 27, 27.5, 28, 28, 28] });
  ok('year sentences: a year with no seasons, no rain and a sea under it says so', flat[0] === 'Mean air temperature is 27.0 °C in every month.' && yearSentences({ ...yr, t: K[0][2] })[0].startsWith('Mean air temperature changes little through the year: 26.4 °C in December, 28.3 °C in May') && flat[1] === 'Almost no precipitation falls here: about 12 mm in a typical year.'
    && flat[2] === 'The day is close to 12 h 06 m long all year.' && flat[3] === 'The water’s surface is warmest in March (29.0 °C) and coldest in August (27.0 °C).', flat.join(' | '));
  const polar = yearSentences({ t: K[14][2], pmm: K[14][3], day: [0, 4, 11, 17, 24, 24, 24, 19, 13, 8, 1, 0], sst: null })[2];
  ok('year sentences: polar night and the midnight Sun', polar === 'There is no daylight in January (polar night) and the Sun does not set in May.', polar);
  ok('a length of day in words', hoursText(12.1) === '12 h 06 m' && hoursText(9.999) === '10 h 00 m' && hoursText(0) === 'none' && hoursText(24) === '24 hours');
  // day length by month: London's longest and shortest months (solstice days are 16 h 38 m and 7 h 50 m), the equator, the poles' side
  const dl = daylightMonthly(51.5, 2026), eq = daylightMonthly(0, 2026), hi = daylightMonthly(80, 2026);
  ok('monthly day length: London 16.5 h in June and 7.9 h in December; 12.1 h all year on the equator; none and 24 h at 80 N', near(dl[5], 16.5, 0.15) && near(dl[11], 7.9, 0.15) && eq.every((v) => near(v, 12.12, 0.03)) && hi[11] === 0 && hi[5] === 24,
    `${dl[5].toFixed(2)} ${dl[11].toFixed(2)} ${eq[0].toFixed(2)} ${hi[11]} ${hi[5]}`);
  // the twelve months from a field store: lapse to the ground's height, mm a day to mm a month, and nothing when a month is missing
  const store = (over = {}) => ({ has: { climate: true }, meta: { climate: { lapse_K_per_km: 6.5 } }, elevation: () => 1000, waterFrac: () => 0,
    climate: (name, lon, lat, ms) => (name === 't0' ? 20 + ms.i0 : name === 'precip' ? 2 : NaN), ...over });
  const s1 = monthlySeries(store(), 10, 50, 2026);
  ok('monthly series: sea-level temperature taken 1000 m up at 6.5 K a km; 2 mm a day is 62 mm in January and 56 in February', s1.ok && near(s1.t[0], 13.5, 1e-9) && near(s1.t[11], 24.5, 1e-9) && s1.pmm[0] === 62 && s1.pmm[1] === 56 && s1.sst === null && s1.day.length === 12);
  const s2 = monthlySeries(store({ waterFrac: () => 1, elevation: () => -3000, climate: (name, lon, lat, ms) => (name === 't0' ? 20 : name === 'precip' ? 1 : name === 'sst' ? 18 + ms.i0 : NaN) }), 10, 50, 2026);
  ok('monthly series: over water the sea floor is not a height and the sea\'s own temperature comes too', s2.ok && s2.water && s2.t[0] === 20 && s2.sst && s2.sst[11] === 29);
  const s3 = monthlySeries(store({ waterFrac: () => 1, elevation: () => 200 }), 10, 50, 2026, false);
  ok('monthly series: a card that knows it is on land is on land, whatever the mask says of its cell', s3.ok && !s3.water && s3.sst === null && near(s3.t[0], 20 - 1.3, 1e-9));
  ok('monthly series: a field not loaded, or silent in one month, gives no series and a reason', !monthlySeries(store({ has: { climate: false } }), 0, 0, 2026).ok && !monthlySeries(store({ elevation: () => NaN }), 0, 0, 2026).ok
    && !monthlySeries(store({ climate: (name, lon, lat, ms) => (ms.i0 === 7 ? NaN : 5) }), 0, 0, 2026).ok && typeof monthlySeries(store({ elevation: () => NaN }), 0, 0, 2026).why === 'string');
  const svg = climateChart(s1, 10), tab = climateTable(s1, 10);
  ok('climate chart: twelve bars, twelve hit areas with their values, one marked month, and no number that was not computed',
    (svg.match(/<path /g) || []).length === 12 && (svg.match(/<title>/g) || []).length === 12 && (svg.match(/class="cm on"/g) || []).length === 1 && !/NaN|undefined|Infinity/.test(svg + tab) && (tab.match(/<tr/g) || []).length === 13);
  ok('axis labels are round values inside the range', ticks(-12.3, 24.1, 3).join() === '0,20' && ticks(0, 187, 2).join() === '0,100' && ticks(25.2, 27.9, 3).join() === '26,27');

  // Wikipedia's lead: cut at a sentence end, inside the cap, abbreviations not taken for ends
  const lead = 'Tokyo (; Japanese: 東京), officially the Tokyo Metropolis ( ), is the capital of Japan. It lies on Honshu, near Mt. Fuji and the U.S. base at Yokosuka. Its population was 14 million in 2023.\nA second paragraph follows here. It has two sentences.';
  const whole = trimLead(lead), part = trimLead(lead, 120), tiny = trimLead('One very long sentence without any full stop that simply goes on and on past the cap', 30);
  ok('lead: under the cap it is shown whole, by paragraph, with the empty brackets a plain-text extract leaves taken out', !whole.cut && whole.paras.length === 2 && whole.paras[0].startsWith('Tokyo (Japanese: 東京), officially the Tokyo Metropolis, is the capital'));
  ok('lead: over the cap it ends at the last sentence that fits, and "Mt." and "U.S." are not sentence ends', part.cut && part.paras.length === 1 && part.paras[0].endsWith('is the capital of Japan.') && part.paras.join('').length <= 120
    && sentenceEnds('It lies near Mt. Fuji and the U.S. base. Next.').length === 2, JSON.stringify(part));
  ok('lead: a first sentence longer than the cap is cut at a word and marked', tiny.cut && tiny.paras[0].endsWith(' …') && tiny.paras[0].length <= 32);
  { let over = 0; for (let cap = 40; cap < lead.length + 20; cap += 7) { const r = trimLead(lead, cap); if (r.paras.join('').replace(/ …$/, '').length > cap) over++; } ok('lead: never longer than the cap, at any cap', over === 0, `${over} caps exceeded`); }
  const pl = parseLead({ query: { pages: [{ pageid: 1, title: 'Tokyo', extract: lead, fullurl: 'https://en.wikipedia.org/wiki/Tokyo' }] } });
  ok('lead: the answer is read as a title, an address and paragraphs', pl.title === 'Tokyo' && pl.url === 'https://en.wikipedia.org/wiki/Tokyo' && pl.paras.length === 2 && !pl.cut && LEAD_CAP >= 1000);
  ok('lead: an address that is not the article on en.wikipedia.org is not used', parseLead({ query: { pages: [{ title: 'São Paulo', extract: 'x.', fullurl: 'javascript:alert(1)' }] } }).url === 'https://en.wikipedia.org/wiki/S%C3%A3o_Paulo' && articleUrl('A b') === 'https://en.wikipedia.org/wiki/A_b');
  { let threw = 0; for (const j of [null, {}, { query: { pages: [] } }, { query: { pages: [{ title: 'X', missing: true }] } }]) { try { parseLead(j); } catch (e) { threw++; } } ok('lead: a missing article or a malformed answer is an error, not an empty description', threw === 4); }
  ok('the request names the article and nothing else', leadUrl('Côte d\'Ivoire') === 'https://en.wikipedia.org/w/api.php?action=query&prop=extracts|info&exintro=1&explaintext=1&redirects=1&inprop=url&format=json&formatversion=2&origin=*&titles=C%C3%B4te%20d\'Ivoire');

  // which article belongs to which card: the page's own key rule over the shipped files, against the counts the build wrote
  ok('card keys: a city, a state, a dispute, a feature, a peak, a river', wikiKey('city', ['Tokyo', 139.749, 35.687]) === 'Tokyo|139.749|35.687' && wikiKey('country', { a3: 'JPN' }) === 'JPN'
    && wikiKey('dispute', { name: 'Crimea', note: 'Admin. by Russia; Claimed by Ukraine' }) === 'Crimea|Admin. by Russia; Claimed by Ukraine' && wikiKey('feature', { name: 'X', kind: 'sea', lon: -0, lat: 12.5 }) === 'X|sea|0.000|12.500'
    && wikiKey('peak', { name: 'Y', lon: 86.881, lat: 27.98 }) === 'Y|86.881|27.980' && wikiKey('river', { name: 'Z', lines: [[5194, 5570, 5188, 5569]] }) === 'Z|5194|5570' && wikiKey('river', { name: 'Z', lines: [] }) === '');
  const D = (f) => new URL(`../web/data/${f}`, import.meta.url);
  if (existsSync(D('wiki.json'))) {
    const W = JSON.parse(readFileSync(D('wiki.json'), 'utf8')), rd = (f) => JSON.parse(readFileSync(D(f), 'utf8'));
    const places = rd('places.json'), pol = rd('political.json'), phys = rd('physical.json'), volc = rd('volcanoes.json');
    const sets = { city: places.rows, country: pol.countries, dispute: pol.disputes, feature: phys.features, peak: phys.peaks.filter((p) => p.name),
      river: phys.rivers.filter((r) => r.name && r.lines.length && r.lines[0].length), volcano: volc.rows };
    const off = [];
    for (const [kind, cards] of Object.entries(sets)) {
      const hit = cards.filter((c) => articleFor(kind, wikiKey(kind, c), W)).length;
      if (hit !== W.counts[kind][0] || cards.length !== W.counts[kind][1]) off.push(`${kind}: the page finds ${hit} of ${cards.length}, the build wrote ${W.counts[kind].join(' of ')}`);
    }
    ok('card keys: the page finds an article for exactly the cards the build matched, kind by kind', off.length === 0, off.join('; ') || Object.entries(W.counts).map(([k, v]) => `${k} ${v[0]}/${v[1]}`).join(', '));
    const tokyo = articleFor('city', wikiKey('city', places.rows.find((r) => r[0] === 'Tokyo')), W), jp = articleFor('country', 'JPN', W);
    ok('card keys: Tokyo\'s card has the article Tokyo and Japan\'s has Japan', tokyo && tokyo.title === 'Tokyo' && tokyo.qid === 'Q1490' && jp && jp.title === 'Japan' && articleFor('country', 'XXX', W) === null && articleFor('city', 'x') === undefined);
  } else ok('card keys: web/data/wiki.json is there to check (build/wiki_titles.py)', false);
}

// ---------------------------------------------------------------- streets and buildings (streets.js, register F15)
{
  const { OFM, STREETS, ROADS, FILLS, streetPlan, decodeTile, frame, tileXY, tileLon, tileLat, shadowOffset } = await import('../web/js/streets.js');
  const D = await import('../web/js/detail.js');
  // a vector tile written here, byte by byte, to the published format: what the decoder must read back is known
  const varint = (v) => { const o = []; while (v > 127) { o.push((v & 127) | 128); v = Math.floor(v / 128); } o.push(v); return o; };
  const tag = (f, w) => varint(f * 8 + w);
  const bytes = (f, b) => [...tag(f, 2), ...varint(b.length), ...b];
  const str = (f, s) => bytes(f, [...new TextEncoder().encode(s)]);
  const zz = (v) => (v < 0 ? -2 * v - 1 : 2 * v);
  const geom = (pts, close) => [...varint(1 * 8 + 1), ...varint(zz(pts[0][0])), ...varint(zz(pts[0][1])), ...varint((pts.length - 1) * 8 + 2), ...pts.slice(1).flatMap((p, i) => [...varint(zz(p[0] - pts[i][0])), ...varint(zz(p[1] - pts[i][1]))]), ...(close ? varint(7 + 8) : [])];
  const feature = (type, tags, g) => [...bytes(2, tags.flatMap((t) => varint(t))), ...tag(3, 0), ...varint(type), ...bytes(4, g)];
  const layer = (name, keys, vals, feats) => [...tag(15, 0), ...varint(2), ...str(1, name), ...feats.flatMap((f) => bytes(2, f)), ...keys.flatMap((k) => str(3, k)), ...vals.flatMap((v) => bytes(4, typeof v === 'string' ? str(1, v) : [...tag(4, 0), ...varint(v)])), ...tag(5, 0), ...varint(4096)];
  const tile = new Uint8Array([
    ...bytes(3, layer('transportation', ['class', 'brunnel'], ['primary', 'minor', 'tunnel', 'rail', 'path'], [
      feature(2, [0, 0], geom([[0, 0], [4096, 0], [4096, 2048]])),              // a main street
      feature(2, [0, 1, 1, 2], geom([[10, 10], [20, 20]])),                     // a side street in a tunnel: left out
      feature(2, [0, 3], geom([[5, 5], [6, 5]])),                               // a railway
      feature(2, [0, 4], geom([[1, 1], [2, 2]])),                               // a footpath: not drawn
      feature(1, [0, 0], [...varint(1 * 8 + 1), ...varint(zz(7)), ...varint(zz(7))]),   // a point in a line layer: not drawn
    ])),
    ...bytes(3, layer('building', ['render_height'], [30], [feature(3, [0, 0], geom([[100, 100], [200, 100], [200, 200], [100, 200]], true)), feature(3, [], geom([[-50, 300], [50, 300], [50, 400]], true))])),
    ...bytes(3, layer('landuse', ['class'], ['commercial', 'cemetery'], [feature(3, [0, 0], geom([[0, 0], [10, 0], [10, 10]], true)), feature(3, [0, 1], geom([[0, 0], [10, 0], [10, 10]], true))])),
    ...bytes(3, layer('poi', ['name'], ['a shop'], [feature(1, [0, 0], [...varint(9), ...varint(2), ...varint(2)])])),
  ]);
  const d = decodeTile(tile);
  ok('streets: a tile written to the published format is read back: one main street with its three points, the tunnel, the path and the stray point left out',
    Object.keys(d.roads).join() === 'primary' && d.roads.primary.length === 1 && [...d.roads.primary[0]].join() === '0,0,4096,0,4096,2048' && d.extent === 4096, JSON.stringify(Object.fromEntries(Object.entries(d.roads).map(([k, v]) => [k, v.length]))));
  ok('streets: the railway is kept apart from the roads', d.rail.length === 1 && [...d.rail[0]].join() === '5,5,6,5');
  ok('streets: a building keeps its height and its closed ring; one without a height gets the default; a point beyond the tile edge is kept (lines must join)',
    d.buildings.length === 2 && d.buildings[0].h === 30 && [...d.buildings[0].rings[0]].join() === '100,100,200,100,200,200,100,200,100,100' && d.buildings[1].h === STREETS.defaultH && d.buildings[1].rings[0][0] === -50);
  ok('streets: commercial ground is kept and a cemetery is not; a layer the atlas does not draw is skipped', Object.keys(d.fills).join() === 'commercial' && d.fills.commercial.length === 1);
  ok('streets: a tile cut short is an error, not a wrong answer', (() => { try { decodeTile(tile.subarray(0, 40)); return false; } catch (e) { return /cut short/.test(e.message); } })());
  ok('streets: every road is 0.5 or over in the pattern and every filled ground under 0.3, so one channel tells them apart', Object.values(ROADS).every((r) => r.light >= 0.5 && r.light <= 1) && Object.values(FILLS).every((v) => v < 0.3 && v > 0.05));
  // the frame: Web Mercator tile coordinates against known places
  const [gx, gy] = tileXY(0, 0, 3);
  ok('streets: longitude 0, latitude 0 is the middle of the tile grid; the grid\'s top is 85.0511 N', near(gx, 4, 1e-12) && near(gy, 4, 1e-9) && near(tileLat(0, 5), 85.0511287798, 1e-9) && near(tileLon(2 ** 14, 14), 180, 1e-12));
  const [px, py] = tileXY(2.3376, 48.8606, 14);
  ok('streets: the Louvre is in tile 14/8298/5636 (OpenStreetMap\'s own numbering), and there and back is exact', Math.floor(px) === 8298 && Math.floor(py) === 5636 && near(tileLon(px, 14), 2.3376, 1e-10) && near(tileLat(py, 14), 48.8606, 1e-10), `${px.toFixed(2)}, ${py.toFixed(2)}`);
  // the plan: the finest zoom that fits the budget; the unwrapped column is kept for placing
  const win5 = { west: 2.28, north: 48.89, lonSpan: 0.12, latSpan: 0.06 };
  const sp = streetPlan(win5);
  ok('streets: a 9 km window at Paris is zoom 14 within the budget and holds its corners', sp && sp.z === 14 && sp.count <= STREETS.maxTiles && sp.tiles.length === sp.count && sp.tiles.some((t) => t.x === 8298 && t.y === 5636), sp && `z${sp.z}, ${sp.count} tiles`);
  const sp2 = streetPlan({ west: 1.5, north: 49.4, lonSpan: 1.6, latSpan: 1.0 });
  ok('streets: a 120 km window drops to the zoom that fits', sp2 && sp2.z < 12 && sp2.z >= OFM.minZoom && sp2.count <= STREETS.maxTiles, sp2 && `z${sp2.z}, ${sp2.count} tiles`);
  ok('streets: no plan beyond Web Mercator\'s reach', streetPlan({ west: 10, north: 86, lonSpan: 0.1, latSpan: 0.05 }) === null);
  const spw = streetPlan({ west: 179.95, north: 10.05, lonSpan: 0.1, latSpan: 0.1 });
  ok('streets: across the date line the tiles wrap and the unwrapped column runs on', spw && spw.tiles.some((t) => t.x === 0 && t.ox === 2 ** spw.z) && spw.tiles.every((t) => t.x >= 0 && t.x < 2 ** spw.z));
  // the drawing frame: metres, so a road is as wide north-south as east-west
  const fr = frame(win5, 4000, 2000);
  ok('streets: the canvas is drawn in metres: a degree of longitude at 48.86 N is 73.2 km and the scale is finer east-west than north-south by its cosine',
    near(fr.mx(win5.west + 1), 111195 * Math.cos(48.86 * Math.PI / 180), 1) && near(fr.my(win5.north - 1), 111195, 1e-6) && near(fr.sx / fr.sy, (4000 / 0.12) / (2000 / 0.06) / Math.cos(48.86 * Math.PI / 180), 1e-9), `${fr.sx.toFixed(4)} ${fr.sy.toFixed(4)} px/m`);
  const [sx, sy] = shadowOffset(100, 48), [, sy2] = shadowOffset(100, -34);
  ok('streets: a 100 m tower throws 62 m of shadow, to the north-west north of the equator and the south-west south of it', near(Math.hypot(sx, sy), 62, 1e-9) && sx < 0 && sy < 0 && sy2 > 0);
  // the planner with streets: the zoom floor, the magnified grid, the pixel budget
  const cam5 = new Camera(); cam5.resize(1440, 900, 2); cam5.lookAt(2.3376, 48.8606); cam5.setKmPerPx(0.005);
  ok('camera: the zoom floor is 5 m a pixel and the globe camera reaches it', near(cam5.kmPerPx(), 0.005, 1e-9), `${cam5.kmPerPx()}`);
  const p5 = planDetail(viewBox(cam5), cam5.kmPerPx());
  ok('plan: at 5 m a pixel the grid is finer than Sentinel-2 (its level-13 tiles magnified), within the texel budget, with streets at zoom 14',
    p5 && p5.alb.src === 's2' && p5.alb.L === S2.maxLevel && p5.alb.mag >= 2 && p5.alb.w === p5.alb.sw * p5.alb.mag && p5.alb.w * p5.alb.h <= PLAN.maxPx && p5.alb.texelKm <= 0.0049 && p5.streets && p5.streets.z === 14 && p5.streets.count <= STREETS.maxTiles && windowHolds(p5.win, viewBox(cam5), PLAN.fullView),
    p5 && `grid level ${p5.alb.VL} (x${p5.alb.mag}), ${p5.alb.w} x ${p5.alb.h}, ${p5.alb.count} tiles, streets z${p5.streets && p5.streets.z} x ${p5.streets && p5.streets.count}`);
  ok('plan: the magnified grid starts on a whole source texel, so the mosaic magnifies without a seam', p5 && Number.isInteger(Math.round(((p5.win.west + 180) / s2TexelDeg(S2.maxLevel)) * 1e6) / 1e6) && near(p5.alb.sw * s2TexelDeg(S2.maxLevel), p5.win.lonSpan, 1e-9));
  cam5.setKmPerPx(0.2);
  const pFar = planDetail(viewBox(cam5), cam5.kmPerPx());
  ok('plan: at 200 m a pixel there are no streets, and with streets refused there are none at 5 m', pFar && pFar.streets === null && (() => { cam5.setKmPerPx(0.005); const q = planDetail(viewBox(cam5), 0.005, { noStreets: true }); return q && q.streets === null; })());
  // the season reference's packing (register A16)
  ok('season: three bytes ride in one float exactly, and come apart as the shader takes them apart', (() => {
    for (const [a, r, b] of [[0, 0, 0], [1, 255, 255], [0.5, 17, 200], [0.2, 255, 0]]) {
      const pk = Math.fround(D.packDet(a, r, b)), A = Math.floor(pk / 65536), R = Math.floor((pk - A * 65536) / 256), B = pk - A * 65536 - R * 256;
      if (A !== Math.round(a * 255) || R !== r || B !== b) return false;
    }
    return true;
  })());
  ok('season: a colour ratio survives its byte to within 1%, from 0.1 to 2.4', [0.1, 0.19, 0.5, 1, 1.6, 2.4].every((v) => Math.abs(D.seasonRatio(D.seasonCode(v)) / v - 1) < 0.01) && D.seasonCode(0.01) === 0 && D.seasonCode(9) === 255);
  const shader = readFileSync(new URL('../web/shaders/earth.frag.glsl', import.meta.url), 'utf8');
  const lut = D.albedoLut(shader);
  ok('season: the albedo table is read out of the shader itself: nine knots, rising, black at 0', lut.length === 9 && lut[0].every((v) => v === 0) && lut.every((q, i) => i === 0 || q.every((v, k) => v > lut[i - 1][k])) && near(D.lutAlbedo(lut, 255, 0), lut[8][0], 1e-12) && near(D.lutAlbedo(lut, 255 / 16, 1), lut[1][1] / 2, 1e-12));
  ok('season: the shader unpacks with the same constants the page packs with', /0\.08 \* exp\(r \/ 255\.0 \* 3\.4420\)/.test(shader) && near(Math.log(2.5 / 0.08), 3.4420, 1e-4));
}

console.log(bad ? `\napp math: ${bad} FAILURES` : '\napp math: ALL PASS');
process.exit(bad ? 1 : 0);
