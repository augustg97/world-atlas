import { viewBox } from './detail.js';
import { BUILDING_STRIDE, OFM, streetTileRange, tileXY } from './streets.js';
import { program, setUniforms } from './gl.js';

export const CITY_EXAMPLES = [
  { name: 'Los Angeles', lon: -118.2554, lat: 34.0501 },
  { name: 'San Francisco', lon: -122.4011, lat: 37.7897 },
  { name: 'London', lon: -0.0858, lat: 51.5132 },
];
export const CITY_START_KM = 0.007;
export const CITY_CREDIT = { pre: 'Buildings: ', credit: OFM.credit, link: OFM.link, post: ' via OpenFreeMap' };
const MAX_TILES = 48;
const MESH_MAX_KM = 0.032;

export function cityTilePlan(camera) {
  const v = viewBox(camera);
  if (v.full) return null;
  const lonSpan = v.east - v.west, latSpan = v.north - v.south;
  const z = OFM.maxZoom, n = 2 ** z;
  // The z13 source merges many footprints and loses their individual heights. Keep the original features from z14.
  const bounds = streetTileRange({
    west: v.west - lonSpan * 0.08, north: v.north + latSpan * 0.08,
    lonSpan: lonSpan * 1.16, latSpan: latSpan * 1.16,
  }, z);
  if (!bounds) return null;
  const { c0, c1, r0, r1 } = bounds;
  const count = (c1 - c0 + 1) * (r1 - r0 + 1), focus = tileXY(v.lon, v.lat, z);
  const tiles = [], radius = Math.ceil(Math.sqrt(MAX_TILES));
  const lo = count <= MAX_TILES ? c0 : Math.max(c0, Math.floor(focus[0]) - radius);
  const hi = count <= MAX_TILES ? c1 : Math.min(c1, Math.floor(focus[0]) + radius);
  const top = count <= MAX_TILES ? r0 : Math.max(r0, Math.floor(focus[1]) - radius);
  const bottom = count <= MAX_TILES ? r1 : Math.min(r1, Math.floor(focus[1]) + radius);
  for (let y = top; y <= bottom; y++) for (let x = lo; x <= hi; x++) tiles.push({ x: ((x % n) + n) % n, y, ox: x });
  if (tiles.length > MAX_TILES) {
    const distance = (t) => (t.ox + 0.5 - focus[0]) ** 2 + (t.y + 0.5 - focus[1]) ** 2;
    tiles.sort((a, b) => distance(a) - distance(b) || a.y - b.y || a.ox - b.ox);
    tiles.length = MAX_TILES;
  }
  tiles.sort((a, b) => a.y - b.y || a.ox - b.ox);
  return { z, tiles, count: tiles.length, limited: count > tiles.length, focus };
}

// One bounded mesh per view. A pan within the current set of tiles needs no new request or GPU upload.
export class Buildings {
  constructor(gl, streets, onChange) {
    this.gl = gl; this.streets = streets; this.onChange = onChange;
    this.key = ''; this.signature = ''; this.status = 'idle'; this.info = null; this.vertices = 0;
  }

  clear(status = 'idle') {
    const changed = this.status !== status || this.vertices;
    this.ctl?.abort();
    this.ctl = null; this.key = ''; this.signature = '';
    this.info = null; this.vertices = 0; this.status = status;
    if (changed) this.onChange();
  }

  update(cam, settled, active) {
    if (!active) { if (this.status !== 'idle') this.clear(); return; }
    if (!settled) return;
    if (cam.view !== 'globe' || cam.kmPerPx() >= MESH_MAX_KM) { if (this.status !== 'zoom') this.clear('zoom'); return; }
    const signature = [cam.lon, cam.lat, cam.kmPerPx(), cam.pitch, cam.bearing, cam.w, cam.h].join();
    if (signature === this.signature) return;
    const plan = cityTilePlan(cam);
    if (!plan) { if (this.status !== 'zoom') this.clear('zoom'); this.signature = signature; return; }
    this.signature = signature;
    const key = plan.z + ':' + plan.tiles.map(({ x, y }) => x + '/' + y).join(',');
    if (this.key === key) { if (this.info) this.info.limited = plan.limited; return; }
    this.key = key;
    this.ctl?.abort();
    const ctl = new AbortController();
    this.ctl = ctl;
    this.status = 'loading';
    this.load(plan, ctl);
  }

  async load(plan, ctl) {
    try {
      this.progRequest ||= program(this.gl, 'buildings').catch((error) => { this.progRequest = null; throw error; });
      const [prog, mesh] = await Promise.all([
        this.progRequest,
        this.streets.request({ meshOnly: true, z: plan.z, tiles: plan.tiles, focus: plan.focus }, ctl.signal),
      ]);
      if (this.ctl !== ctl) return;
      this.install(prog, mesh.data);
      this.info = { count: mesh.count, fallback: mesh.fallback, tallest: mesh.tallest, truncated: mesh.truncated, failed: mesh.failed, limited: plan.limited };
      this.status = mesh.count ? 'ready' : mesh.failed ? 'failed' : 'empty';
    } catch (error) {
      if (this.ctl !== ctl || error.name === 'AbortError') return;
      ctl.abort();
      this.vertices = 0;
      this.info = null;
      this.status = 'failed';
    }
    if (this.ctl === ctl) { this.ctl = null; this.onChange(); }
  }

  install(prog, data) {
    const gl = this.gl;
    if (!this.vao) {
      this.prog = prog;
      this.vao = gl.createVertexArray(); this.buffer = gl.createBuffer();
      gl.bindVertexArray(this.vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
      for (const [index, size, offset] of [[0, 3, 0], [1, 3, 3], [2, 1, 6]]) {
        gl.enableVertexAttribArray(index);
        gl.vertexAttribPointer(index, size, gl.FLOAT, false, BUILDING_STRIDE * 4, offset * 4);
      }
      gl.bindVertexArray(null);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.vertices = data.length / BUILDING_STRIDE;
  }

  draw(cam, sun, atlas) {
    if (!this.vertices || !this.prog || cam.view !== 'globe' || cam.kmPerPx() >= MESH_MAX_KM) return;
    const gl = this.gl, depth = cam.dist - 1;
    gl.enable(gl.DEPTH_TEST);
    gl.clear(gl.DEPTH_BUFFER_BIT);
    gl.useProgram(this.prog.p);
    setUniforms(gl, this.prog, {
      ...cam.uniforms(), uNear: depth * 0.06, uFar: depth * 5, uSun: sun.vec, uAtlas: atlas ? 1 : 0,
    });
    gl.bindVertexArray(this.vao);
    gl.drawArrays(gl.TRIANGLES, 0, this.vertices);
    gl.bindVertexArray(null);
    gl.disable(gl.DEPTH_TEST);
  }
}
