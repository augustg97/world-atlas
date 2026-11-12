// For audit_streets.py: read vector tiles with the page's own decoder and frame (web/js/streets.js) and print what
// it finds as JSON, in longitude and latitude. One line per tile file named <z>_<x>_<y>.pbf.
//   node build/streets_dump.mjs reference/streets/14_8298_5636.pbf ...
import { readFileSync } from 'node:fs';
import { basename } from 'node:path';
import { decodeTile, tileLon, tileLat } from '../web/js/streets.js';

for (const f of process.argv.slice(2)) {
  const [z, x, y] = basename(f, '.pbf').split('_').map(Number);
  const b = readFileSync(f);
  const d = b.length ? decodeTile(new Uint8Array(b)) : { extent: 4096, roads: {}, rail: [], buildings: [], fills: {} };
  const ll = (p) => { const o = []; for (let i = 0; i < p.length; i += 2) o.push(+tileLon(x + p[i] / d.extent, z).toFixed(7), +tileLat(y + p[i + 1] / d.extent, z).toFixed(7)); return o; };
  console.log(JSON.stringify({ z, x, y, box: [tileLon(x, z), tileLat(y, z), tileLon(x + 1, z), tileLat(y + 1, z)],
    buildings: d.buildings.map((q) => ({ h: q.h, rings: q.rings.map(ll) })), roads: Object.fromEntries(Object.entries(d.roads).map(([k, v]) => [k, v.map(ll)])) }));
}
