// Run the app's own water rule (web/js/detail.js :: waterFlag) on grids prepared by
// Research/modeling/audit_closewater.py, so the audit scores what the page runs and not a copy of it.
//   node build/closewater_flags.mjs <dir>
// <dir>/jobs.json lists [{name, w, h, mx, my, cell, pool}]; for each, <name>.rgba (w*h*4 bytes), <name>.elev
// (w*h float32, little-endian), <name>.mask (w*h bytes) and, where ship is true, <name>.ship (w*h float32) are read and <name>.flag (w*h bytes) is written.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { waterFlag } from '../web/js/water.js';

const dir = process.argv[2];
const jobs = JSON.parse(readFileSync(join(dir, 'jobs.json'), 'utf8'));
for (const j of jobs) {
  const rgba = new Uint8ClampedArray(readFileSync(join(dir, `${j.name}.rgba`)));
  const eb = readFileSync(join(dir, `${j.name}.elev`));
  const elev = new Float32Array(eb.buffer, eb.byteOffset, eb.byteLength / 4);
  const mask = new Uint8Array(readFileSync(join(dir, `${j.name}.mask`)));
  if (rgba.length !== j.w * j.h * 4 || elev.length !== j.w * j.h || mask.length !== j.w * j.h) throw new Error(`${j.name}: the grids are not ${j.w} x ${j.h}`);
  const t0 = performance.now(), info = {};
  const sb = j.ship ? readFileSync(join(dir, `${j.name}.ship`)) : null;
  const ship = sb ? new Float32Array(sb.buffer, sb.byteOffset, sb.byteLength / 4) : null;
  const flag = waterFlag({ w: j.w, h: j.h, rgba: j.noPicture ? null : rgba, elev, mask, ship, mx: j.mx, my: j.my, cell: j.cell }, info);
  j.ms = Math.round(performance.now() - t0); j.seedWater = info.seedWater; j.seedLand = info.seedLand;
  writeFileSync(join(dir, `${j.name}.flag`), flag);
}
writeFileSync(join(dir, 'done.json'), JSON.stringify(jobs));
