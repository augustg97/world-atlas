// The focus window (register A2). The shipped fields stop at 5 km a texel (10 km for elevation);
// closer in than that the app streams finer imagery and elevation for the part of the Earth in
// view and hands them to the substrate shader as two textures over one lon/lat rectangle.
//
//   imagery    NASA GIBS WMTS, EPSG:4326, layer BlueMarble_NextGeneration (August 2004), tile matrix
//              set "500m". Equirectangular 512 px tiles: compositing is a copy.
//   imagery, finer   Sentinel-2 cloudless 2016 by EOX (https://s2maps.eu; contains modified Copernicus Sentinel data
//              2016; CC BY 4.0), WMTS at tiles.maps.eox.at, layer "s2cloudless", tile matrix set "WGS84": the
//              atlas's own equirectangular frame, 256 px tiles, 10 m at its finest. Used where the view wants a
//              texel finer than Blue Marble's last level (0.49 km). The owner approved the host on 2026-11-11.
//              EOX asks for the attribution on the map itself: main.js shows it while these tiles are on screen.
//   lights     the same service and the same tiling as Blue Marble, layer VIIRS_Black_Marble (2016): the picture the shipped
//              night lights were made from, at 500 m. Fetched only while part of the view is in the dark, and
//              carried in the imagery texture's fourth channel (there is no seventeenth sampler: fields.js UNIT).
//   elevation  Terrain Tiles on AWS (Mapzen/Tilezen "terrarium" PNG), Web Mercator 256 px tiles,
//              resampled here to the atlas's equirectangular frame.
//
// The top half of this file is pure mathematics (no DOM, no GL) and is tested by
// build/test_app_math.mjs: tile <-> lon/lat for both tilings, the Mercator row resampling, the
// window planner and the elevation compositor. A wrong frame conversion is the most expensive
// class of bug in this project (CLAUDE.md, "The canonical frame"); change nothing here without
// running that test.

import { UNIT } from './fields.js?v=20261111T235202Z';
import { stamped } from './gl.js?v=20261111T235202Z';
import { R_KM } from './camera.js?v=20261111T235202Z';
import { WATER_RULE, boxMean, waterFlag, runRule } from './water.js?v=20261111T235202Z';

const D2R = Math.PI / 180, R2D = 180 / Math.PI;
export const KM_PER_DEG = R_KM * D2R;                       // 111.195 km on the atlas's sphere
export const SHIPPED_ALB_DEG = 360 / 8192;                  // the shipped albedo's texel: 4.89 km

// ============================================================================ NASA GIBS, EPSG:4326
// From https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml : TileMatrixSet
// "500m", top-left corner (-180, 90), 512 px tiles, level 0 a 288 degree tile, each level half the
// last, levels 0-7 (matrix 2x1, 3x2, 5x3, 10x5, 20x10, 40x20, 80x40, 160x80). Rows count from the north.
export const GIBS = {
  layer: 'BlueMarble_NextGeneration', tms: '500m', tilePx: 512, level0Deg: 288, maxLevel: 7,
  url: (L, row, col) => `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/BlueMarble_NextGeneration/default/500m/${L}/${row}/${col}.jpeg`,
  nightUrl: (L, row, col) => `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/VIIRS_Black_Marble/default/2016-01-01/500m/${L}/${row}/${col}.png`,
  // NASA's MODIS land/water mask (MOD44W), tile matrix set "250m": the same tiling one level deeper (level 8 is
  // 244 m). A PNG whose water is opaque and whose land is transparent. See waterFlag below for what it is used for.
  waterMaxLevel: 8,
  waterUrl: (L, row, col) => `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Water_Mask/default/250m/${L}/${row}/${col}.png`,
};
/**
 * Black Marble's display values (0..255) to the brightness of its lights, 0..1.
 * The shipped field (build/fields_surface.py::step_night) is the picture's WARM EXCESS over its moonlit blue base,
 * (R + G) / 2 - 0.62 B: that tells light from moonlit desert and snow, but it stops rising where a city starts (the
 * picture runs amber, then pale, then white, and white is not warm), so a whole basin is one value. Close in the
 * structure inside a city is the point. Here the warm excess only GATES (is this light at all?) and the brightness
 * is the green channel's, which rises all the way to the white cores. NIGHT_SHIPPED of it is the shipped field's
 * full scale: min(1, value / NIGHT_SHIPPED) is the shipped value (measured on Los Angeles and its desert: the
 * means agree to 0.6%, lit pixels to 0.02), which is what the shader uses for everything but the close-in picture.
 */
export const NIGHT_SHIPPED = 0.53;
export const nightLight = (r, g, b) => Math.max(0, Math.min(1, ((r + g) * 0.5 - 0.62 * b - 2) / (95 * 0.25))) * Math.max(0, Math.min(1, (g - 30) / 225));
export const gibsTileDeg = (L) => GIBS.level0Deg / 2 ** L;
export const gibsTexelDeg = (L) => gibsTileDeg(L) / GIBS.tilePx;
export const gibsMatrix = (L) => ({ w: Math.ceil(360 / gibsTileDeg(L) - 1e-9), h: Math.ceil(180 / gibsTileDeg(L) - 1e-9) });
/** Continuous global pixel coordinates at level L: pixel i covers [i, i + 1), its centre is at i + 0.5. */
export const gibsPixel = (lon, lat, L) => [(lon + 180) / gibsTexelDeg(L), (90 - lat) / gibsTexelDeg(L)];
export const gibsLonLat = (gx, gy, L) => [gx * gibsTexelDeg(L) - 180, 90 - gy * gibsTexelDeg(L)];
/** The tile holding a place, and the pixel inside it. */
export function gibsTile(lon, lat, L) {
  const [gx, gy] = gibsPixel(lon, lat, L), m = gibsMatrix(L);
  const col = Math.min(m.w - 1, Math.max(0, Math.floor(gx / GIBS.tilePx))), row = Math.min(m.h - 1, Math.max(0, Math.floor(gy / GIBS.tilePx)));
  return { col, row, px: Math.floor(gx - col * GIBS.tilePx), py: Math.floor(gy - row * GIBS.tilePx) };
}
export function gibsTileBounds(col, row, L) {
  const d = gibsTileDeg(L);
  return { west: -180 + col * d, east: -180 + (col + 1) * d, north: 90 - row * d, south: 90 - (row + 1) * d };
}

// ================================================================ Sentinel-2 cloudless (EOX), EPSG:4326
// From https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml : layer "s2cloudless" (the 2016 mosaic, the one
// edition under CC BY 4.0; 2018 onwards are non-commercial), TileMatrixSet "WGS84", top-left corner (-180, 90),
// 256 px tiles, level 0 two tiles side by side (180 degrees each), each level half the last, levels 0-17. The
// mosaic itself is 10 m, which is level 13 (9.6 m at the equator); beyond that the tiles only magnify.
export const S2 = {
  layer: 's2cloudless', tilePx: 256, level0Deg: 180, minLevel: 8, maxLevel: 13,
  url: (z, row, col) => `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless/default/WGS84/${z}/${row}/${col}.jpg`,
  credit: 'Sentinel-2 cloudless by EOX (contains modified Copernicus Sentinel data 2016)', link: 'https://s2maps.eu',
};
export const s2TileDeg = (z) => S2.level0Deg / 2 ** z;
export const s2TexelDeg = (z) => s2TileDeg(z) / S2.tilePx;
export const s2Matrix = (z) => ({ w: 2 ** (z + 1), h: 2 ** z });
export const s2Pixel = (lon, lat, z) => [(lon + 180) / s2TexelDeg(z), (90 - lat) / s2TexelDeg(z)];
export function s2Tile(lon, lat, z) {
  const [gx, gy] = s2Pixel(lon, lat, z), m = s2Matrix(z);
  const col = Math.min(m.w - 1, Math.max(0, Math.floor(gx / S2.tilePx))), row = Math.min(m.h - 1, Math.max(0, Math.floor(gy / S2.tilePx)));
  return { col, row, px: Math.floor(gx - col * S2.tilePx), py: Math.floor(gy - row * S2.tilePx) };
}
export function s2TileBounds(col, row, z) {
  const d = s2TileDeg(z);
  return { west: -180 + col * d, east: -180 + (col + 1) * d, north: 90 - row * d, south: 90 - (row + 1) * d };
}

// ============================================================ Terrain Tiles (terrarium), Web Mercator
// https://github.com/tilezen/joerd/blob/master/docs/formats.md : 256 px PNG tiles in EPSG:3857,
// elevation in metres = (red * 256 + green + blue / 256) - 32768. Tile (0, 0) is the north-west corner.
export const TERRAIN = {
  tilePx: 256, maxZoom: 15, latMax: 85.0511287798066,
  url: (z, x, y) => `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`,
};
/** Web Mercator y as a fraction of the square: 0 at 85.0511 N, 0.5 at the equator, 1 at 85.0511 S. */
export const mercY = (lat) => 0.5 - Math.log(Math.tan(Math.PI / 4 + (lat * D2R) / 2)) / (2 * Math.PI);
export const mercLat = (y) => (2 * Math.atan(Math.exp((0.5 - y) * 2 * Math.PI)) - Math.PI / 2) * R2D;
/** Continuous global pixel coordinates at zoom z: pixel i covers [i, i + 1), its centre is at i + 0.5. */
export const terrPixel = (lon, lat, z) => { const n = TERRAIN.tilePx * 2 ** z; return [(lon / 360 + 0.5) * n, mercY(lat) * n]; };
export const terrLonLat = (gx, gy, z) => { const n = TERRAIN.tilePx * 2 ** z; return [(gx / n - 0.5) * 360, mercLat(gy / n)]; };
/** The tile holding a place, and the pixel inside it. Latitude is clamped to the Mercator square. */
export function terrTile(lon, lat, z) {
  const n = 2 ** z, [gx, gy] = terrPixel(lon, Math.max(-TERRAIN.latMax, Math.min(TERRAIN.latMax, lat)), z);
  const x = ((Math.floor(gx / 256) % n) + n) % n, y = Math.min(n - 1, Math.max(0, Math.floor(gy / 256)));
  return { x, y, px: Math.min(255, Math.max(0, Math.floor(gx - Math.floor(gx / 256) * 256))), py: Math.min(255, Math.max(0, Math.floor(gy - y * 256))) };
}
export function terrTileBounds(x, y, z) {
  const n = 2 ** z;
  return { west: (x / n - 0.5) * 360, east: ((x + 1) / n - 0.5) * 360, north: mercLat(y / n), south: mercLat((y + 1) / n) };
}
export const terrDecode = (r, g, b) => r * 256 + g + b / 256 - 32768;
/** Degrees of longitude per pixel at zoom z; a pixel's height in latitude is this times cos(lat). */
export const terrTexelDeg = (z) => 360 / (TERRAIN.tilePx * 2 ** z);
export const terrTexelKm = (lat, z) => terrTexelDeg(z) * Math.cos(lat * D2R) * KM_PER_DEG;

// ===================================================================================== resampling
/**
 * The source pixels that make one output sample, and their weights: a tent centred at source
 * coordinate `g` (continuous, pixel centres at integer + 0.5) with half-width max(1, s), where `s`
 * is source pixels per output pixel. Magnifying, that is bilinear interpolation; minifying, it is an
 * area average, so a coarser output never aliases. The weights sum to 1 and their centroid is `g`
 * exactly. Returns [index, weight, index, weight, ...].
 */
export function tentTaps(g, s) {
  const r = Math.max(1, s), c = g - 0.5;                    // c: position in pixel-centre units
  const i0 = Math.ceil(c - r), i1 = Math.floor(c + r), out = [];
  let sum = 0;
  for (let i = i0; i <= i1; i++) { const w = 1 - Math.abs(i - c) / r; if (w > 1e-9) { out.push(i, w); sum += w; } }
  // A sampled tent of non-integer width is not centred on c exactly (by up to 0.04 pixel). Take the first
  // moment out, so that no latitude-dependent sub-pixel shift is built into the rows.
  let m1 = 0, m2 = 0;
  for (let k = 0; k < out.length; k += 2) { m1 += out[k + 1] * (out[k] - c); m2 += out[k + 1] * (out[k] - c) ** 2; }
  const lam = m2 > 0 ? m1 / m2 : 0;
  sum = 0;
  for (let k = 0; k < out.length; k += 2) { out[k + 1] *= 1 - lam * (out[k] - c); sum += out[k + 1]; }
  for (let k = 1; k < out.length; k += 2) out[k] /= sum;
  return out;
}

/**
 * The shipped elevation field {w, h, d: Uint16Array} at a place, in metres; NaN if absent. Bicubic
 * (Catmull-Rom): it passes through the cell values and its slope is continuous, so heights taken from
 * it at a finer spacing do not shade as facets.
 */
export function shippedElevation(f, lon, lat) {
  if (!f) return NaN;
  const fx = ((lon + 180) / 360) * f.w - 0.5, fy = ((90 - lat) / 180) * f.h - 0.5;
  const x1 = Math.floor(fx), y1 = Math.floor(fy), tx = fx - x1, ty = fy - y1;
  const cr = (t) => [((-t + 2) * t - 1) * t / 2, ((3 * t - 5) * t * t + 2) / 2, ((-3 * t + 4) * t + 1) * t / 2, (t - 1) * t * t / 2];
  const wx = cr(tx), wy = cr(ty);
  let v = 0;
  for (let j = 0; j < 4; j++) {
    const y = Math.max(0, Math.min(f.h - 1, y1 - 1 + j)), o = y * f.w;
    let r = 0; for (let i = 0; i < 4; i++) r += wx[i] * f.d[o + ((((x1 - 1 + i) % f.w) + f.w) % f.w)];
    v += wy[j] * r;
  }
  return (v / 65535) * 20000 - 11000;
}

/**
 * Take single bad heights out of a grid, in place. The terrain tiles carry them where a survey met water or a
 * building it could not measure: one texel 1900 m below Manhattan, hundreds along the East River's piers. Seen
 * from 30 m a texel each is a black pit in the relief. A texel further than `thr` metres from the MEDIAN of its
 * eight neighbours is not terrain (on a uniform slope, however steep, the median of the neighbours is the texel
 * itself; a ridge crest or a gully floor at 45 degrees is within 20 m of it at 30 m a texel) and takes that
 * median. Two passes, for pits two texels wide. Returns how many texels were changed.
 */
export function despike(d, w, h, thr) {
  let changed = 0;
  const nb = new Float32Array(8);
  for (let pass = 0; pass < 2; pass++) {
    const src = pass === 0 ? d : Float32Array.from(d);
    for (let y = 1; y < h - 1; y++) {
      for (let x = 1; x < w - 1; x++) {
        const o = y * w + x, v = src[o];
        // cheap way out: within the threshold of any two opposite neighbours' mean, it cannot be a spike worth the sort
        if (Math.abs(v - 0.5 * (src[o - 1] + src[o + 1])) <= thr && Math.abs(v - 0.5 * (src[o - w] + src[o + w])) <= thr) continue;
        nb[0] = src[o - w - 1]; nb[1] = src[o - w]; nb[2] = src[o - w + 1]; nb[3] = src[o - 1]; nb[4] = src[o + 1]; nb[5] = src[o + w - 1]; nb[6] = src[o + w]; nb[7] = src[o + w + 1];
        nb.sort();
        const med = 0.5 * (nb[3] + nb[4]);
        if (Math.abs(v - med) > thr) { d[o] = med; changed++; }
      }
    }
  }
  return changed;
}

const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

/**
 * Mercator tiles -> one equirectangular grid of metres. `win` = {west, north, lonSpan, latSpan} in
 * degrees (west may lie outside -180..180: the window is in unwrapped longitude); the grid is w x h,
 * pixel-centre registered, row 0 north. `getTile(x, y)` returns a Float32Array of 256 x 256 metres.
 *
 * Two parts of the grid are not the tiles':
 *  - polewards of the Mercator square (85.05 degrees) no tile exists: there, and blended in over the
 *    last degree before it, the height is the shipped field's;
 *  - under water. The tiles' sea floor is ETOPO1, and measured against the shipped ETOPO 2022 it lies
 *    about 3 km to the north and differs by 120-190 m rms on 10 km means (land agrees to 10-25 m with no
 *    shift; build/test_app_math.mjs prints both). Two sources that are not in one frame are not
 *    combined: where the atlas's own water mask says water (`water(lon, lat)`, 0..1) and the tiles
 *    are below sea level, the height stays the shipped field's. Lakes above sea level keep the
 *    tiles' flat surface, and land below sea level keeps the tiles' ground.
 * `shipped(lon, lat)` gives the shipped height; either sampler may be null. `own`, if given, is a
 * Float32Array(w * h) that receives the share of each texel that is the tiles' (1 on land, 0 where the
 * height is the shipped field's): the second channel of the texture, so the shader can keep its own
 * shipped height and slope there.
 */
export function compositeElevation(win, z, w, h, getTile, shipped, water, own) {
  const T = TERRAIN.tilePx, n = T * 2 ** z, nt = 2 ** z, src = terrTexelDeg(z);
  const dLon = win.lonSpan / w, dLat = win.latSpan / h;
  const xt = new Array(w), yt = new Array(h), lats = new Float64Array(h);
  let gx0 = Infinity, gx1 = -Infinity, gy0 = Infinity, gy1 = -Infinity;
  for (let i = 0; i < w; i++) {
    const t = tentTaps(((win.west + (i + 0.5) * dLon) / 360 + 0.5) * n, dLon / src);
    xt[i] = t; gx0 = Math.min(gx0, t[0]); gx1 = Math.max(gx1, t[t.length - 2]);
  }
  for (let j = 0; j < h; j++) {
    const lat = win.north - (j + 0.5) * dLat, la = Math.max(-TERRAIN.latMax, Math.min(TERRAIN.latMax, lat));
    lats[j] = lat;
    const t = tentTaps(mercY(la) * n, dLat / (src * Math.cos(la * D2R)));
    for (let k = 0; k < t.length; k += 2) { t[k] = Math.max(0, Math.min(n - 1, t[k])); gy0 = Math.min(gy0, t[k]); gy1 = Math.max(gy1, t[k]); }   // no row beyond the square
    yt[j] = t;
  }
  // the part of the mosaic the taps touch, copied out of the tiles (longitude wraps, latitude does not)
  const mw = gx1 - gx0 + 1, mh = gy1 - gy0 + 1, mos = new Float32Array(mw * mh);
  for (let ty = Math.floor(gy0 / T); ty <= Math.floor(gy1 / T); ty++) {
    for (let tx = Math.floor(gx0 / T); tx <= Math.floor(gx1 / T); tx++) {
      const tile = getTile(((tx % nt) + nt) % nt, ty);
      if (!tile) throw new Error(`elevation tile ${z}/${((tx % nt) + nt) % nt}/${ty} is missing`);
      const xa = Math.max(gx0, tx * T), xb = Math.min(gx1, tx * T + T - 1), ya = Math.max(gy0, ty * T), yb = Math.min(gy1, ty * T + T - 1);
      for (let y = ya; y <= yb; y++) mos.set(tile.subarray((y - ty * T) * T + (xa - tx * T), (y - ty * T) * T + (xb - tx * T) + 1), (y - gy0) * mw + (xa - gx0));
    }
  }
  // rows first (Mercator y -> latitude), then columns
  const tmp = new Float32Array(mw * h), out = new Float32Array(w * h);
  for (let j = 0; j < h; j++) {
    const t = yt[j], o = j * mw;
    for (let k = 0; k < t.length; k += 2) { const wgt = t[k + 1], s = (t[k] - gy0) * mw; for (let x = 0; x < mw; x++) tmp[o + x] += wgt * mos[s + x]; }
  }
  for (let i = 0; i < w; i++) {
    const t = xt[i];
    for (let k = 0; k < t.length; k += 2) { const wgt = t[k + 1], s = t[k] - gx0; for (let j = 0; j < h; j++) out[j * w + i] += wgt * tmp[j * mw + s]; }
  }
  // single bad heights out (see despike): the threshold is 40 m at 30 m a texel and grows with the texel
  despike(out, w, h, Math.max(40, 1.5 * dLat * KM_PER_DEG * 1000));
  // the polar caps and the sea
  if (own) own.fill(1);
  const edge = TERRAIN.latMax - 0.05;
  for (let j = 0; j < h; j++) {
    const lat = lats[j], cap = shipped ? 1 - Math.max(0, Math.min(1, edge - Math.abs(lat))) : 0;       // 0 = the tiles', 1 = the shipped field's
    if (!cap && !(water && shipped)) continue;
    for (let i = 0; i < w; i++) {
      const o = j * w + i, v = out[o], lon = win.west + (i + 0.5) * dLon;
      let t = cap;
      if (t < 1 && water && v < 0) { const wf = water(lon, lat); if (wf > 0.35) t = Math.max(t, smooth(0.35, 0.65, wf) * smooth(0, -30, v)); }
      if (t > 0) { const s = shipped(lon, lat); if (Number.isFinite(s)) { out[o] = v * (1 - t) + s * t; if (own) own[o] = 1 - t; } }
    }
  }
  return out;
}

// ============================================================================ land or water, close in
// The rule itself is water.js (it runs in a worker); what it needs fetched and what is done with its answer are below.
export { WATER_RULE, boxMean, waterFlag };

// ================================================================================ the window planner
export const PLAN = {
  activeKm: 5,          // closer than this many km a pixel, the window is on
  maxTiles: 64,         // imagery requests per window (512 px tiles)
  maxS2Tiles: 120,      // the same for Sentinel-2's 256 px tiles: under half the pixels of 64 Blue Marble tiles
  maxElevZ: 12,         // terrain zoom never asked beyond this (38 m at the equator)
  maxElevTiles: 96,     // elevation requests per window (256 px tiles: a quarter of the pixels each)
  maxTex: 8192,         // texels on a side
  gainKm: 3,            // a streamed texel coarser than this adds nothing to the shipped fields
  minKm: 0.0095,        // no source here is finer than this: Sentinel-2 cloudless is a 10 m mosaic
  bmKm: 0.45,           // a wanted texel finer than this is beyond Blue Marble's last level (0.49 km): Sentinel-2's
  // The window is the view's lon/lat box grown by this share of its size on every side. Negative: the
  // box does not fit the request budget, and the window covers the middle of the view only.
  margins: [0.25, 0.15, 0.05, -0.05, -0.12, -0.19, -0.26, -0.32, -0.38],
  fullView: 0.05,       // the least margin that still counts as covering the view (the shader's fade takes 6% of the window)
  slack: 0.10,          // how far, in view sizes, the view may move before a new window is fetched
};

const LIST_MAX = 400;   // a plan with more tiles than this is only counted, never listed: it is about to be rejected
/** The window for a view box grown by `m` of its size on every side, in unwrapped longitude, clamped at the poles. */
function grow(view, m) {
  const ls = view.full ? 360 : Math.min(360, (view.east - view.west) * (1 + 2 * m));
  const west = view.full || ls >= 360 ? view.lon - 180 : view.west - (view.east - view.west) * m;
  const pad = (view.north - view.south) * m;
  return { west, east: west + ls, north: Math.min(90, view.north + pad), south: Math.max(-90, view.south - pad) };
}
/** Snap a window outwards to a grid of `step` degrees (anchored at -180, 90), never past a pole or all the way round twice. */
function snap(b, step) {
  const west = Math.floor((b.west + 180) / step + 1e-9) * step - 180;
  let east = Math.ceil((b.east + 180) / step - 1e-9) * step - 180;
  if (east - west > 360) east = west + 360;
  const north = Math.min(90, 90 - Math.floor((90 - b.north) / step + 1e-9) * step), south = Math.max(-90, 90 - Math.ceil((90 - b.south) / step - 1e-9) * step);
  return { west, north, lonSpan: east - west, latSpan: north - south };
}
function albPlan(win, L, src = 'bm') {
  const s2 = src === 's2';
  const t = s2 ? s2TexelDeg(L) : gibsTexelDeg(L), P = s2 ? S2.tilePx : GIBS.tilePx, m = s2 ? s2Matrix(L) : gibsMatrix(L);
  const x0 = Math.round((win.west + 180) / t), y0 = Math.round((90 - win.north) / t), w = Math.round(win.lonSpan / t), h = Math.round(win.latSpan / t);
  const r0 = Math.max(0, Math.floor(y0 / P)), r1 = Math.min(m.h - 1, Math.floor((y0 + h - 1) / P));      // rows that exist
  const c0 = Math.floor(x0 / P), c1 = Math.floor((x0 + w - 1) / P), count = (r1 - r0 + 1) * (c1 - c0 + 1);
  const tiles = [];
  if (count <= LIST_MAX) for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) tiles.push({ col: ((c % m.w) + m.w) % m.w, row: r, dx: c * P - x0, dy: r * P - y0 });
  return { L, w, h, tiles, count, texelDeg: t, texelKm: t * KM_PER_DEG, src, tilePx: P };
}
function elevPlan(win, z) {
  const src = terrTexelDeg(z), n = 2 ** z, south = win.north - win.latSpan;
  // rows are as fine as the source is at the window's lowest latitude, so no row of it is skipped
  const lo = win.north * south <= 0 ? 0 : Math.min(Math.abs(win.north), Math.abs(south));
  const w = Math.max(2, Math.round(win.lonSpan / src)), h = Math.max(2, Math.round(win.latSpan / (src * Math.max(0.1, Math.cos(Math.min(lo, TERRAIN.latMax) * D2R)))));
  const cl = (v) => Math.max(-TERRAIN.latMax, Math.min(TERRAIN.latMax, v));
  // one tile of slack on each side for the taps of the edge texels
  const x0 = Math.floor(((win.west / 360 + 0.5) * n * 256 - 2) / 256), x1 = Math.floor((((win.west + win.lonSpan) / 360 + 0.5) * n * 256 + 2) / 256);
  const y0 = Math.max(0, Math.floor((mercY(cl(win.north)) * n * 256 - 2) / 256)), y1 = Math.min(n - 1, Math.floor((mercY(cl(south)) * n * 256 + 2) / 256));
  const nx = Math.min(n, x1 - x0 + 1), count = nx * (y1 - y0 + 1), tiles = [];            // all the way round, each column once
  if (count <= LIST_MAX) for (let y = y0; y <= y1; y++) for (let x = x0; x < x0 + nx; x++) tiles.push({ x: ((x % n) + n) % n, y });
  return { z, w, h, tiles, count, texelDeg: [win.lonSpan / w, win.latSpan / h] };
}

/**
 * Choose the window and the tile levels for a view.
 *   view  {lon, lat: the centre; west, east: unwrapped degrees with west < east; south, north; full: the view goes all the way round}
 *   kmPerPx  the camera's km per CSS pixel at the centre of the view
 * Wanted: a texel no coarser than max(0.45 km, 0.8 x kmPerPx), over the whole view and a margin, within
 * the request budget of each layer. A perspective view of a globe sees far more ground than its
 * centre scale suggests (at 3 km a pixel a 1440 x 900 view spans 60 by 29 degrees), so all three
 * cannot always hold. The order of giving way: the margin; then one level coarser, while that is
 * still finer than gainKm; then coverage, the window shrinking toward the middle of the view. Both
 * layers share one window, so it is the smaller of the two. Returns null when nothing is to be streamed.
 */
export function planDetail(view, kmPerPx, opts = {}) {
  const P = { ...PLAN, ...opts };
  if (!(kmPerPx < P.activeKm)) return null;
  const want = Math.max(P.minKm, 0.8 * kmPerPx);
  const refLat = Math.min(80, Math.abs(view.lat));
  const albKm = (L) => gibsTexelDeg(L) * KM_PER_DEG, elevKm = (z) => terrTexelKm(refLat, z);
  const fits = (p) => !p || (p.count <= (p.z === undefined ? (p.src === 's2' ? P.maxS2Tiles : P.maxTiles) : P.maxElevTiles) && p.w <= P.maxTex && p.h <= P.maxTex);
  let src = 'bm';
  const make = (m, L, z) => {
    const win = snap(grow(view, m), L !== null ? (src === 's2' ? s2TexelDeg(L) : gibsTexelDeg(L)) : 1 / 64);
    return { win, margin: m, alb: L !== null ? albPlan(win, L, src) : null, elev: z !== null ? elevPlan(win, z) : null, night: !!P.night && L !== null };
  };
  // the wanted level of each layer: the coarsest that meets the texel rule
  let L = GIBS.maxLevel; while (L > 5 && albKm(L - 1) <= want) L--;                   // 7 (0.49 km), 6 (0.98 km) or 5 (1.95 km)
  if (want < P.bmKm && !P.noS2) {
    // finer than Blue Marble has: Sentinel-2, at the coarsest level that meets the rule, one level coarser at a time
    // while the whole view does not fit. If even its coarsest useful level does not fit, Blue Marble's last level does.
    const s2Km = (zz) => s2TexelDeg(zz) * KM_PER_DEG;
    let zz = S2.maxLevel; while (zz > S2.minLevel && s2Km(zz - 1) <= want) zz--;
    src = 's2';
    while (zz > S2.minLevel && !fits(make(P.fullView, zz, null).alb)) zz--;
    if (fits(make(P.fullView, zz, null).alb)) L = zz; else src = 'bm';
  }
  let z = P.maxElevZ; while (z > 0 && elevKm(z - 1) <= Math.min(want, P.gainKm)) z--;
  // one level coarser at a time while the whole view does not fit and the coarser level still gains
  while (src === 'bm' && !fits(make(P.fullView, L, null).alb) && albKm(L - 1) <= P.gainKm) L--;
  while (!fits(make(P.fullView, null, z).elev) && z > 0 && elevKm(z - 1) <= P.gainKm) z--;
  for (const m of P.margins) { const p = make(m, L, z); if (fits(p.alb) && fits(p.elev)) return finish(p, want); }
  return null;
}
function finish(p, want) {
  p.wantKm = want;
  p.key = `${p.win.west.toFixed(5)},${p.win.north.toFixed(5)},${p.win.lonSpan.toFixed(5)},${p.win.latSpan.toFixed(5)},${p.alb ? p.alb.src + p.alb.L : '-'},${p.elev ? p.elev.z : '-'},${p.night ? 'n' : '-'}`;
  return p;
}

/**
 * The MODIS mask's tiles for a window whose elevation plan is `elev`: the coarsest level of the "250m" set whose
 * texel is no coarser than the grid's rows (level 8, 244 m, at most), one level coarser at a time while the tiles
 * are more than `max`. The window is snapped outwards to that level's own grid.
 */
export function maskPlan(win, elev, max = PLAN.maxTiles) {
  let L = GIBS.waterMaxLevel; while (L > 0 && gibsTexelDeg(L - 1) <= elev.texelDeg[1]) L--;
  const box = { west: win.west, east: win.west + win.lonSpan, north: win.north, south: win.north - win.latSpan };
  let p = null;
  for (; L >= 0; L--) { const sn = snap(box, gibsTexelDeg(L)); p = albPlan(sn, L); p.win = sn; if (p.count <= max) break; }
  return p;
}
/** The mask's mosaic (RGBA bytes, `mp` from maskPlan; water is opaque) at the centres of a w x h grid over `win`: Uint8Array, 1 = water. */
export function sampleMask(px, mp, win, w, h) {
  const out = new Uint8Array(w * h), t = mp.texelDeg, dLon = win.lonSpan / w, dLat = win.latSpan / h;
  const xs = new Int32Array(w);
  for (let i = 0; i < w; i++) xs[i] = Math.max(0, Math.min(mp.w - 1, Math.floor((win.west + (i + 0.5) * dLon - mp.win.west) / t)));
  for (let j = 0; j < h; j++) {
    const y = Math.max(0, Math.min(mp.h - 1, Math.floor((mp.win.north - (win.north - (j + 0.5) * dLat)) / t))), o = y * mp.w;
    for (let i = 0; i < w; i++) out[j * w + i] = px[(o + xs[i]) * 4 + 3] > 127 ? 1 : 0;
  }
  return out;
}

/** Does the window hold the view box grown by `m` of its size? Longitude wraps; a window cannot pass a pole, so a pole edge always holds. */
export function windowHolds(win, view, m = 0) {
  const b = grow(view, m), south = win.north - win.latSpan;
  let dw = b.west - win.west; dw -= Math.floor(dw / 360 + 1e-12) * 360;                 // the window's longitude is unwrapped; bring the box to it
  const okLon = win.lonSpan >= 360 - 1e-9 || dw + (b.east - b.west) <= win.lonSpan + 1e-9;
  return okLon && (win.north >= 90 || b.north <= win.north + 1e-9) && (south <= -90 || b.south >= south - 1e-9);
}

/** The uniform block for a window (weights excepted). */
export function windowUniforms(p) {
  const w = p.win;
  return {
    uDetWin: [w.west / 360 + 0.5, 0.5 - w.north / 180, w.lonSpan / 360, w.latSpan / 180],
    uDetAlbLod: p.alb ? Math.log2(SHIPPED_ALB_DEG / p.alb.texelDeg) : 0,
    uDetS2: p.alb && p.alb.src === 's2' ? 1 : 0,
    uDetElevPx: p.elev ? [1 / p.elev.w, 1 / p.elev.h] : [1, 1],
    uDetElevM: p.elev ? [p.elev.texelDeg[0] * KM_PER_DEG * 1000, p.elev.texelDeg[1] * KM_PER_DEG * 1000] : [1000, 1000],
  };
}

/** The lon/lat box of what the camera sees: {lon, lat, west, east, south, north, full}. Longitudes are unwrapped about the centre. */
export function viewBox(cam) {
  // project() works from a basis the camera caches for a frame's worth of label work. After a camera change that
  // no label pass has seen yet it is the OLD view's: a pole could "be on screen", the box came back as the whole
  // Earth, no plan fitted, and the planner (which plans once per view) never looked again. Take the basis now.
  if (cam.beginFrame) cam.beginFrame();
  const c = cam.center(), NX = 12, NY = 8;
  let w = 0, e = 0, s = c[1], n = c[1];
  for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) {
    const ll = cam.unproject((i / NX) * cam.w, (j / NY) * cam.h);
    if (!ll) continue;                                                   // off the Earth or off the sheet
    let d = ll[0] - c[0]; d -= Math.round(d / 360) * 360;
    w = Math.min(w, d); e = Math.max(e, d); s = Math.min(s, ll[1]); n = Math.max(n, ll[1]);
  }
  // a pole on screen: every longitude is in view and the box reaches the pole
  let full = e - w > 200;
  for (const pole of [90, -90]) {
    const p = cam.project(0, pole);
    if (p && p[0] >= 0 && p[0] <= cam.w && p[1] >= 0 && p[1] <= cam.h) { full = true; if (pole > 0) n = 90; else s = -90; }
  }
  return { lon: c[0], lat: c[1], west: c[0] + w, east: c[0] + e, south: s, north: n, full };
}

// =================================================================================== the live part
const FADE_MS = 300, RETRIES = 2, PARALLEL = 8;
const CACHE_TILES = Math.ceil(Math.max(PLAN.maxTiles, PLAN.maxS2Tiles, PLAN.maxElevTiles) * 1.5);          // decoded tiles kept per layer: one window and half of the next

/** A small LRU keyed by string: a Map keeps insertion order, so the first key is the oldest. */
class LRU {
  constructor(max, drop) { this.max = max; this.drop = drop; this.m = new Map(); }
  get(k) { const v = this.m.get(k); if (v !== undefined) { this.m.delete(k); this.m.set(k, v); } return v; }
  set(k, v) { this.m.delete(k); this.m.set(k, v); while (this.m.size > this.max) { const [ok, ov] = this.m.entries().next().value; this.m.delete(ok); if (this.drop) this.drop(ov); } }
}

export class Detail {
  /** onChange() asks for a redraw. opts.frozen: no fades and no retries by timer; a deterministic frame waits on `busy`. */
  constructor(gl, fields, onChange, opts = {}) {
    this.gl = gl; this.fields = fields; this.onChange = onChange || (() => {}); this.frozen = !!opts.frozen;
    this.enabled = false;
    this.cur = null;          // the window on screen: {plan, alb: {tex, at}|null, elev: {tex, at}|null}
    this.job = null;          // the window on its way
    this.failedKey = '';      // a window whose tiles failed is not asked for again until the view asks for a different one
    this.error = null;        // why the last window has less than it should, or null
    this.note = ''; this.state = 'off';
    this.stats = null;        // the last finished window: requests, bytes, ms
    this.keep = false;        // development: keep the composited imagery canvas and elevation grid of the current window
    this.albCache = new LRU(CACHE_TILES, (b) => b.close && b.close());
    this.nightCache = new LRU(CACHE_TILES, (b) => b.close && b.close());
    this.elevCache = new LRU(CACHE_TILES);
    this.floatLinear = !!gl.getExtension('OES_texture_float_linear');
    this.maxTex = Math.min(PLAN.maxTex, gl.getParameter(gl.MAX_TEXTURE_SIZE));
    this._lastView = '';
  }

  /** True while a window the view needs is still on its way. */
  get busy() { return !!this.job; }
  /** True while a layer is fading in: the caller keeps redrawing. */
  fading(now) { const c = this.cur; return !!c && [c.alb, c.elev].some((l) => l && now - l.at < FADE_MS); }

  _set(state, note) { this.state = state; this.note = note; this.onChange(); }

  /** Call every frame. Plans a window when the camera has settled on a view the current one does not serve.
   *  `sun`: the sub-solar point {lon, lat} while the night lights are shown, else null. */
  update(cam, settled, on, sun = null) {
    if (!on) { if (this.enabled) { this.enabled = false; this._cancel(); this._drop(); this.failedKey = ''; this.error = null; this._lastView = ''; this._set('off', ''); } return; }
    this.enabled = true;
    const k = cam.kmPerPx();
    const sig = `${cam.view},${cam.w},${cam.h},${k.toFixed(4)},${cam.center().map((v) => v.toFixed(4))},${sun ? Math.round(sun.lon / 2) : 'x'}`;
    if (sig === this._lastView) return;
    if (!(k < PLAN.activeKm)) { this._lastView = sig; this._cancel(); if (this.state !== 'idle') this._set('idle', ''); return; }
    const view = viewBox(cam);
    // a window on its way that the middle of the view has left is stale: stop it now, even mid-gesture
    if (this.job && !windowHolds(this.job.plan.win, { ...view, west: view.lon, east: view.lon, south: view.lat, north: view.lat, full: false })) this._cancel();
    if (!settled) return;                                                 // look again next frame
    this._lastView = sig;
    // the lights are wanted where the Sun is not well up somewhere in the view (they fade out by 6 degrees of Sun)
    const sunAlt = (lon, lat) => Math.asin(Math.sin(lat * D2R) * Math.sin(sun.lat * D2R) + Math.cos(lat * D2R) * Math.cos(sun.lat * D2R) * Math.cos((lon - sun.lon) * D2R)) * R2D;
    const dark = !!sun && [[view.lon, view.lat], [view.west, view.north], [view.east, view.north], [view.west, view.south], [view.east, view.south]].some(([lo, la]) => sunAlt(lo, la) < 8);
    const plan = planDetail(view, k, { maxTex: this.maxTex, night: dark });
    if (!plan) { this._cancel(); if (this.state !== 'idle') this._set('idle', ''); return; }
    // a window serves if it is at least as fine as the one wanted now and holds what that one was to cover, less the slack
    const serves = (p) => p && windowHolds(p.win, view, plan.margin - PLAN.slack) && (!plan.alb || (p.alb && p.alb.texelDeg <= plan.alb.texelDeg * 1.001)) && (!plan.elev || (p.elev && p.elev.z >= plan.elev.z)) && (!plan.night || p.night);
    if (this.cur && serves(this.cur.plan)) { this._cancel(); return; }
    if (this.job && serves(this.job.plan)) return;
    if (plan.key === this.failedKey) return;
    this._cancel();
    this._start(plan, view);
  }

  _cancel() { if (this.job) { this.job.ctl.abort(); this.job = null; if (this.state === 'loading') this._set(this.cur ? 'ready' : 'idle', this.cur ? this.cur.note : ''); } }
  _drop() {
    const gl = this.gl, c = this.cur; if (!c) return;
    for (const [l, unit] of [[c.alb, 'detAlb'], [c.elev, 'detElev']]) if (l) { this.fields.tex[unit] = this.fields.placeholder[unit]; gl.deleteTexture(l.tex); }
    this.cur = null; this.canvas = null; this.cpu = null;
  }

  async _start(plan, view) {
    const ctl = new AbortController(), job = { plan, ctl, t0: performance.now(), requests: 0, bytes: 0, hits: 0 };
    this.job = job;
    this._set('loading', 'Fetching finer tiles…');
    const errs = [];
    const [alb, grid, mask] = await Promise.all([
      plan.alb ? this._imagery(job).catch((e) => { errs.push(`imagery: ${e.message || e}`); return null; }) : null,
      plan.elev ? this._elevation(job).catch((e) => { errs.push(`elevation: ${e.message || e}`); return null; }) : null,
      plan.elev ? this._mask(job).catch((e) => { if (e.name !== 'AbortError') errs.push(`water mask: ${e.message || e}`); return null; }) : null,
    ]);
    // land or water, texel by texel, on the elevation's grid (water.js, in a worker); then the elevation texture, which carries it
    let flag = null;
    if (this.job === job && grid && mask) {
      try { flag = await this._flag(plan, grid, mask, alb ? alb.canvas : null); } catch (e) { errs.push(`water: ${e.message || e}`); }
    }
    if (this.job !== job) {                                                // the view moved on: nothing here is wanted
      if (alb) this.gl.deleteTexture(alb.tex);
      return;
    }
    this.job = null;
    let elev = null;
    if (grid) {
      const t0 = performance.now();
      elev = this._elevTexture(plan.elev, grid, flag ? flag.d : null);
      elev.water = !!flag; elev.flag = flag ? flag.d : null; elev.waterC = flag ? flag.waterC : null;
      job.flagMs = flag ? flag.ms : null;
      job.compositeMs = (job.compositeMs || 0) + Math.round(performance.now() - t0);
    }
    // a layer whose tiles did not all arrive is left out whole (weight 0): the shipped field shows there, and says so
    const now = performance.now(), keepFade = this.cur && windowHolds(this.cur.plan.win, view, -0.45);     // the old window was on screen: no second fade
    const at = (had) => (this.frozen || (keepFade && had) ? -1e9 : now);
    const next = { plan, alb: alb ? { tex: alb.tex, at: at(this.cur && this.cur.alb), night: alb.night } : null, elev: elev ? { tex: elev.tex, at: at(this.cur && this.cur.elev), water: elev.water, waterC: elev.waterC } : null };
    if (alb && plan.night && !alb.night) errs.push(`lights: ${job.nightError || 'not fetched'}`);
    this._drop();
    this.cur = next;
    if (alb) this.fields.tex.detAlb = alb.tex; if (elev) this.fields.tex.detElev = elev.tex;
    if (this.keep) { this.canvas = alb ? alb.canvas : null; this.cpu = elev ? { w: plan.elev.w, h: plan.elev.h, d: elev.data, water: elev.flag, win: plan.win } : null; }
    this.stats = { requests: job.requests, cached: job.hits, bytes: job.bytes, ms: Math.round(now - job.t0), compositeMs: job.compositeMs || 0, flagMs: job.flagMs || null, albTiles: plan.alb ? plan.alb.tiles.length : 0, elevTiles: plan.elev ? plan.elev.tiles.length : 0 };
    this.error = errs.length ? errs.join('; ') : null;
    this.failedKey = errs.length ? plan.key : '';
    const km = (v) => (v < 0.095 ? `${Math.round(v * 1000)} m` : `${v.toFixed(v < 0.95 ? 2 : 1)} km`);
    const nightKm = plan.alb && plan.alb.src === 's2' ? gibsTexelDeg(GIBS.maxLevel) * KM_PER_DEG : plan.alb ? plan.alb.texelKm : 0;
    const parts = [alb ? `imagery ${km(plan.alb.texelKm)}${plan.alb.src === 's2' ? ' (Sentinel-2)' : ''}` : null, alb && alb.night ? `night lights ${km(nightKm)}` : null,
      elev ? `elevation ${km(terrTexelKm(view.lat, plan.elev.z))}` : null].filter(Boolean);
    next.note = errs.length ? `Some tiles could not be fetched (${errs.join('; ')}). ${parts.length ? `Showing ${parts.join(', ')}; the rest is the shipped field.` : 'Showing the shipped fields.'}`
      : `Streamed for this view: ${parts.join(', ')} a texel.`;
    next.credit = alb && plan.alb.src === 's2' ? S2 : null;                 // EOX asks for its attribution on the map
    this._set(errs.length ? (parts.length ? 'partial' : 'failed') : 'ready', next.note);
  }

  /** Fetch with retries; counts requests and bytes on the job. */
  async _fetch(url, job) {
    let last;
    for (let a = 0; a <= RETRIES; a++) {
      if (job.ctl.signal.aborted) throw new DOMException('aborted', 'AbortError');
      try {
        job.requests++;
        const r = await fetch(url, { signal: job.ctl.signal, mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const b = await r.blob(); job.bytes += b.size;
        return b;
      } catch (e) {
        if (e.name === 'AbortError') throw e;
        last = e;
        if (a < RETRIES) await new Promise((res) => setTimeout(res, 300 * (a + 1)));
      }
    }
    throw new Error(`tile ${url.split('/').slice(-3).join('/')}: ${last && last.message}`);
  }
  /** Run `fn` over `items`, PARALLEL at a time; the first failure stops the rest. */
  async _each(items, job, fn) {
    let i = 0, fail = null;
    const worker = async () => { while (i < items.length && !fail && !job.ctl.signal.aborted) { const it = items[i++]; try { await fn(it); } catch (e) { fail = fail || e; } } };
    await Promise.all(Array.from({ length: Math.min(PARALLEL, items.length) }, worker));
    if (job.ctl.signal.aborted) throw new DOMException('aborted', 'AbortError');
    if (fail) throw fail;
  }

  async _imagery(job) {
    const gl = this.gl, p = job.plan.alb, bmp = new Map(), src = p.src === 's2' ? S2 : GIBS;
    await this._each(p.tiles, job, async (t) => {
      const key = `${p.src}/${p.L}/${t.row}/${t.col}`;
      let b = this.albCache.get(key);
      if (b) job.hits++;
      else {
        // no colour management and no premultiplication: the bytes in the file are the data
        b = await createImageBitmap(await this._fetch(src.url(p.L, t.row, t.col), job), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
        if (b.width !== p.tilePx || b.height !== p.tilePx) throw new Error(`tile ${key} is ${b.width} x ${b.height}`);
        this.albCache.set(key, b);                                         // the cache holds more than one window's tiles, so none in use is evicted
      }
      bmp.set(key, b);
    });
    // The lights: Black Marble's tiles. Under Blue Marble they are the same rows and columns of another layer; under
    // Sentinel-2 they are Black Marble's last level over the same window, magnified onto the finer grid below.
    // A failure here costs the lights only: the imagery still shows.
    let nbmp = null;
    const np = p.src === 's2' ? albPlan(snap({ west: job.plan.win.west, east: job.plan.win.west + job.plan.win.lonSpan, north: job.plan.win.north, south: job.plan.win.north - job.plan.win.latSpan }, gibsTexelDeg(GIBS.maxLevel)), GIBS.maxLevel) : p;
    if (job.plan.night) {
      nbmp = new Map();
      await this._each(np.tiles, job, async (t) => {
        const key = `${np.L}/${t.row}/${t.col}`;
        let b = this.nightCache.get(key);
        if (b) job.hits++;
        else {
          b = await createImageBitmap(await this._fetch(GIBS.nightUrl(np.L, t.row, t.col), job), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
          if (b.width !== GIBS.tilePx || b.height !== GIBS.tilePx) throw new Error(`lights tile ${key} is ${b.width} x ${b.height}`);
          this.nightCache.set(key, b);
        }
        nbmp.set(key, b);
      }).catch((e) => { if (e.name === 'AbortError') throw e; job.nightError = e.message || String(e); nbmp = null; });
    }
    // Equirectangular onto equirectangular at the same pixel size: every tile lands on whole pixels.
    const mosaic = (tiles, q, pre = '') => {
      const c = new OffscreenCanvas(q.w, q.h), g = c.getContext('2d', { alpha: false, colorSpace: 'srgb' });
      g.imageSmoothingEnabled = false;
      for (const t of q.tiles) g.drawImage(tiles.get(`${pre}${q.L}/${t.row}/${t.col}`), t.dx, t.dy);
      return c;
    };
    const c = mosaic(bmp, p, `${p.src}/`);
    let nc = nbmp ? mosaic(nbmp, np) : null;
    if (nc && np !== p) {
      // the lights' mosaic covers the window snapped outwards to its own grid: take the window out of it, onto the imagery's grid
      const t7 = gibsTexelDeg(GIBS.maxLevel), W = job.plan.win;
      const sn = snap({ west: W.west, east: W.west + W.lonSpan, north: W.north, south: W.north - W.latSpan }, t7);
      const sx = (W.west - sn.west) / t7, sy = (sn.north - W.north) / t7, sw = W.lonSpan / t7, sh = W.latSpan / t7;
      const out = new OffscreenCanvas(p.w, p.h), g = out.getContext('2d', { alpha: false, colorSpace: 'srgb' });
      g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
      g.drawImage(nc, sx, sy, sw, sh, 0, 0, p.w, p.h);
      nc = out;
    }
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false); gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, nbmp ? gl.RGBA8 : gl.RGB8, nbmp ? gl.RGBA : gl.RGB, gl.UNSIGNED_BYTE, c);
    if (nc) this._writeLights(tex, nc, p.w, p.h);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const ext = gl.getExtension('EXT_texture_filter_anisotropic');
    if (ext) gl.texParameterf(gl.TEXTURE_2D, ext.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    return { tex, canvas: c, night: !!nbmp };                              // the canvas is read once more, for the water flag, then let go
  }

  /**
   * Write the lights into the alpha channel of the imagery texture, on the GPU: the lights mosaic goes up as a
   * texture of its own, one triangle is drawn into the imagery texture with only alpha unmasked, and the
   * mosaic is thrown away. (A 2D canvas cannot hold the four channels: it premultiplies colour by alpha.)
   * Every piece of GL state touched is put back; this runs between frames.
   */
  _writeLights(tex, canvas, w, h) {
    const gl = this.gl;
    if (!this._lightProg) {
      const sh = (type, src) => { const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(`lights shader: ${gl.getShaderInfoLog(o)}`); return o; };
      const pr = gl.createProgram();
      gl.attachShader(pr, sh(gl.VERTEX_SHADER, '#version 300 es\nvoid main() { gl_Position = vec4(float((gl_VertexID << 1) & 2) * 2.0 - 1.0, float(gl_VertexID & 2) * 2.0 - 1.0, 0.0, 1.0); }'));
      // nightLight() above, in the shader's units
      gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, '#version 300 es\nprecision highp float;\nuniform sampler2D uN;\nout vec4 o;\nvoid main() { vec3 c = texelFetch(uN, ivec2(gl_FragCoord.xy), 0).rgb * 255.0; o = vec4(0.0, 0.0, 0.0, clamp(((c.r + c.g) * 0.5 - 0.62 * c.b - 2.0) / 23.75, 0.0, 1.0) * clamp((c.g - 30.0) / 225.0, 0.0, 1.0)); }'));
      gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(`lights program: ${gl.getProgramInfoLog(pr)}`);
      this._lightProg = pr; this._lightU = gl.getUniformLocation(pr, 'uN');
    }
    const was = { fb: gl.getParameter(gl.FRAMEBUFFER_BINDING), vp: gl.getParameter(gl.VIEWPORT), blend: gl.isEnabled(gl.BLEND), scissor: gl.isEnabled(gl.SCISSOR_TEST), depth: gl.isEnabled(gl.DEPTH_TEST), cull: gl.isEnabled(gl.CULL_FACE), prog: gl.getParameter(gl.CURRENT_PROGRAM), vao: gl.getParameter(gl.VERTEX_ARRAY_BINDING), unit: gl.getParameter(gl.ACTIVE_TEXTURE) };
    const ntex = gl.createTexture(), fb = gl.createFramebuffer();
    gl.activeTexture(gl.TEXTURE0 + UNIT.detAlb);
    gl.bindTexture(gl.TEXTURE_2D, ntex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB8, gl.RGB, gl.UNSIGNED_BYTE, canvas);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    try {
      if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('lights: the imagery texture cannot be drawn into');
      gl.viewport(0, 0, w, h);
      gl.disable(gl.BLEND); gl.disable(gl.SCISSOR_TEST); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
      gl.colorMask(false, false, false, true);
      gl.useProgram(this._lightProg); gl.uniform1i(this._lightU, UNIT.detAlb);
      gl.bindVertexArray(null);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    } finally {
      gl.colorMask(true, true, true, true);
      gl.bindFramebuffer(gl.FRAMEBUFFER, was.fb); gl.viewport(was.vp[0], was.vp[1], was.vp[2], was.vp[3]);
      for (const [cap, on] of [[gl.BLEND, was.blend], [gl.SCISSOR_TEST, was.scissor], [gl.DEPTH_TEST, was.depth], [gl.CULL_FACE, was.cull]]) if (on) gl.enable(cap);
      gl.useProgram(was.prog); gl.bindVertexArray(was.vao);
      gl.deleteFramebuffer(fb); gl.deleteTexture(ntex);
      gl.bindTexture(gl.TEXTURE_2D, this.fields.tex.detAlb || null);
      gl.activeTexture(was.unit);
    }
  }

  async _elevation(job) {
    const gl = this.gl, p = job.plan.elev, tiles = new Map();
    await this._each(p.tiles, job, async (t) => {
      const key = `${p.z}/${t.x}/${t.y}`;
      let d = this.elevCache.get(key);
      if (d) job.hits++;
      else {
        const b = await createImageBitmap(await this._fetch(TERRAIN.url(p.z, t.x, t.y), job), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
        if (b.width !== 256 || b.height !== 256) { b.close(); throw new Error(`tile ${key} is ${b.width} x ${b.height}`); }
        this._dec ||= new OffscreenCanvas(256, 256).getContext('2d', { willReadFrequently: true, colorSpace: 'srgb' });
        this._dec.drawImage(b, 0, 0); b.close();
        const px = this._dec.getImageData(0, 0, 256, 256).data;
        d = new Float32Array(65536);
        for (let i = 0; i < 65536; i++) d[i] = terrDecode(px[i * 4], px[i * 4 + 1], px[i * 4 + 2]);
        this.elevCache.set(key, d);
      }
      tiles.set(`${t.x}/${t.y}`, d);
    });
    const ship = this.fields.cpu.elev, water = await this._water(job.plan.win, job).catch((e) => { console.error('detail: the water mask could not be read; the tiles\u2019 sea floor is used', e); return null; });
    if (job.ctl.signal.aborted) throw new DOMException('aborted', 'AbortError');
    const t0 = performance.now();
    const own = new Float32Array(p.w * p.h);
    const data = compositeElevation(job.plan.win, p.z, p.w, p.h, (x, y) => tiles.get(`${x}/${y}`), ship ? (lon, lat) => shippedElevation(ship, lon, lat) : null, ship ? water : null, own);
    job.compositeMs = Math.round(performance.now() - t0);
    return { data, own, shipWater: water };
  }

  /** The elevation texture. R: metres. G: the share of the texel that is the tiles' (0 under the sea and beyond 85
   *  degrees, where R holds the shipped field). B: 1 where the texel is water (waterFlag), when `flag` is given. */
  _elevTexture(p, grid, flag) {
    const gl = this.gl, n = p.w * p.h, rgb = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { rgb[i * 3] = grid.data[i]; rgb[i * 3 + 1] = grid.own[i]; rgb[i * 3 + 2] = flag ? flag[i] : 0; }
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    // metres as floats. Without linear filtering of 32-bit floats, half floats: 8 m steps above 8192 m, finer below.
    gl.texImage2D(gl.TEXTURE_2D, 0, this.floatLinear ? gl.RGB32F : gl.RGB16F, p.w, p.h, 0, gl.RGB, gl.FLOAT, rgb);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return { tex, data: this.keep ? grid.data : null };
  }

  /** NASA's MODIS water mask over the window, on the elevation's grid: {d: Uint8Array (1 = water), cell: the mask's cell in texels}. */
  async _mask(job) {
    const W = job.plan.win, e = job.plan.elev, mp = maskPlan(W, e);
    const bmp = new Map();
    await this._each(mp.tiles, job, async (t) => {
      const key = `w/${mp.L}/${t.row}/${t.col}`;
      let b = this.nightCache.get(key);
      if (b) job.hits++;
      else {
        b = await createImageBitmap(await this._fetch(GIBS.waterUrl(mp.L, t.row, t.col), job), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
        if (b.width !== GIBS.tilePx || b.height !== GIBS.tilePx) throw new Error(`water mask tile ${key} is ${b.width} x ${b.height}`);
        this.nightCache.set(key, b);
      }
      bmp.set(key, b);
    });
    const c = new OffscreenCanvas(mp.w, mp.h), g = c.getContext('2d', { willReadFrequently: true, colorSpace: 'srgb' });
    g.imageSmoothingEnabled = false;
    for (const t of mp.tiles) g.drawImage(bmp.get(`w/${mp.L}/${t.row}/${t.col}`), t.dx, t.dy);
    const px = g.getImageData(0, 0, mp.w, mp.h).data;                     // water is opaque, land transparent
    return { d: sampleMask(px, mp, W, e.w, e.h), cell: Math.max(1, mp.texelDeg / e.texelDeg[1]) };
  }

  /** Run the rule in the worker; on this thread if there is no worker to be had. Resolves {d, waterC}. */
  _rule(g) {
    if (this._worker === undefined) {
      try {
        const u = new URL('./water.worker.js', import.meta.url); u.search = new URL(import.meta.url).search;   // the build's code stamp, if any
        this._worker = new Worker(u, { type: 'module' });
        this._calls = new Map(); this._callId = 0;
        this._worker.onmessage = (ev) => { const c = this._calls.get(ev.data.id); if (!c) return; this._calls.delete(ev.data.id); if (ev.data.error) c.reject(new Error(ev.data.error)); else c.resolve(ev.data); };
        this._worker.onerror = () => { const cs = [...this._calls.values()]; this._calls.clear(); this._worker = null; for (const c of cs) c.reject(new Error('the water worker failed')); };
      } catch (e) { this._worker = null; }
    }
    if (!this._worker) return Promise.resolve(runRule(g));
    return new Promise((resolve, reject) => {
      const id = ++this._callId;
      this._calls.set(id, { resolve, reject });
      this._worker.postMessage({ id, g });                                 // copied, not transferred: the elevation grid is still wanted here
    }).catch(() => runRule(g));
  }

  /** The water flag for a window: the picture drawn down onto the elevation's grid, the shipped water fraction on it, and the rule. */
  async _flag(plan, grid, mask, canvas) {
    const e = plan.elev, W = plan.win, tm = [performance.now()];
    let rgba = null;
    if (canvas) {
      const c = new OffscreenCanvas(e.w, e.h), g = c.getContext('2d', { alpha: false, willReadFrequently: true, colorSpace: 'srgb' });
      g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
      g.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, e.w, e.h);
      rgba = g.getImageData(0, 0, e.w, e.h).data;
    }
    tm.push(performance.now());
    let ship = null;
    if (grid.shipWater) {
      ship = new Float32Array(e.w * e.h);
      const dLon = W.lonSpan / e.w, dLat = W.latSpan / e.h;
      // the shipped field is 5 km: sampled every few texels and repeated, it is the same field
      const st = Math.max(1, Math.floor(1.2 / (e.texelDeg[1] * KM_PER_DEG)));
      for (let j = 0; j < e.h; j += st) for (let i = 0; i < e.w; i += st) {
        const v = grid.shipWater(W.west + (Math.min(e.w - 1, i + (st >> 1)) + 0.5) * dLon, W.north - (Math.min(e.h - 1, j + (st >> 1)) + 0.5) * dLat);
        for (let jj = j; jj < Math.min(e.h, j + st); jj++) ship.fill(v, jj * e.w + i, jj * e.w + Math.min(e.w, i + st));
      }
    }
    tm.push(performance.now());
    const midLat = W.north - W.latSpan / 2;
    const r = await this._rule({ w: e.w, h: e.h, rgba, elev: grid.data, mask: mask.d, ship, cell: mask.cell,
      mx: e.texelDeg[0] * KM_PER_DEG * 1000 * Math.max(0.05, Math.cos(midLat * D2R)), my: e.texelDeg[1] * KM_PER_DEG * 1000 });
    tm.push(performance.now());
    return { d: r.d, waterC: r.waterC, ms: { draw: Math.round(tm[1] - tm[0]), ship: Math.round(tm[2] - tm[1]), rule: Math.round(tm[3] - tm[2]), worker: !!this._worker } };
  }

  /**
   * The atlas's own water mask over a window, at its full resolution (the CPU copy in Fields is a quarter of it):
   * returns water(lon, lat) -> 0..1, bilinear. The file is the one Fields has already fetched, so this is a cache read.
   */
  async _water(win, job) {
    this._waterBlob ||= fetch(stamped('fields/water.webp')).then((r) => { if (!r.ok) throw new Error(`water mask: HTTP ${r.status}`); return r.blob(); });
    const blob = await this._waterBlob.catch((e) => { this._waterBlob = null; throw e; });
    const W = 8192, H = 4096, cell = 360 / W;
    const x0 = Math.floor((win.west + 180) / cell) - 2, x1 = Math.ceil((win.west + win.lonSpan + 180) / cell) + 2;
    const y0 = Math.max(0, Math.floor((90 - win.north) / cell) - 2), y1 = Math.min(H, Math.ceil((90 - win.north + win.latSpan) / cell) + 2);
    const cw = Math.min(W, x1 - x0), ch = y1 - y0, c = new OffscreenCanvas(cw, ch), g = c.getContext('2d', { willReadFrequently: true, colorSpace: 'srgb' });
    // the crop may run off either end of the image: longitude wraps, so it is drawn in up to two pieces
    for (let x = x0; x < x0 + cw;) {
      const sx = ((x % W) + W) % W, n = Math.min(W - sx, x0 + cw - x);
      const b = await createImageBitmap(blob, sx, y0, n, ch, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
      if (b.width !== n) { b.close(); throw new Error(`water mask is not ${W} px wide`); }
      g.drawImage(b, x - x0, 0); b.close(); x += n;
    }
    const px = g.getImageData(0, 0, cw, ch).data, d = new Uint8Array(cw * ch);
    for (let i = 0; i < d.length; i++) d[i] = px[i * 4];
    return (lon, lat) => {
      let fx = (lon + 180) / cell - 0.5 - x0; const fy = Math.max(0, Math.min(ch - 1, (90 - lat) / cell - 0.5 - y0));
      fx -= Math.floor(fx / W) * W; fx = Math.max(0, Math.min(cw - 1, fx));
      const xa = Math.floor(fx), ya = Math.floor(fy), xb = Math.min(cw - 1, xa + 1), yb = Math.min(ch - 1, ya + 1), ax = fx - xa, ay = fy - ya;
      return ((d[ya * cw + xa] * (1 - ax) + d[ya * cw + xb] * ax) * (1 - ay) + (d[yb * cw + xa] * (1 - ax) + d[yb * cw + xb] * ax) * ay) / 255;
    };
  }

  /** The shader's uniforms for this instant. With the layer off, or nothing loaded, both weights are 0. */
  uniforms(now) {
    const u = { uDetAlb: UNIT.detAlb, uDetElev: UNIT.detElev, uDetWin: [0, 0, 1, 1], uDetAlbW: 0, uDetElevW: 0, uDetNightW: 0, uDetWaterW: 0, uDetWaterC: [0.10, 0.15, 0.20], uDetS2: 0, uDetAlbLod: 0, uDetElevPx: [1, 1], uDetElevM: [1000, 1000] };
    const c = this.cur;
    if (!this.enabled || !c) return u;
    const wgt = (l) => { if (!l) return 0; const x = Math.max(0, Math.min(1, (now - l.at) / FADE_MS)); return x * x * (3 - 2 * x); };
    return { ...u, ...windowUniforms(c.plan), uDetAlbW: wgt(c.alb), uDetElevW: wgt(c.elev), uDetNightW: c.alb && c.alb.night ? wgt(c.alb) : 0, uDetWaterW: c.elev && c.elev.water ? wgt(c.elev) : 0, uDetWaterC: (c.elev && c.elev.waterC) || u.uDetWaterC };
  }
}
