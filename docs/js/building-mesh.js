// Build roofs and walls off the main thread from the same OpenStreetMap tiles as the street plan.
// Earcut handles courtyards and concave roofs. Faces are clipped to the tile that owns the ground.
import earcut from './vendor/earcut.js?v=20261124T234441Z';
import { lonLatToVec } from './astro.js?v=20261124T234441Z';
import { R_KM } from './camera.js?v=20261124T234441Z';
import { BUILDING_STRIDE, tileLat, tileLon } from './streets.js?v=20261124T234441Z';

const R_M = R_KM * 1000;
const MAX_TRIANGLES = 190000;
const length = (a) => Math.hypot(...a);

function signedArea(ring) {
  let area = 0;
  for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) area += ring[j] * ring[i + 1] - ring[i] * ring[j + 1];
  return area;
}

function polygons(rings) {
  const out = [];
  let exteriorSign = 0;
  for (const r of rings) {
    const closed = r[0] === r[r.length - 2] && r[1] === r[r.length - 1];
    const ring = closed ? r.subarray(0, r.length - 2) : r;
    if (ring.length < 6) continue;
    const sign = Math.sign(signedArea(ring));
    if (!sign) continue;
    exteriorSign ||= sign;
    if (sign === exteriorSign) out.push({ rings: [ring], sign });
    else out[out.length - 1].rings.push(ring);
  }
  return out;
}

const TILE_EDGES = [[0, 1], [0, -1], [1, 1], [1, -1]];
const inside = (p, extent) => p[0] >= 0 && p[0] <= extent && p[1] >= 0 && p[1] <= extent;
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

function clipRoof(points, extent) {
  if (points.every((p) => inside(p, extent))) return points;
  for (const [axis, sign] of TILE_EDGES) {
    const edge = sign > 0 ? 0 : extent;
    const next = [];
    for (let i = 0; i < points.length; i++) {
      const a = points[i], b = points[(i + 1) % points.length];
      const da = (a[axis] - edge) * sign, db = (b[axis] - edge) * sign;
      if (da >= 0) next.push(a);
      if ((da > 0 && db < 0) || (da < 0 && db > 0)) next.push(mix(a, b, da / (da - db)));
    }
    points = next;
    if (points.length < 3) return [];
  }
  return points;
}

function clipWall(a, b, extent) {
  if (inside(a, extent) && inside(b, extent)) return [a, b];
  let t0 = 0, t1 = 1;
  for (const [axis, sign] of TILE_EDGES) {
    const edge = sign > 0 ? 0 : extent;
    const da = (a[axis] - edge) * sign, db = (b[axis] - edge) * sign;
    if (da < 0 && db < 0) return null;
    if (da < 0) t0 = Math.max(t0, da / (da - db));
    if (db < 0) t1 = Math.min(t1, da / (da - db));
    if (t1 <= t0) return null;
  }
  return [mix(a, b, t0), mix(a, b, t1)];
}

export function buildingMesh(z, tiles, decoded, focus) {
  const picks = [];
  tiles.forEach((tile, i) => {
    const d = decoded[i];
    if (!d?.buildings?.length) return;
    const ext = d.extent;
    if (!(ext > 0)) return;
    const distance = Math.hypot(tile.ox + 0.5 - focus[0], tile.y + 0.5 - focus[1]);
    for (const b of d.buildings) if (!b.hide3d) picks.push({ tile, ext, b, priority: Math.min(160, b.h) + 38 / (1 + distance ** 2) });
  });
  picks.sort((a, b) => b.priority - a.priority);

  const data = new Float32Array(MAX_TRIANGLES * 3 * BUILDING_STRIDE);
  let used = 0, count = 0, fallback = 0, tallest = 0, truncated = false;
  const vertex = (p, r, n, given) => {
    data[used++] = p[0] * r; data[used++] = p[1] * r; data[used++] = p[2] * r;
    data[used++] = n[0]; data[used++] = n[1]; data[used++] = n[2];
    data[used++] = given;
  };
  mesh: for (const { tile, ext, b } of picks) {
    const high = 1 + b.h / R_M, low = 1 + (b.base || 0) / R_M, given = b.supplied ? 1 : 0;
    const globe = ([x, y]) => lonLatToVec(tileLon(tile.ox + x / ext, z), tileLat(tile.y + y / ext, z));
    for (const { rings, sign } of polygons(b.rings)) {
      const mark = used;
      const xy = [], holes = [];
      for (const ring of rings) {
        if (xy.length) holes.push(xy.length / 2);
        for (let i = 0; i < ring.length; i++) xy.push(ring[i]);
      }
      if (xy.length > 18000) { truncated = true; continue; }
      const tri = earcut(xy, holes);
      const roofPoint = (i) => [xy[2 * tri[i]], xy[2 * tri[i] + 1]];
      const normal = globe([xy[0], xy[1]]);
      const worst = (tri.length * 5 + xy.length * 3) * BUILDING_STRIDE;
      if (used + worst > data.length) {
        truncated = true;
        if (data.length - used < BUILDING_STRIDE * 1500) break mesh;
        continue;
      }
      for (let i = 0; i < tri.length; i += 3) {
        const p = clipRoof([roofPoint(i), roofPoint(i + 1), roofPoint(i + 2)], ext).map(globe);
        for (let j = 2; j < p.length; j++) {
          vertex(p[0], high, normal, given); vertex(p[j - 1], high, normal, given); vertex(p[j], high, normal, given);
        }
      }
      for (const ring of rings) {
        for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
          const segment = clipWall([ring[j], ring[j + 1]], [ring[i], ring[i + 1]], ext);
          if (!segment) continue;
          const [a, c] = segment.map(globe), e = c.map((v, k) => v - a[k]);
          const n = [a[1] * e[2] - a[2] * e[1], a[2] * e[0] - a[0] * e[2], a[0] * e[1] - a[1] * e[0]];
          const norm = length(n);
          if (norm < 1e-11) continue;
          const wall = n.map((v) => sign * v / norm);
          vertex(a, low, wall, given); vertex(c, low, wall, given); vertex(c, high, wall, given);
          vertex(a, low, wall, given); vertex(c, high, wall, given); vertex(a, high, wall, given);
        }
      }
      if (used > mark) { count++; fallback += b.supplied ? 0 : 1; tallest = Math.max(tallest, b.h); }
    }
  }
  return { data: data.slice(0, used), count, fallback, tallest, truncated };
}
