// Land or water, close in (register A12): the rule the focus window uses to tell them apart, texel by texel.
// Pure arithmetic on typed arrays, with no DOM and no GL, so it runs in a worker (water.worker.js) off the frame
// loop, under node for the tests (build/test_app_math.mjs) and for the audit that scores it on real places
// (Research/modeling/audit_closewater.py). detail.js fetches its inputs and uses its answer.

// ============================================================================ land or water, close in
/**
 * WHICH TEXELS OF THE WINDOW ARE WATER (register A12).
 * The shipped water field is 5 km. Close in, a coast drawn from it shades the first kilometres of sea as land
 * and of land as sea, and a river or lake narrower than that is in the picture and is not water to the atlas.
 * Nothing on the three hosts the page may ask is a fine water map of the whole Earth:
 *   - NASA's MODIS mask (250 m, GIBS) knows rivers and lakes down to its cell, and is grossly wrong in places:
 *     it holds most of Manhattan as water. Scored against a 30 m record of surface water at 23 places
 *     (Research/modeling/audit_closewater.py) it gets 4.5% of texels wrong; the shipped field gets 10.2%.
 *   - the terrain tiles' sign tells the sea only, and a polder or the Dead Sea's shore is below it. Their
 *     flatness tells nothing (a third of a city is "flat" in them).
 *   - the picture's colour alone cannot tell the Seine from the Bois de Boulogne, anywhere-on-Earth weights or
 *     not (0.15 of the river found at best).
 * So the mask says roughly WHERE and the picture says exactly where. Inside one window water has a colour of
 * its own (navy, silt brown, glacier green), and the window is asked for it:
 *   1. every texel gets a first guess from its colour and slope, the same weights everywhere (`w`, fitted to the
 *      23 places; weak, and only used to check and to break ties);
 *   2. the window's water colours are counted over the mask's water, half a cell in from its edge, LESS what the
 *      first guess calls plainly land (Manhattan's roofs); its land colours over ground two cells clear of the mask;
 *   3. each texel is water if its colour is likelier among the water colours than the land colours, by more than
 *      its distance from the mask's water argues against (worth e^3 at two cells out);
 *   4. once more, counting the colours over the answer itself.
 * WHAT IT DOES NOT DO: find water of a colour the mask's water in this window does not have. A pond the colour of
 * the lake beside it is found; the Seine through Paris, which the mask has almost none of, stays land.
 *
 *   5. THE MASK IS NOT BELIEVED WHERE IT HAS FAR MORE WATER THAN THE ATLAS'S OWN FIELD. MODIS holds most of
 *      Manhattan as water. The shipped field (Natural Earth's 1:10m land, as a share of each 5 km cell) cannot
 *      draw a coast finely but it knows how much of a district is water; where the mask's share over 8 km runs
 *      a fifth to two fifths over it, the mask's water stops counting, as a vote and as a place to learn colours
 *      from. The Hudson is then water for its colour, learned from the bay, and the island is land.
 * Scored at 23 places (audit_closewater.py): 2.6% of texels wrong at 19 m and under 2.9% at every texel size to
 * 500 m, against the mask's 4.5% and the shipped field's 10.2%.
 * WHAT IT DOES NOT DO: find water of a colour the mask's water in this window does not have. A pond the colour of
 * the lake beside it is found; the Seine through Paris, which the mask has almost none of, stays land. And a
 * wrong patch of the mask whose colours occur nowhere else in the window, in a district the shipped field also
 * calls wet, stays water.
 *
 * g: {w, h: the grid; rgba: the picture on it (4 bytes a texel), or null: then the mask is the answer; elev:
 * metres, or null; mask: 1 where MODIS has water; ship: the shipped water fraction 0..1, or null; mx, my: metres
 * a texel; cell: the mask's cell in texels}. Returns a Uint8Array, 1 = water. `info` receives the seed counts.
 */
export const WATER_RULE = {
  w: [-1.22, 0.884, -2.572, 9.183, -10.686, -12.28],   // 1, luma, luma^2, (B - R) / sum, (G - max(R, B)) / sum, slope (m/m, capped at 0.2)
  bins: 16, prior: 3, reach: 2, erode: 0.5, clear: 2, seedWater: -2, seedLand: 2, global: 0.5, gcap: 8, cap: 6, n0: 2000, eps: 1e-5, minSeeds: 50, passes: 2,
  doubtM: 8000, doubt0: 0.2, doubt1: 0.4, bodyM: 55, body: 0.6,
};
/** Distance, in texels, from every texel to the nearest one whose mask value is `target`: a two-pass 3-4 chamfer (within 8% of the true distance). */
function chamfer(mask, w, h, target) {
  const d = new Float32Array(w * h), BIG = 1e9;
  for (let i = 0; i < d.length; i++) d[i] = mask[i] === target ? 0 : BIG;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const o = y * w + x; let v = d[o];
    if (v === 0) continue;
    if (x > 0) v = Math.min(v, d[o - 1] + 3);
    if (y > 0) { v = Math.min(v, d[o - w] + 3); if (x > 0) v = Math.min(v, d[o - w - 1] + 4); if (x < w - 1) v = Math.min(v, d[o - w + 1] + 4); }
    d[o] = v;
  }
  for (let y = h - 1; y >= 0; y--) for (let x = w - 1; x >= 0; x--) {
    const o = y * w + x; let v = d[o];
    if (v === 0) continue;
    if (x < w - 1) v = Math.min(v, d[o + 1] + 3);
    if (y < h - 1) { v = Math.min(v, d[o + w] + 3); if (x < w - 1) v = Math.min(v, d[o + w + 1] + 4); if (x > 0) v = Math.min(v, d[o + w - 1] + 4); }
    d[o] = v;
  }
  for (let i = 0; i < d.length; i++) d[i] /= 3;
  return d;
}
/** The mean of a 0/1 grid over a box of n x n texels about each texel (edges repeat): two running sums. */
export function boxMean(src, w, h, n) {
  const r0 = Math.floor(n / 2), r1 = n - 1 - r0, tmp = new Float32Array(w * h), out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) {
    let sum = 0; const o = y * w;
    for (let k = -r0; k <= r1; k++) sum += src[o + Math.max(0, Math.min(w - 1, k))];
    for (let x = 0; x < w; x++) { tmp[o + x] = sum / n; sum += src[o + Math.min(w - 1, x + r1 + 1)] - src[o + Math.max(0, x - r0)]; }
  }
  for (let x = 0; x < w; x++) {
    let sum = 0;
    for (let k = -r0; k <= r1; k++) sum += tmp[Math.max(0, Math.min(h - 1, k)) * w + x];
    for (let y = 0; y < h; y++) { out[y * w + x] = sum / n; sum += tmp[Math.min(h - 1, y + r1 + 1) * w + x] - tmp[Math.max(0, y - r0) * w + x]; }
  }
  return out;
}
export function waterFlag(g, info = null) {
  const { w, h, rgba, elev, mask, ship, mx, my } = g;
  const R = WATER_RULE, n = w * h, out = new Uint8Array(n);
  if (!rgba) { out.set(mask); return out; }
  const B = R.bins, sh = Math.log2(256 / B), px = Math.max(1, g.cell || 1);
  const dW = chamfer(mask, w, h, 0), dL = chamfer(mask, w, h, 1);        // how far inside the mask's water; how far outside it
  const wide = ship ? boxMean(mask, w, h, Math.max(1, Math.round(R.doubtM / my))) : null;
  const z0 = new Float32Array(n), cb = new Uint16Array(n), cls = new Int8Array(n);   // cls: 1 a water seed, -1 a land seed
  const doubted = wide ? new Uint8Array(n) : null;
  const sx = Math.max(1, Math.round(45 / mx)), sy = Math.max(1, Math.round(45 / my));
  let nw = 0, nl = 0;
  for (let y = 0; y < h; y++) {
    const ya = Math.max(0, y - sy) * w, yb = Math.min(h - 1, y + sy) * w;
    for (let x = 0; x < w; x++) {
      const o = y * w + x, r = rgba[o * 4] / 255, gg = rgba[o * 4 + 1] / 255, b = rgba[o * 4 + 2] / 255;
      const L = 0.2126 * r + 0.7152 * gg + 0.0722 * b, S = r + gg + b + 0.02;
      let slope = 0;
      if (elev) {
        const xa = Math.max(0, x - sx), xb = Math.min(w - 1, x + sx);
        slope = Math.min(0.2, Math.hypot((elev[y * w + xb] - elev[y * w + xa]) / (2 * sx * mx), (elev[yb + x] - elev[ya + x]) / (2 * sy * my)));
      }
      const first = Math.max(-R.gcap, Math.min(R.gcap, R.w[0] + R.w[1] * L + R.w[2] * L * L + R.w[3] * (b - r) / S + R.w[4] * (gg - Math.max(r, b)) / S + R.w[5] * slope));
      let doubt = 0, sure = true;
      if (wide) {
        const over = wide[o] - ship[o], t = Math.max(0, Math.min(1, (over - R.doubt0) / (R.doubt1 - R.doubt0)));
        doubt = t * t * (3 - 2 * t);
        sure = over < 0.5 * R.doubt0;                                     // colours are learned only well clear of the doubt (its fringe leaks)
      }
      const u = Math.max(-1, Math.min(1, (dW[o] - dL[o]) / (R.reach * px)));
      if (doubt > 0) doubted[o] = 1;
      z0[o] = R.global * first + R.prior * (u > 0 ? u * (1 - doubt) : u);
      cb[o] = (((rgba[o * 4] >> sh) * B) + (rgba[o * 4 + 1] >> sh)) * B + (rgba[o * 4 + 2] >> sh);
      if (dW[o] > R.erode * px && first > R.seedWater && sure) { cls[o] = 1; nw++; } else if (dL[o] > R.clear * px && first < R.seedLand) { cls[o] = -1; nl++; }
    }
  }
  if (info) { info.seedWater = nw; info.seedLand = nl; }
  const hw = new Float64Array(B * B * B), hl = new Float64Array(B * B * B), tmp = new Float64Array(B * B * B), llr = new Float32Array(B * B * B);
  const blur = (a) => {                                                   // a 3-bin mean along each colour axis: neighbouring colours vouch for each other
    for (const st of [1, B, B * B]) {
      tmp.set(a);
      for (let i = 0; i < a.length; i++) { const k = Math.floor(i / st) % B; a[i] = (tmp[i] + (k > 0 ? tmp[i - st] : 0) + (k < B - 1 ? tmp[i + st] : 0)) / 3; }
    }
  };
  for (let pass = 0; pass < R.passes; pass++) {
    if (nw < R.minSeeds || nl < R.minSeeds) break;
    hw.fill(0); hl.fill(0);
    for (let o = 0; o < n; o++) { if (cls[o] > 0) hw[cb[o]]++; else if (cls[o] < 0) hl[cb[o]]++; }
    blur(hw); blur(hl);
    const lam = nw / (nw + R.n0);                                         // a handful of seeds: lean on the first guess
    for (let i = 0; i < llr.length; i++) llr[i] = lam * Math.max(-R.cap, Math.min(R.cap, Math.log(hw[i] / nw + R.eps) - Math.log(hl[i] / nl + R.eps)));
    nw = 0; nl = 0;
    for (let o = 0; o < n; o++) { if (z0[o] + llr[cb[o]] > 0) { cls[o] = 1; nw++; } else { cls[o] = -1; nl++; } }
    if (pass === R.passes - 1 || nw < R.minSeeds || nl < R.minSeeds) { for (let o = 0; o < n; o++) out[o] = cls[o] > 0 ? 1 : 0; return cohere(out); }
  }
  for (let o = 0; o < n; o++) out[o] = z0[o] > 0 ? 1 : 0;                  // too few seeds to learn from: the first guess and the mask
  return cohere(out);
  // Where the mask is doubted, water is there on its colour alone, and the shadow between two towers has a
  // river's colour. There water must be a BODY: most of the texels within about 55 m of it water too.
  function cohere(f) {
    const k = 2 * Math.round(R.bodyM / my) + 1;
    if (!doubted || k < 3) return f;
    const near = boxMean(f, w, h, k);
    for (let o = 0; o < n; o++) if (doubted[o] && f[o] && near[o] < R.body) f[o] = 0;
    return f;
  }
}

/** The flag and the mean colour of the window's water in the picture's display values (what the join takes out of a coastal mean). */
export function runRule(g) {
  const info = {}, d = waterFlag(g, info);
  let waterC = [0.10, 0.15, 0.20];
  if (g.rgba) {
    let r = 0, gr = 0, b = 0, n = 0;
    for (let o = 0; o < d.length; o++) if (d[o]) { r += g.rgba[o * 4]; gr += g.rgba[o * 4 + 1]; b += g.rgba[o * 4 + 2]; n++; }
    if (n > 50) waterC = [r / n / 255, gr / n / 255, b / n / 255];
  }
  return { d, waterC, info };
}
