// Streets and buildings for one window, off the frame loop: fetch the vector tiles, decode them, and draw the day
// overlay and the light pattern on the window's own grid (streets.js says what each is). detail.js posts
//   {id, win, w, h, z, tiles: [{x, y, ox}], texelM}
// and gets back {id, overlay: ImageBitmap|null, pattern: ImageBitmap, requests, bytes, cached, ms, roads, buildings}
// or {id, error}. {cancel: id} stops one.
import { OFM, STREETS, ROADS, ROAD_ORDER, RAIL, FILLS, LAMP_M, decodeTile, frame, tileLon, tileLat, shadowOffset } from './streets.js';

const CACHE = 80;                       // decoded tiles kept
const cache = new Map();
const jobs = new Map();
let template = null, templateAt = 0;

/** The tiles' address. OpenFreeMap publishes a new planet every week under a new path; its TileJSON says which. */
async function tileUrl(signal) {
  if (template && Date.now() - templateAt < 3600e3) return template;
  const r = await fetch(OFM.tilejson, { signal, mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer' });
  if (!r.ok) throw new Error(`streets: TileJSON HTTP ${r.status}`);
  const j = await r.json();
  if (!j.tiles || !/^https:\/\/tiles\.openfreemap\.org\/.*\{z\}\/\{x\}\/\{y\}/.test(j.tiles[0])) throw new Error('streets: the TileJSON names no tile address on the approved host');
  template = j.tiles[0]; templateAt = Date.now();
  return template;
}

async function getTile(z, t, job) {
  const key = `${z}/${t.x}/${t.y}`;
  let d = cache.get(key);
  if (d) { cache.delete(key); cache.set(key, d); job.cached++; return d; }
  const url = (await tileUrl(job.ctl.signal)).replace('{z}', z).replace('{x}', t.x).replace('{y}', t.y);
  let last;
  for (let a = 0; a < 3; a++) {
    try {
      job.requests++;
      const r = await fetch(url, { signal: job.ctl.signal, mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer' });
      // open sea and empty ground have no tile, or an empty one: nothing to draw there, and not a failure
      if (r.status === 404 || r.status === 204) { d = null; break; }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const b = new Uint8Array(await r.arrayBuffer());
      job.bytes += b.length;
      d = b.length ? decodeTile(b) : null;
      break;
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      last = e;
      if (a === 2) throw new Error(`streets tile ${key}: ${last.message || last}`);
      await new Promise((res) => setTimeout(res, 300 * (a + 1)));
    }
  }
  cache.set(key, d || { empty: true });
  while (cache.size > CACHE) cache.delete(cache.keys().next().value);
  return d || { empty: true };
}

const line = (g, parts) => { g.beginPath(); for (const p of parts) { g.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) g.lineTo(p[i], p[i + 1]); } };
const area = (g, rings) => { g.beginPath(); for (const p of rings) { g.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) g.lineTo(p[i], p[i + 1]); g.closePath(); } };
const grey = (v) => { const b = Math.round(255 * v); return `rgb(${b},${b},${b})`; };

async function run(msg) {
  const { id, win, w, h, z, tiles, texelM } = msg;
  const job = { ctl: new AbortController(), requests: 0, bytes: 0, cached: 0 };
  jobs.set(id, job);
  const t0 = performance.now(), marks = {};
  try {
    const got = new Array(tiles.length);
    let next = 0;
    const pull = async () => { while (next < tiles.length) { const k = next++; got[k] = await getTile(z, tiles[k], job); } };
    await Promise.all(Array.from({ length: Math.min(8, tiles.length) }, pull));
    if (job.ctl.signal.aborted) throw new DOMException('aborted', 'AbortError');

    const fr = frame(win, w, h);
    // Each tile's lines and rings in metres from the window's corner, with the tile's own square. A tile holds what
    // lies a little beyond its edge too, so that lines join; drawn unclipped, the strips where two tiles overlap took
    // every roof and road twice and showed as pale bands. Each tile is drawn inside its own square.
    const parts = [];
    let nRoads = 0, nBuildings = 0;
    tiles.forEach((t, k) => {
      const d = got[k]; if (!d || d.empty) return;
      const ext = d.extent;
      const c = (part) => {
        const o = new Float32Array(part.length);
        for (let i = 0; i < part.length; i += 2) { o[i] = fr.mx(tileLon(t.ox + part[i] / ext, z)); o[i + 1] = fr.my(tileLat(t.y + part[i + 1] / ext, z)); }
        return o;
      };
      const P = { roads: {}, rail: d.rail.map(c), buildings: d.buildings.map((b) => ({ h: b.h, rings: b.rings.map(c) })), fills: {},
        box: [fr.mx(tileLon(t.ox, z)), fr.my(tileLat(t.y, z)), fr.mx(tileLon(t.ox + 1, z)), fr.my(tileLat(t.y + 1, z))] };
      for (const cls of Object.keys(d.roads)) { P.roads[cls] = d.roads[cls].map(c); nRoads += P.roads[cls].length; }
      for (const cls of Object.keys(d.fills)) P.fills[cls] = d.fills[cls].map(c);
      nBuildings += P.buildings.length;
      parts.push(P);
    });
    marks.fetch = Math.round(performance.now() - t0);
    const withBuildings = texelM <= STREETS.buildingsM && nBuildings > 0;
    /** Run `draw(P)` for every tile, clipped to the tile's square. */
    const each = (g, draw) => { for (const P of parts) { g.save(); g.beginPath(); g.rect(P.box[0], P.box[1], P.box[2] - P.box[0], P.box[3] - P.box[1]); g.clip(); draw(P); g.restore(); } };

    // ---- the pattern: where light comes from. Opaque greys, the dimmer first, so that the brighter stands where two meet.
    const pc = new OffscreenCanvas(w, h), pg = pc.getContext('2d', { alpha: false });
    pg.fillStyle = '#000'; pg.fillRect(0, 0, w, h);
    pg.setTransform(fr.sx, 0, 0, fr.sy, 0, 0);
    pg.lineCap = 'round'; pg.lineJoin = 'round';
    each(pg, (P) => {
      for (const cls of Object.keys(P.fills).sort((a, b) => FILLS[a] - FILLS[b])) { pg.fillStyle = grey(FILLS[cls]); area(pg, P.fills[cls]); pg.fill('evenodd'); }
      if (withBuildings) { pg.fillStyle = grey(FILLS.building); for (const b of P.buildings) { area(pg, b.rings); pg.fill('evenodd'); } }
      for (const cls of ROAD_ORDER) {
        if (!P.roads[cls]) continue;
        const R = ROADS[cls];
        // never thinner than a texel and a half: a road finer than the grid would break into dots
        pg.lineWidth = Math.max(R.w + 2 * LAMP_M, 1.5 * texelM); pg.strokeStyle = grey(R.light);
        line(pg, P.roads[cls]); pg.stroke();
      }
    });
    marks.pattern = Math.round(performance.now() - t0);

    // ---- the day overlay: only where the grid is fine enough for it to be more than the photograph already shows
    let overlay = null;
    if (texelM <= 20) {
      const oc = new OffscreenCanvas(w, h), og = oc.getContext('2d');
      og.setTransform(fr.sx, 0, 0, fr.sy, 0, 0);
      og.lineCap = 'round'; og.lineJoin = 'round';
      if (withBuildings && texelM <= STREETS.shadowsM) {
        // A shadow is the footprint swept along the Sun's direction: each wall's quadrilateral, and the roof's outline
        // at the end. Drawn solid, every wall's piece wound the same way (two opposite walls' pieces wound against
        // each other cancel where they overlap) and a few hundred to a path (one path of a hundred thousand
        // overlapping pieces took the rasteriser over half a minute), then thinned to a shadow's darkness in one
        // step: nothing is darkened twice.
        og.fillStyle = 'rgb(6,8,14)';
        each(og, (P) => {
          let quads = 0;
          og.beginPath();
          for (const b of P.buildings) {
            const [dx, dy] = shadowOffset(b.h, fr.lat0);
            if (Math.hypot(dx, dy) < 0.6 * texelM) continue;
            for (const p of b.rings) {
              for (let i = 0; i + 3 < p.length; i += 2) {
                const ax = p[i], ay = p[i + 1], bx = p[i + 2], by = p[i + 3];
                if ((bx - ax) * dy - (by - ay) * dx > 0) { og.moveTo(ax, ay); og.lineTo(bx, by); og.lineTo(bx + dx, by + dy); og.lineTo(ax + dx, ay + dy); }
                else { og.moveTo(bx, by); og.lineTo(ax, ay); og.lineTo(ax + dx, ay + dy); og.lineTo(bx + dx, by + dy); }
                og.closePath();
                if (++quads % 300 === 0) { og.fill('nonzero'); og.beginPath(); }
              }
            }
          }
          og.fill('nonzero');
        });
        og.globalCompositeOperation = 'destination-in';
        og.fillStyle = 'rgba(0,0,0,0.50)';
        og.fillRect(0, 0, w / fr.sx, h / fr.sy);
        og.globalCompositeOperation = 'source-over';
        marks.shadows = Math.round(performance.now() - t0);
      }
      each(og, (P) => {
        for (const cls of ROAD_ORDER) {
          if (!P.roads[cls]) continue;
          const R = ROADS[cls];
          if (R.w < 0.45 * texelM) continue;
          og.lineWidth = R.w; og.strokeStyle = `rgba(126,125,122,${R.day})`;
          line(og, P.roads[cls]); og.stroke();
        }
        if (P.rail.length && RAIL.w >= 0.45 * texelM) { og.lineWidth = RAIL.w; og.strokeStyle = `rgba(66,62,60,${RAIL.day})`; line(og, P.rail); og.stroke(); }
      });
      marks.roads = Math.round(performance.now() - t0);
      if (withBuildings) {
        og.fillStyle = 'rgba(250,246,238,0.20)';
        og.strokeStyle = 'rgba(24,22,20,0.36)'; og.lineWidth = Math.min(1.2, 0.5 * texelM);
        each(og, (P) => { for (const b of P.buildings) { area(og, b.rings); og.fill('evenodd'); og.stroke(); } });
      }
      overlay = oc.transferToImageBitmap();
    }
    const pattern = pc.transferToImageBitmap();
    self.postMessage({ id, overlay, pattern, requests: job.requests, bytes: job.bytes, cached: job.cached, ms: Math.round(performance.now() - t0), marks, roads: nRoads, buildings: withBuildings ? nBuildings : 0 }, overlay ? [overlay, pattern] : [pattern]);
  } catch (e) {
    self.postMessage({ id, error: e && e.name === 'AbortError' ? 'aborted' : String((e && e.message) || e) });
  } finally { jobs.delete(id); }
}

self.onmessage = (e) => {
  if (e.data.cancel !== undefined) { const j = jobs.get(e.data.cancel); if (j) j.ctl.abort(); return; }
  run(e.data);
};
