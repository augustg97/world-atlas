// Feature data: countries, borders, places, physical names, plates, quakes, volcanoes, power
// stations, airports. Loaded once; everything else asks this module.

import { kmBetween } from './cards.js?v=20261112T060955Z';
import { getJSON } from './gl.js?v=20261112T060955Z';

const get = (f) => getJSON('data/' + f);

export class Data {
  async loadCore() {
    [this.political, this.places, this.physical, this.stats] = await Promise.all([get('political.json'), get('places.json'), get('physical.json'), get('stats.json')]);
    this.countryByA3 = Object.fromEntries(this.political.countries.map((c) => [c.a3, c]));
    this.countryById = Object.fromEntries(this.political.countries.map((c) => [c.id, c]));
    return this;
  }
  async loadLazy(name) {
    if (this[name] || this['_' + name]) return this['_' + name];
    this['_' + name] = get({ plates: 'plates.json', quakes: 'quakes.json', volcanoes: 'volcanoes.json', power: 'power.json', air: 'air.json' }[name]).then((j) => { this[name] = j; return j; });
    return this['_' + name];
  }

  /** Exact test: is the point inside this unit? */
  inCountry(c, lon, lat) {
    const b = c.bbox;
    if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) return false;
    const x = lon * 100, y = lat * 100;
    // each part's own box first: an archipelago is hundreds of parts and a point is in the box of very few
    const pb = c._pb || (c._pb = c.polys.map((poly) => { const r = poly[0]; let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; for (let i = 0; i < r.length; i += 2) { if (r[i] < x0) x0 = r[i]; if (r[i] > x1) x1 = r[i]; if (r[i + 1] < y0) y0 = r[i + 1]; if (r[i + 1] > y1) y1 = r[i + 1]; } return [x0, y0, x1, y1]; }));
    for (let n = 0; n < c.polys.length; n++) {
      const q = pb[n];
      if (x < q[0] || x > q[2] || y < q[1] || y > q[3]) continue;
      const poly = c.polys[n];
      let inside = false;
      for (const ring of poly) {
        for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
          const xi = ring[i], yi = ring[i + 1], xj = ring[j], yj = ring[j + 1];
          if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
        }
      }
      if (inside) return true;
    }
    return false;
  }

  /** The unit that administers a point, by exact polygon test (the raster is only for tinting). */
  countryAt(lon, lat) {
    for (const c of this.political.countries) if (this.inCountry(c, lon, lat)) return c;
    return null;
  }

  /**
   * Which unit holds each 0.1 degree cell (its id; 0 = none: sea, or a lake Natural Earth leaves outside
   * the country polygons). The label layer asks it thousands of times a frame what lies under a name, which
   * the exact test above is too slow for. Scanline fill at cell centres, largest unit first so that an
   * enclave drawn without a hole still shows.
   */
  ownerGrid() {
    if (this._owner) return this._owner;
    const cols = 3600, rows = 1800, id = new Uint8Array(cols * rows);
    // The same at 0.4 degrees, for the whole-Earth scales where a 0.1 degree cell is under half a pixel and looking at
    // every cell under a name would cost too much: 0 no land, a unit's id if it alone has land in the block, 255 if several do.
    const pc = cols / 4, pr = rows / 4, pool = new Uint8Array(pc * pr);
    const mark = (r, ca, cb, v) => { const o = (r >> 2) * pc; for (let q = ca >> 2; q <= cb >> 2; q++) { const w = pool[o + q]; if (!w) pool[o + q] = v; else if (w !== v) pool[o + q] = 255; } };
    const units = this.political.countries.slice().sort((a, b) => (b.area || 0) - (a.area || 0));
    for (const c of units) {
      for (const poly of c.polys) {
        let ymin = Infinity, ymax = -Infinity;
        const ext = poly[0];
        for (let i = 1; i < ext.length; i += 2) { if (ext[i] < ymin) ymin = ext[i]; if (ext[i] > ymax) ymax = ext[i]; }
        // row r has its centre at y = 8995 - 10 r (hundredths of a degree); a crossing counts when ya <= y < yb
        const r0 = Math.max(0, Math.floor((8995 - ymax) / 10) + 1), r1 = Math.min(rows - 1, Math.floor((8995 - ymin) / 10));
        if (r1 < r0) continue;
        const xs = [];
        for (let r = r0; r <= r1; r++) xs.push([]);
        for (const ring of poly) {
          for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
            const xi = ring[i], yi = ring[i + 1], xj = ring[j], yj = ring[j + 1];
            if (yi === yj) continue;
            const ya = Math.min(yi, yj), yb = Math.max(yi, yj);
            const ra = Math.max(r0, Math.floor((8995 - yb) / 10) + 1), rb = Math.min(r1, Math.floor((8995 - ya) / 10));
            for (let r = ra; r <= rb; r++) xs[r - r0].push(xi + ((8995 - 10 * r - yi) * (xj - xi)) / (yj - yi));
          }
        }
        for (let r = r0; r <= r1; r++) {
          const row = xs[r - r0];
          if (row.length < 2) continue;
          row.sort((a, b) => a - b);
          for (let q = 0; q + 1 < row.length; q += 2) {
            const ca = Math.max(0, Math.ceil((row[q] + 17995) / 10)), cb = Math.min(cols, Math.ceil((row[q + 1] + 17995) / 10));
            if (cb > ca) { id.fill(c.id, r * cols + ca, r * cols + cb); mark(r, ca, cb - 1, c.id); }
          }
        }
      }
    }
    // Every vertex of every outline also claims its cell if the cell is still sea: an island smaller than a cell
    // is then on the raster, and every coast is drawn half a cell generous. A name set "in open water" by this
    // raster is therefore clear of all land, however small.
    for (const c of units) {
      for (const poly of c.polys) for (const ring of poly) for (let i = 0; i < ring.length; i += 2) {
        const n = Math.min(rows - 1, Math.max(0, Math.floor((9000 - ring[i + 1]) / 10))) * cols + Math.min(cols - 1, Math.max(0, Math.floor((ring[i] + 18000) / 10)));
        if (!id[n]) { id[n] = c.id; mark((n / cols) | 0, n % cols, n % cols, c.id); }
      }
    }
    this._owner = { cell: 0.1, cols, rows, id, pool, poolCols: pc, poolRows: pr, aspects: this.political.label_aspects || [], inside: (c, lon, lat) => this.inCountry(c, lon, lat) };
    return this._owner;
  }

  /** The named sea a point most plausibly lies in: nearest marine label relative to that sea's size. Generic tier. */
  seaAt(lon, lat) {
    let best = null, bs = 0.8;
    for (const f of this.physical.features) {
      if (f.realm !== 'sea') continue;
      const d = kmBetween(lon, lat, f.lon, f.lat) / 111.2;
      const s = d / Math.max(f.size, 1.5);
      if (s < bs) { bs = s; best = f; }
    }
    return best ? best.name : null;
  }

  disputeNear(lon, lat) {
    let best = null, bd = 900;
    for (const d of this.political.disputes) { const k = kmBetween(lon, lat, d.lon, d.lat); if (k < bd) { bd = k; best = d; } }
    return best ? `${best.name}: ${best.note}.` : null;
  }

  /**
   * The drawn river nearest a point, if one lies within maxKm: { i, river, km, lon, lat }, the last two the nearest
   * point ON its line. Distances are to the segments (their vertices can be tens of km apart), on a local flat map.
   */
  riverNear(lon, lat, maxKm) {
    const R = this.physical.rivers, box = this._rbox || (this._rbox = R.map((r) => {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const l of r.lines) for (let i = 0; i < l.length; i += 2) { if (l[i] < x0) x0 = l[i]; if (l[i] > x1) x1 = l[i]; if (l[i + 1] < y0) y0 = l[i + 1]; if (l[i + 1] > y1) y1 = l[i + 1]; }
      return [x0 / 100, y0 / 100, x1 / 100, y1 / 100];
    }));
    const kx = 111.195 * Math.cos(lat * Math.PI / 180), ky = 111.195, padY = maxKm / ky, padX = maxKm / Math.max(kx, 1e-6);
    let best = null, bd = maxKm;
    for (let n = 0; n < R.length; n++) {
      const r = R[n], b = box[n];
      if (!r.name || lon < b[0] - padX || lon > b[2] + padX || lat < b[1] - padY || lat > b[3] + padY) continue;
      for (const l of r.lines) for (let i = 0; i + 3 < l.length; i += 2) {
        const ax = (l[i] / 100 - lon) * kx, ay = (l[i + 1] / 100 - lat) * ky, bx = (l[i + 2] / 100 - lon) * kx, by = (l[i + 3] / 100 - lat) * ky;
        const dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy, t = len ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len)) : 0;
        const d = Math.hypot(ax + t * dx, ay + t * dy);
        if (d < bd) { bd = d; best = { i: n, river: r, km: d, lon: lon + (ax + t * dx) / kx, lat: lat + (ay + t * dy) / ky }; }
      }
    }
    return best;
  }
  /** A river as something a card can be opened for: the reach, and a point on its line (the middle of its longest line unless given). */
  riverItem(r, lon, lat) {
    if (lon === undefined) { const l = r.lines.reduce((a, b) => (b.length > a.length ? b : a), r.lines[0] || []), m = (l.length >> 2) << 1; lon = l[m] / 100; lat = l[m + 1] / 100; }
    return { name: r.name, kind: 'River', rank: r.rank, lon, lat, realm: 'land', river: r };
  }
  /** "index|lon|lat" from a card's link -> what app.pick() takes. The river's card opens as a feature's does. */
  riverRef(s) {
    const [i, lon, lat] = s.split('|').map(Number), r = this.physical.rivers[i];
    return r && r.name && Number.isFinite(lon) && Number.isFinite(lat) ? { lon, lat, km: Infinity, ref: ['feature', this.riverItem(r, lon, lat)] } : null;
  }

  /** Everything that can carry a name on the map, with the zoom range it shows at. */
  labelItems() {
    const items = [];
    for (const f of this.physical.features) {
      // a continent's name is set last, in spaced capitals across the states and clear of every other name (overlays.js, _spread)
      if (f.kind === 'Continent') { items.push({ text: f.name, lon: f.lon, lat: f.lat, cls: 'continent', prio: 9.5, maxKm: 60, minKm: 7, ref: ['feature', f] }); continue; }
      if (f.realm === 'sea') {
        const maxKm = [60, 26, 15, 9, 6, 4, 3][Math.min(6, f.rank)];
        items.push({ text: f.name, lon: f.lon, lat: f.lat, cls: 'ocean', rank: f.rank, prio: f.rank <= 0 ? 1 : 24 + f.rank, maxKm, ref: ['feature', f] });
      } else {
        const maxKm = [14, 12, 8, 5.5, 4, 2.6, 2][Math.min(6, f.rank)];
        items.push({ text: f.name, lon: f.lon, lat: f.lat, cls: 'feature', rank: f.rank, prio: 40 + f.rank, maxKm, ref: ['feature', f] });
      }
    }
    for (const c of this.political.countries) {
      const maxKm = { 1: 40, 2: 26, 3: 16, 4: 11, 5: 7.5, 6: 5.5 }[c.rank] || 3.5;
      const small = 0.9 * (1 - Math.min(1, Math.log10((c.pop || 1) + 1) / 9.2));       // 0 for the most populous
      // A STATE is a unit that is the home part of its sovereignty (Natural Earth HOMEPART) and that Natural
      // Earth types as a country, a sovereignty or a self-administering disputed state: the 193 UN members,
      // the Vatican, Taiwan, Kosovo, N. Cyprus and Somaliland. Its name is placed by its own geometry at
      // every zoom (overlays.js, Labels), ahead of every other unit, and where two states want the same
      // room the more populous one has it. Every other unit (dependencies, non-home parts, indeterminate
      // areas) keeps the old treatment: one position at its label point, shown from its rank's zoom on.
      const state = !!c.home && ['Sovereign country', 'Country', 'Sovereignty', 'Disputed'].includes(c.type) && !!c.lp;
      items.push({ text: c.short, abbr: state && c.abbr && c.abbr.length < c.short.length ? c.abbr : null, lon: c.lon, lat: c.lat, cls: 'country', rank: c.rank, state,
        roomy: !state && !!c.lp && (c.type === 'Dependency' || c.type === 'Country'),    // may also show earlier, once its full name fits inside it
        prio: state ? 8 + small : 8 + c.rank + small, maxKm: state ? 1e9 : maxKm, minKm: 0.7, ref: ['country', c] });
    }
    for (const r of this.places.rows) {
      const sr = r[4];
      let maxKm = [15, 10.5, 7.5, 5.2, 3.6, 2.6, 2.2, 1.5, 1.0, 0.8, 0.6][Math.min(10, sr)];
      if (r[9]) maxKm = Math.max(maxKm, 9);
      if (r[5]) maxKm = Math.max(maxKm, 4.2);
      items.push({ text: r[0], lon: r[1], lat: r[2], cls: 'city', pop: r[3], capital: !!r[5], prio: 16 + sr + (r[5] ? -1.5 : 0) + (r[9] ? -1 : 0), maxKm, ref: ['city', r] });
    }
    for (const p of this.physical.peaks) items.push({ text: `${p.name} ${p.elev} m`, lon: p.lon, lat: p.lat, cls: 'peak', prio: 60, maxKm: 2.6, ref: ['feature', { ...p, realm: 'land' }] });
    items.geo = this.ownerGrid();
    return items;
  }

  search(q, n = 8) {
    q = q.trim().toLowerCase();
    if (q.length < 2) return [];
    const out = [];
    const score = (name) => { const s = name.toLowerCase(); return s === q ? 0 : s.startsWith(q) ? 1 : s.includes(q) ? 2 : -1; };
    for (const c of this.political.countries) { const s = Math.min(...[c.name, c.short, c.endonym || ''].map(score).filter((v) => v >= 0), 9); if (s < 9) out.push({ s: s + c.rank * 0.01, label: c.name, sub: c.type, ref: ['country', c], lon: c.lon, lat: c.lat, km: 6 }); }
    for (const r of this.places.rows) { const s = score(r[0]); if (s >= 0) out.push({ s: s + 0.3 + r[4] * 0.02, label: r[0], sub: (this.countryByA3[r[6]] || {}).name || r[6], ref: ['city', r], lon: r[1], lat: r[2], km: 1.6 }); }
    for (const f of this.physical.features) { const s = score(f.name); if (s >= 0) out.push({ s: s + 0.5 + f.rank * 0.02, label: f.name, sub: f.kind, ref: ['feature', f], lon: f.lon, lat: f.lat, km: Math.max(2, Math.min(14, f.size / 4)) }); }
    // rivers: one hit a name (a river is drawn as several reaches), at the reach with the longest line
    const rv = new Map();
    for (const r of this.physical.rivers) { if (!r.name || !r.lines.length || !r.lines[0].length || score(r.name) < 0) continue; const len = Math.max(...r.lines.map((l) => l.length)), had = rv.get(r.name); if (!had || len > had.len) rv.set(r.name, { r, len }); }
    for (const { r } of rv.values()) { const f = this.riverItem(r); out.push({ s: score(r.name) + 0.6 + r.rank * 0.02, label: r.name, sub: 'River', ref: ['feature', f], lon: f.lon, lat: f.lat, km: 6 }); }
    return out.sort((a, b) => a.s - b.s).slice(0, n);
  }
}
