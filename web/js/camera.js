// The two cameras: a perspective globe and a Winkel Tripel sheet. The projection maths here is
// the JS twin of web/shaders/common.glsl; js/selftest.js checks that the two agree.

import { D2R, R2D, lonLatToVec, norm180 } from './astro.js';

export const R_KM = 6371.0088;
const TAN_HALF_FOV_DEFAULT = Math.tan(15 * D2R);  // 30 degree vertical field of view
const WT_C = 2 / Math.PI;
export const WT_XMAX = 1 + Math.PI / 2, WT_YMAX = Math.PI / 2;

export function wtForward(lonRad, latRad) {
  const c = Math.cos(latRad);
  const a = Math.acos(Math.max(-1, Math.min(1, c * Math.cos(lonRad / 2))));
  const sinc = a > 1e-6 ? Math.sin(a) / a : 1;
  return [0.5 * (lonRad * WT_C + 2 * c * Math.sin(lonRad / 2) / sinc), 0.5 * (latRad + Math.sin(latRad) / sinc)];
}

export function wtInverse(x, y) {
  if (Math.abs(y) > WT_YMAX + 1e-9 || Math.abs(x) > WT_XMAX + 1e-9) return null;
  let phi = Math.max(-1.5707, Math.min(1.5707, y));
  let lam = Math.max(-Math.PI, Math.min(Math.PI, 2 * x / (WT_C + Math.cos(phi))));
  const h = 1e-5;
  for (let i = 0; i < 14; i++) {
    const f = wtForward(lam, phi);
    const a = wtForward(lam + h, phi), b = wtForward(lam - h, phi), c = wtForward(lam, phi + h), d = wtForward(lam, phi - h);
    const flx = (a[0] - b[0]) / (2 * h), fly = (a[1] - b[1]) / (2 * h), fpx = (c[0] - d[0]) / (2 * h), fpy = (c[1] - d[1]) / (2 * h);
    const det = flx * fpy - fpx * fly;
    if (Math.abs(det) < 1e-12) break;
    const ex = f[0] - x, ey = f[1] - y;
    lam -= (ex * fpy - fpx * ey) / det;
    phi -= (flx * ey - ex * fly) / det;
    lam = Math.max(-Math.PI - 0.05, Math.min(Math.PI + 0.05, lam));
    phi = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, phi));
  }
  const r = wtForward(lam, phi);
  if ((r[0] - x) ** 2 + (r[1] - y) ** 2 > 1e-10 || Math.abs(lam) > Math.PI + 1e-6) return null;
  return [lam, phi];
}

export class Camera {
  constructor() {
    this.view = 'globe';
    this.lon = 15; this.lat = 22;          // sub-camera point, degrees
    this.dist = 5.2;                        // Earth radii from the centre
    this.mapCenter = [0, 0];                // sheet: projected coords at the screen centre
    this.mapUnitsPerPx = 0.005;             // sheet: projected units per CSS px
    this.w = 1; this.h = 1; this.dpr = 1;
    this.tanHalfFov = TAN_HALF_FOV_DEFAULT;
  }
  resize(w, h, dpr) {
    this.w = Math.max(1, w); this.h = Math.max(1, h); this.dpr = dpr;
    // a pane can be created at zero size; frame the Earth the first time there is a real viewport
    if (!this._framed && w > 8 && h > 8) { this._framed = true; if (!this._placed) this.home(); }
    if (!Number.isFinite(this.dist)) this.dist = 5.3;
  }

  basis() {
    const f = lonLatToVec(this.lon, this.lat).map((v) => -v);       // forward: towards the centre
    const l = this.lon * D2R, p = this.lat * D2R;
    const right = [-Math.sin(l), Math.cos(l), 0];
    const up = [-Math.sin(p) * Math.cos(l), -Math.sin(p) * Math.sin(l), Math.cos(p)];
    return { right, up, f, pos: f.map((v) => -v * this.dist) };
  }

  /** km of ground per CSS pixel at the view centre. */
  kmPerPx() {
    if (this.view === 'globe') return (this.dist - 1) * R_KM * 2 * this.tanHalfFov / this.h;
    return this.mapUnitsPerPx * R_KM;
  }
  setKmPerPx(k) {
    if (this.view === 'globe') this.dist = Math.max(1.02, Math.min(12, 1 + k * this.h / (R_KM * 2 * this.tanHalfFov)));
    else this.mapUnitsPerPx = Math.max(1e-5, Math.min(0.02, k / R_KM));
  }

  uniforms() {
    const b = this.basis();
    return {
      uView: this.view === 'globe' ? 0 : 1,
      uViewport: [this.w * this.dpr, this.h * this.dpr],
      uCamPos: b.pos,
      uCamBasis: [...b.right, ...b.up, ...b.f],                    // column-major mat3
      uTanHalfFov: this.tanHalfFov,
      uMapCenter: this.mapCenter,
      uMapScale: this.mapUnitsPerPx / this.dpr,
    };
  }

  /** lon/lat (deg) + height (Earth radii) -> [x, y] CSS px from the top-left, or null if hidden. */
  project(lon, lat, h = 0) {
    if (this.view === 'globe') {
      const b = this._b || this.basis();
      const p = lonLatToVec(lon, lat);
      const s = 1 + h;
      const px = p[0] * s, py = p[1] * s, pz = p[2] * s;
      const pc = px * b.pos[0] + py * b.pos[1] + pz * b.pos[2];
      const vx = px - b.pos[0], vy = py - b.pos[1], vz = pz - b.pos[2];
      const zc = vx * b.f[0] + vy * b.f[1] + vz * b.f[2];
      if (zc <= 0) return null;
      if (pc < 1) {
        if (h <= 0) return null;
        const vl = Math.hypot(vx, vy, vz);
        const bb = (b.pos[0] * vx + b.pos[1] * vy + b.pos[2] * vz) / vl;
        if (this.dist * this.dist - bb * bb <= 1) return null;      // behind the planet
      }
      const xc = vx * b.right[0] + vy * b.right[1] + vz * b.right[2];
      const yc = vx * b.up[0] + vy * b.up[1] + vz * b.up[2];
      const aspect = this.w / this.h;
      return [(xc / (zc * this.tanHalfFov * aspect) * 0.5 + 0.5) * this.w, (0.5 - yc / (zc * this.tanHalfFov) * 0.5) * this.h];
    }
    const xy = wtForward(lon * D2R, lat * D2R);
    return [(xy[0] - this.mapCenter[0]) / this.mapUnitsPerPx + this.w / 2, this.h / 2 - (xy[1] - this.mapCenter[1]) / this.mapUnitsPerPx];
  }
  /** Cache the basis for a batch of project() calls in one frame. */
  beginFrame() { this._b = this.basis(); }

  /** CSS px -> [lonDeg, latDeg] or null if the pixel is off the Earth. */
  unproject(x, y) {
    if (this.view === 'globe') {
      const b = this.basis();
      const aspect = this.w / this.h;
      const nx = (x / this.w * 2 - 1) * this.tanHalfFov * aspect, ny = (1 - y / this.h * 2) * this.tanHalfFov;
      let d = [0, 1, 2].map((i) => b.right[i] * nx + b.up[i] * ny + b.f[i]);
      const dl = Math.hypot(...d); d = d.map((v) => v / dl);
      const bb = b.pos[0] * d[0] + b.pos[1] * d[1] + b.pos[2] * d[2];
      const disc = bb * bb - (this.dist * this.dist - 1);
      if (disc <= 0 || bb >= 0) return null;
      const t = -bb - Math.sqrt(disc);
      const p = [0, 1, 2].map((i) => b.pos[i] + t * d[i]);
      return [Math.atan2(p[1], p[0]) * R2D, Math.asin(Math.max(-1, Math.min(1, p[2]))) * R2D];
    }
    const ll = wtInverse(this.mapCenter[0] + (x - this.w / 2) * this.mapUnitsPerPx, this.mapCenter[1] - (y - this.h / 2) * this.mapUnitsPerPx);
    return ll ? [ll[0] * R2D, ll[1] * R2D] : null;
  }

  pan(dxPx, dyPx) {
    if (this.view === 'globe') {
      const degPerPx = this.kmPerPx() / (R_KM * D2R);
      this.lon = norm180(this.lon - dxPx * degPerPx / Math.max(0.2, Math.cos(this.lat * D2R)));
      this.lat = Math.max(-89.5, Math.min(89.5, this.lat + dyPx * degPerPx));
    } else {
      this.mapCenter[0] = Math.max(-WT_XMAX, Math.min(WT_XMAX, this.mapCenter[0] - dxPx * this.mapUnitsPerPx));
      this.mapCenter[1] = Math.max(-WT_YMAX, Math.min(WT_YMAX, this.mapCenter[1] + dyPx * this.mapUnitsPerPx));
    }
  }

  /** Zoom by a factor about a screen point, keeping the place under the cursor still. */
  zoom(factor, x = this.w / 2, y = this.h / 2) {
    const before = this.unproject(x, y);
    const k = Math.max(0.35, Math.min(this.maxKmPerPx(), this.kmPerPx() * factor));
    this.setKmPerPx(k);
    if (!before) return;
    if (this.view === 'sheet') {
      const xy = wtForward(before[0] * D2R, before[1] * D2R);
      this.mapCenter = [xy[0] - (x - this.w / 2) * this.mapUnitsPerPx, xy[1] + (y - this.h / 2) * this.mapUnitsPerPx];
    } else {
      const after = this.unproject(x, y);
      if (after) {
        this.lon = norm180(this.lon + norm180(before[0] - after[0]));
        this.lat = Math.max(-89.5, Math.min(89.5, this.lat + (before[1] - after[1])));
      }
    }
  }
  maxKmPerPx() { return this.view === 'globe' ? 11 * R_KM * 2 * this.tanHalfFov / this.h : 2.3 * WT_XMAX * R_KM / this.w; }

  /** The framing that shows the whole Earth. */
  home() {
    if (this.view === 'globe') this.dist = 1 + 4.3 * Math.max(1, (this.h / this.w) * 1.15);
    else { this.mapCenter = [0, 0]; this.mapUnitsPerPx = Math.max(2 * WT_XMAX / (this.w * 0.94), 2 * WT_YMAX / (this.h * 0.86)); }
  }

  /**
   * A reference camera for scoring against a photograph: stand `dist` Earth radii above (lon, lat)
   * with north up and a field of view chosen so the disc's diameter is `discFrac` of the frame
   * height. NASA EPIC sits near 235 radii with the disc at about 0.8 of its frame.
   */
  refView(lon, lat, dist, discFrac) {
    this.view = 'globe'; this._placed = true;
    this.lon = norm180(lon); this.lat = lat; this.dist = dist;
    this.tanHalfFov = Math.tan(Math.asin(1 / dist)) / discFrac;
  }
  /** Back to the atlas's own 30 degree camera. */
  stdView() { this.tanHalfFov = TAN_HALF_FOV_DEFAULT; this.home(); }

  /** Centre on a place. On the sheet this moves the paper; on the globe it turns the planet. */
  lookAt(lon, lat) {
    this._placed = true;
    if (this.view === 'globe') { this.lon = norm180(lon); this.lat = Math.max(-89.5, Math.min(89.5, lat)); }
    else this.mapCenter = wtForward(lon * D2R, lat * D2R);
  }
  center() {
    if (this.view === 'globe') return [this.lon, this.lat];
    const ll = wtInverse(this.mapCenter[0], this.mapCenter[1]);
    return ll ? [ll[0] * R2D, ll[1] * R2D] : [0, 0];
  }
  setView(view) {
    if (view === this.view) return;
    const c = this.center(), k = this.kmPerPx();
    this.view = view;
    this.setKmPerPx(Math.min(k, this.maxKmPerPx()));
    this.lookAt(c[0], c[1]);
    if (k > this.maxKmPerPx() * 0.6) this.home();
  }
}
