// Feature data: countries, borders, places, physical names, plates, quakes, volcanoes, power
// stations, airports. Loaded once; everything else asks this module.

import { kmBetween } from './cards.js';
import { getJSON } from './gl.js';

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

  /** The unit that administers a point, by exact polygon test (the raster is only for tinting). */
  countryAt(lon, lat) {
    const x = lon * 100, y = lat * 100;
    for (const c of this.political.countries) {
      const b = c.bbox;
      if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) continue;
      for (const poly of c.polys) {
        let inside = false;
        for (const ring of poly) {
          for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
            const xi = ring[i], yi = ring[i + 1], xj = ring[j], yj = ring[j + 1];
            if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
          }
        }
        if (inside) return c;
      }
    }
    return null;
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

  /** Everything that can carry a name on the map, with the zoom range it shows at. */
  labelItems() {
    const items = [];
    for (const f of this.physical.features) {
      if (f.kind === 'Continent') { items.push({ text: f.name, lon: f.lon, lat: f.lat, cls: 'continent', prio: 0, maxKm: 60, minKm: 7, ref: ['feature', f] }); continue; }
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
      // within a rank, the more populous state wins a collision (alphabetical order put Belgium over France)
      items.push({ text: c.short, lon: c.lon, lat: c.lat, cls: 'country', rank: c.rank, prio: 8 + c.rank + 0.9 * (1 - Math.min(1, Math.log10((c.pop || 1) + 1) / 9.2)), maxKm, minKm: 0.7, ref: ['country', c] });
    }
    for (const r of this.places.rows) {
      const sr = r[4];
      let maxKm = [15, 10.5, 7.5, 5.2, 3.6, 2.6, 2.2, 1.5, 1.0, 0.8, 0.6][Math.min(10, sr)];
      if (r[9]) maxKm = Math.max(maxKm, 9);
      if (r[5]) maxKm = Math.max(maxKm, 4.2);
      items.push({ text: r[0], lon: r[1], lat: r[2], cls: 'city', pop: r[3], capital: !!r[5], prio: 16 + sr + (r[5] ? -1.5 : 0) + (r[9] ? -1 : 0), maxKm, ref: ['city', r] });
    }
    for (const p of this.physical.peaks) items.push({ text: `${p.name} ${p.elev} m`, lon: p.lon, lat: p.lat, cls: 'peak', prio: 60, maxKm: 2.6, ref: ['feature', { ...p, realm: 'land' }] });
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
    return out.sort((a, b) => a.s - b.s).slice(0, n);
  }
}
