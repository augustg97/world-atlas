// Development aid, loaded only on demand from the console:
//     await (await import('/js/refshots.js')).renderEpic('r1')
// Stands the camera where NASA's EPIC stood for each frame in dev/epic_frames.json, at the same
// instant, and posts each render to build/serve.py (scratchpad/epic_<tag>_<frame>.jpg).
// Research/modeling/epic_compare.py then scores the pairs. Use a square window, 1024 x 1024.

const ON = ['clouds', 'air', 'daylight', 'ice'];

export async function renderEpic(tag = 'r0', on = ON) {
  const A = window.ATLAS;
  const frames = await (await fetch('/dev/epic_frames.json', { cache: 'no-store' })).json();
  for (const k of Object.keys(A.state.layers)) A.state.layers[k] = on.includes(k);
  A.setStyle('space'); A.setLens('none');
  const out = [];
  for (const e of frames) {
    A.setTime(Date.parse(e.t));
    A.refView(e.lon, e.lat, e.dist, e.f);
    let tries = 0;
    do { A.step(3); await new Promise((r) => setTimeout(r, 300)); tries++; } while (!A.settled() && tries < 80);
    if (!A.settled()) throw new Error(`fields never settled for ${e.n}`);
    A.redraw(); A.step(3);
    out.push(`${e.n} sun ${A.astro.sun.lon.toFixed(3)},${A.astro.sun.lat.toFixed(3)} ${await A.shot(`epic_${tag}_${e.n}.jpg`)}`);
  }
  return out;
}
