// Network feeds. Each one is LIVE or OBSERVED (SCOPE section 5): it carries its own timestamp,
// reports plainly when it is unavailable, and never presents a stale value as current.

import { loadBitmap, texFromImage, texFromData } from './gl.js';

const HOUR = 3600000, DAY = 86400000;

export class Live {
  constructor(gl, fields, onChange) {
    this.gl = gl; this.fields = fields; this.onChange = onChange || (() => {});
    this.status = { quakes: 'idle', aurora: 'idle', today: 'idle', sats: 'idle' };
    this.note = {};
    this.quakes = null; this.sats = null; this.todayDate = null;
  }
  _set(k, s, note) { this.status[k] = s; if (note !== undefined) this.note[k] = note; this.onChange(k, s); }

  async loadQuakes() {
    if (this.status.quakes === 'loading') return;
    this._set('quakes', 'loading');
    try {
      const j = await (await fetch('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_month.geojson')).json();
      this.quakes = { fetched: Date.now(), generated: j.metadata.generated,
        rows: j.features.map((f) => [new Date(f.properties.time).toISOString(), f.geometry.coordinates[0], f.geometry.coordinates[1], f.geometry.coordinates[2], f.properties.mag, f.properties.place || '', f.properties.time]) };
      this._set('quakes', 'ready', `USGS feed generated ${new Date(j.metadata.generated).toISOString().slice(0, 16).replace('T', ' ')} UTC`);
    } catch (e) { this._set('quakes', 'unavailable', 'The USGS feed could not be reached.'); }
  }

  /** NOAA OVATION: [lon 0..359, lat -90..90, probability] on a 1-degree NODE grid -> canonical 360 x 180 cells. */
  async loadAurora() {
    if (this.status.aurora === 'loading') return;
    this._set('aurora', 'loading');
    try {
      const j = await (await fetch('https://services.swpc.noaa.gov/json/ovation_aurora_latest.json')).json();
      const node = new Float32Array(360 * 181);
      for (const [lon, lat, v] of j.coordinates) node[(lat + 90) * 360 + (((lon % 360) + 360) % 360)] = v;
      const px = new Uint8Array(360 * 180);
      for (let r = 0; r < 180; r++) {                 // canonical row r: centre latitude 89.5 - r
        const latLo = 89 - r;                          // nodes at latLo and latLo + 1 bracket the cell
        for (let c = 0; c < 360; c++) {                // canonical column c: centre longitude -179.5 + c
          const l0 = ((c - 180) % 360 + 360) % 360, l1 = (l0 + 1) % 360;     // bracketing node longitudes, in 0..359
          const a = (latLo + 90) * 360, b = (latLo + 91) * 360;
          px[r * 360 + c] = Math.min(255, (node[a + l0] + node[a + l1] + node[b + l0] + node[b + l1]) / 4 * 2.55);
        }
      }
      if (this.auroraTex) this.gl.deleteTexture(this.auroraTex);
      this.auroraTex = texFromData(this.gl, 360, 180, px, { format: 'r', mips: false });
      this.fields.tex.aurora = this.auroraTex; this.fields.has.aurora = true;
      this.auroraTime = Date.parse(j['Forecast Time']);
      this._set('aurora', 'ready', `NOAA OVATION nowcast for ${j['Forecast Time'].slice(0, 16).replace('T', ' ')} UTC`);
    } catch (e) { this.fields.has.aurora = false; this._set('aurora', 'unavailable', 'The NOAA space-weather feed could not be reached.'); }
  }

  /** The VIIRS true-colour mosaic for a UTC date. Only past dates have one. */
  async loadToday(tMs) {
    const date = new Date(tMs).toISOString().slice(0, 10);
    if (date === this.todayDate && this.status.today !== 'idle') return;
    this.todayDate = date;
    const ageDays = (Date.now() - Date.parse(date + 'T12:00:00Z')) / DAY;
    this.fields.has.live = false;
    if (ageDays < 0.9) { this._set('today', 'none', `No observation exists yet for ${date}. Imagery arrives about a day behind; the future has none.`); return; }
    if (date < '2018-01-05') { this._set('today', 'none', 'This layer’s satellite record starts in January 2018.'); return; }
    this._set('today', 'loading', `Fetching the mosaic for ${date}…`);
    try {
      const url = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=VIIRS_NOAA20_CorrectedReflectance_TrueColor'
        + `&STYLES=&FORMAT=image/jpeg&WIDTH=4096&HEIGHT=2048&CRS=EPSG:4326&BBOX=-90,-180,90,180&TIME=${date}`;
      const b = await loadBitmap(url);
      if (date !== this.todayDate) { b.close(); return; }            // the clock moved on while this was in flight
      if (this.todayTex) this.gl.deleteTexture(this.todayTex);
      this.todayTex = texFromImage(this.gl, b, { format: 'rgb' }); b.close();
      this.fields.tex.live = this.todayTex; this.fields.has.live = true;
      this._set('today', 'ready', `NASA VIIRS (NOAA-20), daytime passes of ${date}`);
    } catch (e) { this._set('today', 'unavailable', 'NASA GIBS could not be reached.'); }
  }

  async loadSats() {
    if (this.status.sats === 'loading' || this.sats) return;
    this._set('sats', 'loading');
    try {
      if (!window.satellite) await new Promise((res, rej) => { const s = document.createElement('script'); s.src = 'js/vendor/satellite.min.js'; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
      const groups = [['stations', 'station'], ['gps-ops', 'navigation'], ['visual', 'bright']];
      const seen = new Set(), list = [];
      for (const [g, kind] of groups) {
        const txt = await (await fetch(`https://celestrak.org/NORAD/elements/gp.php?GROUP=${g}&FORMAT=tle`)).text();
        const lines = txt.split(/\r?\n/).filter((l) => l.trim());
        for (let i = 0; i + 2 < lines.length + 1; i += 3) {
          if (!lines[i + 2]) break;
          const id = lines[i + 1].slice(2, 7);
          if (seen.has(id)) continue; seen.add(id);
          const rec = window.satellite.twoline2satrec(lines[i + 1], lines[i + 2]);
          const epoch = (rec.jdsatepoch - 2440587.5) * DAY;
          list.push({ name: lines[i].trim(), kind, rec, epoch });
        }
      }
      this.sats = list;
      const ep = list.map((s) => s.epoch).sort((a, b) => a - b)[Math.floor(list.length / 2)];
      this.satEpoch = ep;
      this._set('sats', 'ready', `${list.length} objects; CelesTrak elements of ${new Date(ep).toISOString().slice(0, 10)}`);
    } catch (e) { this._set('sats', 'unavailable', 'CelesTrak could not be reached.'); }
  }

  /** Sub-satellite points at t: [{name, kind, lon, lat, h (Earth radii), km}] */
  satPositions(tMs) {
    if (!this.sats) return [];
    const sat = window.satellite, d = new Date(tMs), g = sat.gstime(d), out = [];
    for (const s of this.sats) {
      const pv = sat.propagate(s.rec, d);
      if (!pv.position || Number.isNaN(pv.position.x)) continue;
      const geo = sat.eciToGeodetic(pv.position, g);
      let lon = geo.longitude * 180 / Math.PI; lon = ((lon + 540) % 360) - 180;
      out.push({ name: s.name, kind: s.kind, lon, lat: geo.latitude * 180 / Math.PI, h: geo.height / 6371.0088, km: geo.height });
    }
    return out;
  }
}
export { HOUR, DAY };
