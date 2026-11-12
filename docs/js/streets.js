// Streets and buildings, close in (register F15). OpenStreetMap's roads, buildings and land use, as vector tiles in
// the OpenMapTiles schema from OpenFreeMap (tiles.openfreemap.org: no key, no limit; the owner approved the host on
// 2026-11-11). Data (c) OpenStreetMap contributors, ODbL: credited on the map while its tiles are on it.
//
// This file is the part with no browser in it: which tiles a window needs, the tile format (Mapbox Vector Tile:
// protocol buffers), and how wide and how bright each class of road is drawn. streets.worker.js fetches, decodes and
// draws; detail.js puts the result into the window's picture.
//
// TWO THINGS ARE DRAWN from one set of tiles, both on the imagery window's own grid:
//   the DAY OVERLAY (colour, laid over Sentinel-2): paved roads at their width on the ground, each building's shadow
//     and roof. Sentinel-2 is 10 m; closer than that the photograph is a blur and these are what keep a city a city.
//   the PATTERN (one channel, the imagery texture's alpha): where a city's light comes from. Roads by class, building
//     footprints, commercial ground. At night the shader spreads Black Marble's measured amount over this pattern;
//     in the Atlas style it is read as the street plan. MODELLED: OpenStreetMap says where a road is, not whether it is lit.

const D2R = Math.PI / 180, R2D = 180 / Math.PI;

export const OFM = {
  tilejson: 'https://tiles.openfreemap.org/planet',
  minZoom: 8, maxZoom: 14, extent: 4096,
  credit: '© OpenStreetMap contributors', link: 'https://www.openstreetmap.org/copyright', via: 'OpenFreeMap',
};

export const STREETS = {
  activeKm: 0.12,       // closer than this many km a CSS pixel the window asks for streets
  maxTiles: 36,         // vector tiles per window; the zoom is the finest that fits (a 1440 x 900 view at 5 m a pixel is 30 tiles of zoom 14 at Paris)
  buildingsM: 12,       // buildings are drawn where a window texel is finer than this many metres (a house is 10 m)
  shadowsM: 6.5,        // and their shadows where it is finer than this
  shadow: 0.62,         // a shadow's length over the building's height: the Sun 58 degrees up, as Sentinel-2's mid-morning summer pass has it
  defaultH: 7,          // metres, where OpenStreetMap gives a building no height (two storeys)
};

// Each road class: `w` the paved width in metres; `light` its value in the pattern (0..1); `day` the opacity of its
// pavement over the photograph. Pattern values of roads are all 0.5 and over and those of filled ground all under
// 0.3: the Atlas style tells a road from a block by that alone, and the night reads both as amounts of light.
export const ROADS = {
  motorway: { w: 26, light: 0.66, day: 0.50 },    // lit at junctions and by headlights, not along its length
  trunk: { w: 20, light: 0.92, day: 0.50 },
  primary: { w: 17, light: 1.00, day: 0.50 },
  secondary: { w: 14, light: 0.88, day: 0.46 },
  tertiary: { w: 11, light: 0.76, day: 0.42 },
  minor: { w: 8, light: 0.62, day: 0.36 },
  service: { w: 4.5, light: 0.52, day: 0.26 },
  busway: { w: 7, light: 0.62, day: 0.36 },
};
export const ROAD_ORDER = ['service', 'busway', 'minor', 'tertiary', 'secondary', 'motorway', 'trunk', 'primary'];   // drawn in this order: the brighter over the dimmer
export const RAIL = { w: 3.5, day: 0.42 };         // rail and transit: a dark line by day, no light
export const FILLS = { building: 0.14, commercial: 0.26, retail: 0.26, industrial: 0.10 };   // pattern values of filled ground
export const LAMP_M = 3;                           // a lamp lights this much ground beyond the kerb, each side

/** Web Mercator tile coordinates (fractional) of a longitude and latitude at zoom z. */
export const tileXY = (lon, lat, z) => { const n = 2 ** z; return [(lon / 360 + 0.5) * n, (0.5 - Math.log(Math.tan(Math.PI / 4 + (lat * D2R) / 2)) / (2 * Math.PI)) * n]; };
export const tileLon = (x, z) => (x / 2 ** z - 0.5) * 360;
export const tileLat = (y, z) => (2 * Math.atan(Math.exp((0.5 - y / 2 ** z) * 2 * Math.PI)) - Math.PI / 2) * R2D;

/**
 * The vector tiles for a window {west, north, lonSpan, latSpan}: the finest zoom (OFM.maxZoom at most) at which the
 * window takes no more than `max` tiles. Null beyond Web Mercator's 85 degrees or when even the coarsest zoom is too many.
 */
export function streetPlan(win, max = STREETS.maxTiles) {
  const south = win.north - win.latSpan;
  if (win.north > 84 || south < -84) return null;
  for (let z = OFM.maxZoom; z >= OFM.minZoom; z--) {
    const n = 2 ** z;
    const [x0, y0] = tileXY(win.west, win.north, z), [x1, y1] = tileXY(win.west + win.lonSpan, south, z);
    const c0 = Math.floor(x0), c1 = Math.floor(x1 - 1e-9), r0 = Math.max(0, Math.floor(y0)), r1 = Math.min(n - 1, Math.floor(y1 - 1e-9));
    const count = (c1 - c0 + 1) * (r1 - r0 + 1);
    if (count > max) continue;
    const tiles = [];
    for (let y = r0; y <= r1; y++) for (let x = c0; x <= c1; x++) tiles.push({ x: ((x % n) + n) % n, y, ox: x });   // ox: the unwrapped column, for placing
    return { z, tiles, count };
  }
  return null;
}

// ------------------------------------------------------------------------------------- the tile format
// A Mapbox Vector Tile is a protocol-buffer message: Tile { repeated Layer layers = 3 }; Layer { name = 1, features
// = 2, keys = 3, values = 4, extent = 5 }; Feature { tags = 2 (packed), type = 3, geometry = 4 (packed) }; Value {
// string = 1, float = 2, double = 3, int = 4, uint = 5, sint = 6, bool = 7 }. Geometry is a run of commands (MoveTo
// 1, LineTo 2, ClosePath 7; count in the upper bits) with zigzag-coded steps from the last point.
// https://github.com/mapbox/vector-tile-spec/tree/master/2.1

function reader(buf) {
  let i = 0;
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const varint = () => { let r = 0, s = 1, c; do { if (i >= buf.length) throw new Error('vector tile: cut short'); c = buf[i++]; r += (c & 127) * s; s *= 128; } while (c > 127); return r; };
  return {
    more: () => i < buf.length,
    varint,
    /** The next field: [number, wire type, value]. Length-delimited values come back as a view of the bytes. */
    field() {
      const k = varint(), f = Math.floor(k / 8), w = k % 8;
      if (w === 0) return [f, w, varint()];
      if (w === 2) { const n = varint(); if (i + n > buf.length) throw new Error('vector tile: cut short'); const v = buf.subarray(i, i + n); i += n; return [f, w, v]; }
      if (w === 5) { const v = dv.getFloat32(i, true); i += 4; return [f, w, v]; }
      if (w === 1) { const v = dv.getFloat64(i, true); i += 8; return [f, w, v]; }
      throw new Error(`vector tile: wire type ${w}`);
    },
  };
}
const utf8 = typeof TextDecoder !== 'undefined' ? new TextDecoder() : null;
function value(buf) {
  const r = reader(buf);
  while (r.more()) {
    const [f, w, v] = r.field();
    if (f === 1) return utf8.decode(v);
    if (f === 2 || f === 3 || f === 4 || f === 5) return v;
    if (f === 6) return v % 2 ? -(v + 1) / 2 : v / 2;
    if (f === 7) return !!v;
    void w;
  }
  return null;
}
/** A feature's geometry as a list of parts, each a Float32Array of x, y pairs in tile units (0..extent). */
function geometry(buf) {
  const r = reader(buf), parts = [];
  let x = 0, y = 0, cur = null;
  const zz = (v) => (v % 2 ? -(v + 1) / 2 : v / 2);
  while (r.more()) {
    const c = r.varint(), id = c & 7, n = Math.floor(c / 8);
    if (id === 1) for (let k = 0; k < n; k++) { x += zz(r.varint()); y += zz(r.varint()); cur = [x, y]; parts.push(cur); }
    else if (id === 2) for (let k = 0; k < n; k++) { x += zz(r.varint()); y += zz(r.varint()); cur.push(x, y); }
    else if (id === 7) { if (cur) cur.push(cur[0], cur[1]); }
    else throw new Error(`vector tile: geometry command ${id}`);
  }
  return parts.map((p) => Float32Array.from(p));
}

/**
 * Decode the layers of a tile that the atlas draws. Returns
 *   {extent, roads: {class: [Float32Array line, ...]}, rail: [line, ...], buildings: [{h, rings: [ring, ...]}], fills: {class: [ring, ...]}}
 * Lines and rings are x, y pairs in tile units. Tunnels are left out; so is everything the tile holds for other
 * maps' sake (names, addresses, points of interest), which is most of its bytes and is skipped unread.
 */
export function decodeTile(bytes) {
  const out = { extent: OFM.extent, roads: {}, rail: [], buildings: [], fills: {} };
  const tile = reader(bytes);
  while (tile.more()) {
    const [f, , layerBytes] = tile.field();
    if (f !== 3) continue;
    // the name is the first field of every layer OpenMapTiles writes; read just enough to know whether to go on
    let name = null; const keys = [], vals = [], feats = []; let extent = 4096;
    const L = reader(layerBytes);
    let skip = false;
    while (L.more()) {
      const [lf, , v] = L.field();
      if (lf === 1) { name = utf8.decode(v); if (name !== 'transportation' && name !== 'building' && name !== 'landuse') { skip = true; break; } }
      else if (lf === 2) feats.push(v);
      else if (lf === 3) keys.push(utf8.decode(v));
      else if (lf === 4) vals.push(v);
      else if (lf === 5) extent = v;
    }
    if (skip || !name) continue;
    out.extent = extent;
    const decoded = new Map();
    const val = (k) => { if (!decoded.has(k)) decoded.set(k, value(vals[k])); return decoded.get(k); };
    for (const fb of feats) {
      const F = reader(fb); let type = 0, geom = null; const tags = [];
      while (F.more()) {
        const [ff, , v] = F.field();
        if (ff === 3) type = v;
        else if (ff === 4) geom = v;
        else if (ff === 2) { const t = reader(v); while (t.more()) tags.push(t.varint()); }
      }
      if (!geom) continue;
      const props = {};
      for (let k = 0; k + 1 < tags.length; k += 2) { const key = keys[tags[k]]; if (key === 'class' || key === 'brunnel' || key === 'render_height' || key === 'render_min_height' || key === 'hide_3d') props[key] = val(tags[k + 1]); }
      if (name === 'transportation') {
        if (type !== 2 || props.brunnel === 'tunnel') continue;
        const cls = props.class;
        if (cls === 'rail' || cls === 'transit') out.rail.push(...geometry(geom));
        else if (ROADS[cls]) (out.roads[cls] ||= []).push(...geometry(geom));
      } else if (name === 'building') {
        if (type !== 3) continue;
        const h = Number(props.render_height);
        out.buildings.push({ h: Number.isFinite(h) && h > 0 ? h : STREETS.defaultH, rings: geometry(geom) });
      } else if (type === 3 && FILLS[props.class] !== undefined) (out.fills[props.class] ||= []).push(...geometry(geom));
    }
  }
  return out;
}

/**
 * Where a window's canvas puts a tile's points. The canvas is plate carree (the imagery's own frame): x runs with
 * longitude and y with latitude, `w` by `h` pixels over the window. Drawing is done in METRES east and south of the
 * window's north-west corner, so that a road's width is its width on the ground whichever way it runs (a degree of
 * longitude is shorter than one of latitude, and the canvas is stretched east-west by 1 / cos latitude).
 *   returns {sx, sy: canvas pixels per metre; mx(lon), my(lat): metres; point(tx, ty, tile, z, extent): [mx, my]}
 */
export function frame(win, w, h) {
  const lat0 = win.north - win.latSpan / 2, kx = 111195 * Math.cos(lat0 * D2R), ky = 111195;
  const f = {
    lat0, sx: w / (win.lonSpan * kx), sy: h / (win.latSpan * ky),
    mx: (lon) => (lon - win.west) * kx, my: (lat) => (win.north - lat) * ky,
  };
  return f;
}

/** A building's shadow on the ground, as the offset in metres (east, south) of its roof's outline: Sentinel-2 passes
 *  in mid-morning with the Sun to the south-east (north of the tropics) or the north-east (south of them). */
export function shadowOffset(h, lat) {
  const d = h * STREETS.shadow * Math.SQRT1_2;
  return [-d, lat >= 0 ? -d : d];
}
