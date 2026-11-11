// Insets on the whole-Earth sheet (register F1). At 26 km a pixel the shortest legible name is 520 to 1000 km
// long, so Central Europe, the Balkans, the Baltic states and the Lesser Antilles cannot be named where they
// lie. An inset is a SECOND VIEW OF THE SAME SHEET: the same projection, the same shader, the same fields and
// clock, the same borders and the same label machinery, at a finer scale, in a frame that sits over open
// water. It is not a picture: every pixel in it is a place, and a click in it opens the same card.
//
// This module is the geometry only (no DOM, no GL; build/test_app_math.mjs runs it under node). main.js
// renders, names and frames what is laid out here.
//
// HOW AN INSET IS LAID OUT. Each inset shows a FIXED piece of ground (centre and span) and lives in a FIXED
// piece of sea (a rectangle of the sheet, in the projection's own units, measured to hold no state's land).
// Every frame, the part of that sea that is in the window and under no panel is found; the inset is drawn at
// the finest scale at which its ground fits in that room, between kMin and kMax. If the room is too small for
// kMax, or the inset would magnify less than MIN_GAIN, it is not drawn at all. Scales are taken from the same
// 5% ladder the label layer solves on, so an inset's names are solved once per step, not once per pixel of drag.
//
// WHERE AND HOW BIG, and why (measured at 1440 x 900, both side panels open; 25.9 km a pixel):
//   - Between the panels the sheet shows 834 x 722 px. The open water in it is four holes: the south-east
//     Pacific, the South Atlantic, the southern Indian Ocean (each 150 to 190 px wide and 250 to 300 high)
//     and a strip of Southern Ocean 140 px high. A Europe inset that named everything (2 E to 31 E, 35 N to
//     60 N at 6 km a pixel, 27 states the main map cannot name) would be 400 x 460 px: there is no such water.
//   - EUROPE goes in the south-east Pacific hole, the only one that holds no state and no other name. Its
//     ground is the strip from the Baltic states to northern Greece (13.6-26.9 E, 40.4-60 N), which is the
//     shape of the hole. At 8.56 km a pixel (3.0 x, 146 x 254 px) it names 17 states, 14 of which the main map
//     cannot. The frame stops short of the Peruvian coast on the east (20 px wider it named 16) and of Pitcairn
//     on the west. The Levant and the Caucasus would need it to reach 50 E; they do not fit and are left out.
//   - LESSER ANTILLES goes in the southern Indian Ocean, below that ocean's name: the one rectangle of its
//     size between the panels with no land in it at all. At 8.15 km a pixel (3.2 x, 106 x 144 px) it names all
//     eight island states, four of which the main map cannot.
//   - Both fade out between INSET_FULL and INSET_GONE km a pixel on the main map (see below), and are never
//     drawn on the globe. In a larger window the same seas are larger and each inset grows, to kMin at most.
// The Europe frame covers three specks of land that Natural Earth's 1:50m outlines mostly do not carry: Easter
// Island and Sala y Gomez (Chile) and Ducie atoll (Pitcairn). There is no rectangle of this size on the sheet
// between the panels that covers none. Research/modeling/audit_labels.py reports what lies under each frame.

import { Camera, R_KM, wtForward } from './camera.js?v=20261111T032852Z';
import { D2R } from './astro.js?v=20261111T032852Z';

const LADDER = 1.05;                 // the label layer's scale ladder (overlays.js, ZOOM_STEP)
export const MIN_GAIN = 1.5;         // an inset that magnifies less than this is not worth its frame
export const INSET_PAD = 6;          // px kept between an inset's frame and a panel or another inset
// Main-map scale, km a pixel: an inset is whole above INSET_FULL and gone below INSET_GONE. Measured on the main
// map centred on Europe (1440 x 900): of the 20 states the Europe inset names, the main map itself names 4 at 26
// km a pixel, 8 at 19, 10 at 17, 12 at 15.5, 15 at 14 and 18 at 12.5; of the 8 in the Antilles inset, 4, 5, 5, 6,
// 7 and 7. So an inset is whole while the main map names about half of what it names, and gone once the main map
// names nine in ten. (Long before that it has usually left the window, or met a panel, and is not drawn.)
export const INSET_FULL = 15.5, INSET_GONE = 12.5;

// sea: [X0, Y0, X1, Y1] in Winkel Tripel units (x east, y north), the water the frame may sit on.
// spanKm: the ground shown, east-west and north-south, in km on the sheet. gravity: where in its room the frame
// sits (0 = left / top, 1 = right / bottom); chosen so that it holds to the side of the sea that is land, which
// moves with the map, and not to the side that is a panel, which does not.
export const INSETS = [
  { id: 'europe', title: 'Europe', center: [20.6, 50.2], spanKm: [1250, 2180], kMin: 6.6, kMax: 9.4,
    sea: [-1.7413, -1.1690, -1.1446, -0.1299], gravity: [1, 0.5] },
  { id: 'antilles', title: 'Lesser Antilles', center: [-61.3, 14.4], spanKm: [870, 1180], kMin: 5.4, kMax: 8.4,
    sea: [1.0350, -1.1771, 1.4774, -0.5074], gravity: [0.5, 0] },
];

/** 0..1: how much of an inset shows at this main-map scale. */
export function insetAlpha(kmPerPx) {
  const t = Math.max(0, Math.min(1, (kmPerPx - INSET_GONE) / (INSET_FULL - INSET_GONE)));
  return t * t * (3 - 2 * t);
}

/** The sub-rectangle of box = [x0, y0, x1, y1] that touches nothing in taken and holds the largest rectangle of
 *  the given proportions (aspect = [w, h]); null if there is none. Its edges are edges of the box or of what is taken. */
export function freeRect(box, taken, aspect) {
  if (!(box[2] > box[0] && box[3] > box[1])) return null;
  const hit = taken.filter((t) => t[0] < box[2] && t[2] > box[0] && t[1] < box[3] && t[3] > box[1]);
  const xs = [box[0], box[2]], ys = [box[1], box[3]];
  for (const t of hit) {
    for (const v of [t[0], t[2]]) if (v > box[0] && v < box[2]) xs.push(v);
    for (const v of [t[1], t[3]]) if (v > box[1] && v < box[3]) ys.push(v);
  }
  let best = null, bs = 0, ba = 0;
  for (const x0 of xs) for (const x1 of xs) {
    if (!(x1 > x0)) continue;
    for (const y0 of ys) for (const y1 of ys) {
      if (!(y1 > y0)) continue;
      if (hit.some((t) => t[0] < x1 && t[2] > x0 && t[1] < y1 && t[3] > y0)) continue;
      const s = Math.min((x1 - x0) / aspect[0], (y1 - y0) / aspect[1]), a = (x1 - x0) * (y1 - y0);
      if (s > bs + 1e-9 || (s > bs - 1e-9 && a > ba)) { bs = s; ba = a; best = [x0, y0, x1, y1]; }
    }
  }
  return best;
}

/** Where an inset goes for this main camera (the sheet), given the rectangles already taken (CSS px).
 *  Returns { x, y, w, h, k } in whole CSS px and km a pixel, or null when there is no room for it. */
export function fitInset(def, cam, taken) {
  const u = cam.mapUnitsPerPx, cx = cam.w / 2, cy = cam.h / 2, S = def.sea, c = cam.mapCenter;
  const box = [Math.max(INSET_PAD, cx + (S[0] - c[0]) / u), Math.max(INSET_PAD, cy - (S[3] - c[1]) / u),
    Math.min(cam.w - INSET_PAD, cx + (S[2] - c[0]) / u), Math.min(cam.h - INSET_PAD, cy - (S[1] - c[1]) / u)];
  const free = freeRect(box, taken, def.spanKm);
  if (!free) return null;
  const fw = Math.floor(free[2] - free[0]), fh = Math.floor(free[3] - free[1]);
  if (fw < 8 || fh < 8) return null;
  let k = Math.max(def.kMin, def.spanKm[0] / fw, def.spanKm[1] / fh);
  k = Math.pow(LADDER, Math.ceil(Math.log(k) / Math.log(LADDER) - 1e-6));
  if (k > def.kMax || cam.kmPerPx() < MIN_GAIN * k) return null;
  const w = Math.floor(def.spanKm[0] / k), h = Math.floor(def.spanKm[1] / k);
  return { x: Math.round(free[0] + (free[2] - free[0] - w) * def.gravity[0]), y: Math.round(free[1] + (free[3] - free[1] - h) * def.gravity[1]), w, h, k };
}

export class Inset {
  constructor(def) {
    this.def = def; this.id = def.id;
    this.cam = new Camera(); this.cam.view = 'sheet'; this.cam._placed = this.cam._framed = true;
    this.cam.mapCenter = wtForward(def.center[0] * D2R, def.center[1] * D2R);
    this.rect = null; this.k = 0; this.alpha = 0; this._sig = '';
  }
  /** Lay it out against the main camera. taken: rectangles it must keep clear of, or null to hide it. True when it changed. */
  layout(cam, taken, alpha, dpr) {
    const fit = taken && alpha > 0 ? fitInset(this.def, cam, taken) : null;
    if (fit) {
      this.rect = { x: fit.x, y: fit.y, w: fit.w, h: fit.h }; this.k = fit.k; this.alpha = alpha;
      this.cam.resize(fit.w, fit.h, dpr); this.cam.mapUnitsPerPx = fit.k / R_KM;
    } else { this.rect = null; this.alpha = 0; }
    const sig = fit ? `${fit.x},${fit.y},${fit.w},${fit.h},${fit.k},${alpha},${dpr}` : '';
    if (sig === this._sig) return false;
    this._sig = sig;
    return true;
  }
  holds(x, y) { const r = this.rect; return !!r && x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h; }
  /** The rectangle of the main map that this inset magnifies, CSS px: [x0, y0, x1, y1]. */
  source(cam) {
    const r = this.rect, m = this.k / cam.kmPerPx(), u = cam.mapUnitsPerPx, c = this.cam.mapCenter;
    const x = cam.w / 2 + (c[0] - cam.mapCenter[0]) / u, y = cam.h / 2 - (c[1] - cam.mapCenter[1]) / u;
    return [x - (r.w * m) / 2, y - (r.h * m) / 2, x + (r.w * m) / 2, y + (r.h * m) / 2];
  }
}
