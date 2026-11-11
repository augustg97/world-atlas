// The interface: brand and clock, systems panel, time console, legend, card panel, dashboard,
// search and About. All of it is generated from js/catalog.js.

import { SYSTEMS, TIERS, LAYERS, LENS_DEFS, paletteCss } from './catalog.js';
import { coord } from './cards.js';
import { seasonName } from './astro.js';

const $ = (sel, root = document) => root.querySelector(sel);
const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstChild; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const SPEEDS = [
  { id: 'real', label: 'Real time', rate: 1 }, { id: 'm1', label: '1 minute / s', rate: 60 }, { id: 'm10', label: '10 minutes / s', rate: 600 },
  { id: 'h1', label: '1 hour / s', rate: 3600 }, { id: 'd1', label: '1 day / s · same hour', days: 1 }, { id: 'w1', label: '1 week / s · same hour', days: 7 },
  { id: 'mo1', label: '1 month / s · same hour', days: 30 },
];

export class UI {
  constructor(app) {
    this.app = app;
    const root = $('#ui');
    root.innerHTML = `
      <header id="top">
        <div class="brand"><div class="brand-t">THE WORLD</div><div class="brand-s">a living atlas</div></div>
        <div class="clock" id="clock"><div class="clock-time"><span id="ck-time">--:--</span><span class="utc">UTC</span></div>
          <div class="clock-date" id="ck-date"></div><div class="clock-mode" id="ck-mode"></div></div>
        <div class="spacer"></div>
        <div class="seg" id="seg-view"><button data-v="globe">Globe</button><button data-v="sheet">Sheet</button></div>
        <div class="seg" id="seg-style"><button data-v="space">Space</button><button data-v="atlas">Atlas</button></div>
        <div class="search"><input id="search" type="search" placeholder="Find a place…" autocomplete="off" spellcheck="false"><div id="results" hidden></div></div>
        <button class="ghost" id="btn-about" title="About, sources and limits">About</button>
      </header>
      <aside id="left"><div class="panel-h"><span>Systems</span><button class="ghost sm" id="left-toggle" title="Hide panel">‹</button></div><div id="systems"></div></aside>
      <button class="ghost reopen" id="left-open" hidden title="Show systems">Systems ›</button>
      <aside id="right"><div id="card" hidden></div><div id="dash"></div></aside>
      <div id="legend" hidden></div>
      <div id="hud"><div id="scale"><div id="scale-bar"></div><span id="scale-txt"></span></div><div id="cursor"></div><div id="detail"></div><div id="credit"></div></div>
      <footer id="time">
        <div class="tc-buttons">
          <button id="btn-now" class="pill" title="Return to the present moment">● Now</button>
          <button id="btn-play" class="pill" title="Play or pause (space)">Pause</button>
          <select id="speed">${SPEEDS.map((s) => `<option value="${s.id}">${s.label}</option>`).join('')}</select>
        </div>
        <div class="tc-sliders">
          <div class="tc-row"><label>Year</label><div class="track"><input id="sl-year" type="range" min="0" max="365" step="1"><div class="ticks" id="tk-year"></div></div><output id="out-year"></output></div>
          <div class="tc-row"><label>Day</label><div class="track"><input id="sl-day" type="range" min="0" max="1439" step="1"><div class="ticks" id="tk-day"></div></div><output id="out-day"></output></div>
        </div>
      </footer>
      <div id="about" hidden></div>`;
    this._buildSystems();
    this._buildTicks();
    this._bind();
  }

  _buildSystems() {
    const host = $('#systems');
    host.innerHTML = SYSTEMS.map((s) => `
      <section class="sys" data-sys="${s.id}">
        <button class="sys-h"><span class="sys-name">${s.name}</span><span class="sys-count" data-count="${s.id}"></span><span class="chev">▾</span></button>
        <div class="sys-b"><p class="blurb">${esc(s.blurb)}</p>
          ${s.layers.map((l) => `<div class="layer" data-layer="${l.id}"><label class="sw"><input type="checkbox" data-layer="${l.id}"><i></i></label>
            <button class="lname" data-info="layer:${l.id}">${esc(l.name)}</button><span class="tier tier-${l.tier}" title="${esc(TIERS[l.tier].title)}">${TIERS[l.tier].label}</span><div class="lstat" data-stat="${l.id}"></div></div>`).join('')}
          ${s.note ? `<p class="blurb dim">${esc(s.note)}</p>` : ''}
          ${s.lenses.length ? `<div class="lens-h">Lens</div><div class="lenses">${s.lenses.map((l) => `<button class="lens" data-lens="${l.id}" title="${esc(l.what)}">${esc(l.name)}</button>`).join('')}</div>` : ''}
        </div>
      </section>`).join('');
  }

  _buildTicks() {
    const y = new Date().getUTCFullYear();
    const start = Date.UTC(y, 0, 1), len = (Date.UTC(y + 1, 0, 1) - start) / 86400000;
    $('#tk-year').innerHTML = MONTHS.map((m, i) => `<span style="left:${((Date.UTC(y, i, 1) - start) / 86400000 / len * 100).toFixed(2)}%">${m}</span>`).join('')
      + [[2, 20, 'equinox'], [5, 21, 'solstice'], [8, 22, 'equinox'], [11, 21, 'solstice']].map(([m, d, n]) => `<b title="${n}" style="left:${((Date.UTC(y, m, d) - start) / 86400000 / len * 100).toFixed(2)}%"></b>`).join('');
    $('#tk-day').innerHTML = [0, 3, 6, 9, 12, 15, 18, 21].map((h) => `<span style="left:${(h / 24 * 100).toFixed(2)}%">${String(h).padStart(2, '0')}</span>`).join('');
  }

  _bind() {
    const app = this.app;
    $('#systems').addEventListener('click', (e) => {
      const h = e.target.closest('.sys-h'); if (h) { h.parentElement.classList.toggle('closed'); return; }
      const lens = e.target.closest('[data-lens]'); if (lens) { app.setLens(app.state.lens === lens.dataset.lens ? 'none' : lens.dataset.lens); return; }
      const info = e.target.closest('[data-info]'); if (info) { const [k, id] = info.dataset.info.split(':'); app.openLayerCard(id, k === 'lens'); }
    });
    $('#systems').addEventListener('change', (e) => { const c = e.target.closest('input[data-layer]'); if (c) app.setLayer(c.dataset.layer, c.checked); });
    $('#seg-view').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) app.setView(b.dataset.v); });
    $('#seg-style').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) app.setStyle(b.dataset.v); });
    $('#btn-now').addEventListener('click', () => app.goLive());
    $('#btn-play').addEventListener('click', () => app.togglePlay());
    $('#speed').addEventListener('change', (e) => app.setSpeed(e.target.value));
    const yr = $('#sl-year'), dy = $('#sl-day');
    const fromSliders = () => {
      const d = new Date(app.state.t), y = d.getUTCFullYear();
      app.setTime(Date.UTC(y, 0, 1) + (+yr.value) * 86400000 + (+dy.value) * 60000);
    };
    yr.addEventListener('input', fromSliders); dy.addEventListener('input', fromSliders);
    $('#left-toggle').addEventListener('click', () => { $('#left').hidden = true; $('#left-open').hidden = false; document.body.classList.add('left-closed'); });
    $('#left-open').addEventListener('click', () => { $('#left').hidden = false; $('#left-open').hidden = true; document.body.classList.remove('left-closed'); });
    $('#btn-about').addEventListener('click', () => this.showAbout());
    $('#card').addEventListener('click', (e) => {
      if (e.target.closest('.card-x')) { app.closeCard(); return; }
      const o = e.target.closest('[data-open]'); if (o) app.openRef(o.dataset.open);
      if (e.target.closest('.card-go')) app.flyToSelection();
    });
    const s = $('#search'), res = $('#results');
    let hits = [];
    const render = () => { res.hidden = !hits.length; res.innerHTML = hits.map((h, i) => `<button data-i="${i}"><b>${esc(h.label)}</b><span>${esc(h.sub || '')}</span></button>`).join(''); };
    s.addEventListener('input', () => { hits = app.search(s.value); render(); });
    s.addEventListener('keydown', (e) => { if (e.key === 'Enter' && hits[0]) { app.pick(hits[0]); hits = []; render(); s.blur(); } if (e.key === 'Escape') { hits = []; render(); s.blur(); } e.stopPropagation(); });
    res.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { app.pick(hits[+b.dataset.i]); hits = []; render(); s.value = ''; } });
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input, select, textarea')) return;
      if (e.key === ' ') { e.preventDefault(); app.togglePlay(); }
      else if (e.key === 'n') app.goLive();
      else if (e.key === 'g') app.setView(app.cam.view === 'globe' ? 'sheet' : 'globe');
      else if (e.key === 'a') app.setStyle(app.state.style === 'atlas' ? 'space' : 'atlas');
      else if (e.key === 'Escape') { app.closeCard(); $('#about').hidden = true; }
      else if (e.key === '/') { e.preventDefault(); s.focus(); }
    });
  }

  // ------------------------------------------------------------------------------- updates
  syncControls() {
    const st = this.app.state;
    document.body.dataset.style = st.style;
    for (const c of document.querySelectorAll('input[data-layer]')) c.checked = !!st.layers[c.dataset.layer];
    for (const b of document.querySelectorAll('[data-lens]')) b.classList.toggle('on', b.dataset.lens === st.lens);
    for (const b of document.querySelectorAll('#seg-view button')) b.classList.toggle('on', b.dataset.v === this.app.cam.view);
    for (const b of document.querySelectorAll('#seg-style button')) b.classList.toggle('on', b.dataset.v === st.style);
    for (const s of SYSTEMS) {
      const n = s.layers.filter((l) => st.layers[l.id]).length + (s.lenses.some((l) => l.id === st.lens) ? 1 : 0);
      $(`[data-count="${s.id}"]`).textContent = n ? String(n) : '';
    }
    $('#speed').value = st.speed;
    this.legend();
  }

  clock() {
    const st = this.app.state, d = new Date(st.t);
    $('#ck-time').textContent = d.toISOString().slice(11, 16);
    $('#ck-date').textContent = d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
    const mode = $('#ck-mode');
    if (st.clock === 'live') { mode.className = 'clock-mode live'; mode.textContent = '● NOW · live feeds on'; }
    else { mode.className = 'clock-mode typical'; mode.textContent = 'TYPICAL YEAR · climatology, not this date’s weather'; }
    $('#btn-now').classList.toggle('on', st.clock === 'live');
    $('#btn-play').textContent = st.clock === 'paused' ? 'Play' : 'Pause';
    const y = d.getUTCFullYear(), doy = Math.floor((st.t - Date.UTC(y, 0, 1)) / 86400000), mins = d.getUTCHours() * 60 + d.getUTCMinutes();
    if (document.activeElement !== $('#sl-year')) $('#sl-year').value = doy;
    if (document.activeElement !== $('#sl-day')) $('#sl-day').value = mins;
    $('#out-year').textContent = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
    $('#out-day').textContent = d.toISOString().slice(11, 16);
  }

  legend() {
    const st = this.app.state, host = $('#legend'), l = LENS_DEFS[st.lens];
    if (!l) { host.hidden = true; return; }
    let ticks = l.ticks;
    if (typeof ticks === 'string') {                      // "log:<field>:v1,v2,..." - positions come from the field's own encoding
      const [, field, vals] = ticks.split(':');
      const m = this.app.fields.meta.human && this.app.fields.meta.human[field];
      ticks = m ? vals.split(',').map((v) => [Math.log1p(+v / m.x0) / Math.log1p(m.xmax / m.x0), (+v).toLocaleString('en-US')]) : [];
    }
    host.hidden = false;
    host.innerHTML = `<div class="lg-h"><button class="lname" data-info="lens:${l.id}">${esc(l.name)}</button>${l.units ? `<span class="units">${esc(l.units)}</span>` : ''}<span class="tier tier-${l.tier}">${TIERS[l.tier].label}</span><button class="ghost sm lg-x" title="Remove lens">×</button></div>
      <div class="lg-bar" style="background:${paletteCss(l.palette)}"></div><div class="lg-ticks">${ticks.map(([t, s]) => `<span style="left:${(t * 100).toFixed(1)}%">${esc(s)}</span>`).join('')}</div>`;
    host.querySelector('.lg-x').onclick = () => this.app.setLens('none');
    host.querySelector('[data-info]').onclick = () => this.app.openLayerCard(l.id, true);
  }

  hud(kmPerPx, cursor, detail, credit = null) {
    const target = 110 * kmPerPx;
    const pow = Math.pow(10, Math.floor(Math.log10(target)));
    const nice = [1, 2, 5, 10].map((m) => m * pow).filter((v) => v <= target * 1.15).pop() || pow;
    $('#scale-bar').style.width = `${(nice / kmPerPx).toFixed(1)}px`;
    const dist = nice >= 1 ? `${nice.toLocaleString('en-US')} km` : `${Math.round(nice * 1000)} m`;
    $('#scale-txt').textContent = `${dist} · ${kmPerPx >= 10 ? kmPerPx.toFixed(0) + ' km' : kmPerPx >= 0.95 ? kmPerPx.toFixed(1) + ' km' : Math.round(kmPerPx * 1000) + ' m'}/px`;
    $('#cursor').textContent = cursor || '';
    $('#detail').textContent = detail || '';
    // a source that asks to be named on the map itself, while its pictures are on it (Sentinel-2 cloudless, EOX)
    const cr = $('#credit'), key = credit ? credit.credit : '';
    if (cr.dataset.k !== key) {
      cr.dataset.k = key; cr.textContent = '';
      if (credit) { const a = document.createElement('a'); a.href = credit.link; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = credit.credit; cr.append('Imagery: ', a, ', CC BY 4.0'); }
    }
  }

  layerStatus(id, text, cls = '') { const n = $(`[data-stat="${id}"]`); if (n) { n.textContent = text || ''; n.className = 'lstat ' + cls; } }

  showCard(card) {
    const host = $('#card');
    if (!card) { host.hidden = true; host.innerHTML = ''; return; }
    host.hidden = false;
    host.innerHTML = `<div class="card-bar">${card.lon !== undefined ? '<button class="ghost sm card-go" title="Centre the view here">Centre</button>' : '<span></span>'}<button class="ghost sm card-x" title="Close (Esc)">×</button></div><div class="card-body">${card.html}</div>`;
    host.scrollTop = 0;
  }

  dashboard(d) {
    const row = (k, v, tier, sub) => `<div class="drow"><span class="k">${k}</span><span class="v">${v}${sub ? `<small>${sub}</small>` : ''}</span><span class="tier tier-${tier}">${TIERS[tier].label}</span></div>`;
    const b = (n) => (n / 1e9).toFixed(2) + ' bn';
    const bar = d.people ? `<div class="pbar" title="People in daylight, twilight and night"><i class="day" style="width:${(d.people.day / d.people.total * 100).toFixed(1)}%"></i><i class="twi" style="width:${(d.people.twilight / d.people.total * 100).toFixed(1)}%"></i><i class="night" style="width:${(d.people.night / d.people.total * 100).toFixed(1)}%"></i></div>` : '';
    $('#dash').innerHTML = `<div class="panel-h"><span>Planet now</span><small>${new Date(this.app.state.t).toISOString().slice(0, 16).replace('T', ' ')} UTC</small></div>
      <div class="dsec"><div class="sec-h">Sun & Moon</div>
        ${row('Sun overhead at', coord(d.sun.lon, d.sun.lat), 'modelled', d.sunPlace ? `near ${esc(d.sunPlace)}` : '')}
        ${row('Season', `${d.season[0]}`, 'modelled', d.season[1])}
        ${row('Moon', `${d.moon.name} · ${(d.moon.lit * 100).toFixed(0)}% lit`, 'modelled')}</div>
      <div class="dsec"><div class="sec-h">People</div>${bar}
        ${d.people ? row('In daylight', b(d.people.day), 'modelled', `${b(d.people.twilight)} in twilight · ${b(d.people.night)} in the dark`) : row('In daylight', 'loading…', 'modelled')}
        ${d.people ? row('Awake hours (07–23)', b(d.people.awake), 'modelled', 'by local solar time') : ''}
        ${Number.isFinite(d.aloft) ? row('Aircraft aloft', d.aloft.toLocaleString('en-US'), 'modelled', 'gravity model, not a count') : ''}
        ${d.co2 ? row('Fossil CO₂ this year', `${(d.co2.soFar / 1e9).toFixed(2)} Gt`, 'static', `at the 2022 rate of ${Math.round(d.co2.perSec).toLocaleString('en-US')} t/s`) : ''}</div>
      <div class="dsec"><div class="sec-h">Air & sea</div>
        ${Number.isFinite(d.meanT) ? row('Mean surface air temp.', `${d.meanT.toFixed(1)} °C`, 'climatology', '1991–2020 for this date') : ''}
        ${d.ice ? row('Arctic sea ice', `${d.ice.n.toFixed(1)} M km²`, 'climatology', 'extent, ≥15% cover; NSIDC 1991–2020 mean') + row('Antarctic sea ice', `${d.ice.s.toFixed(1)} M km²`, 'climatology', 'extent, ≥15% cover; lake ice not counted') : ''}</div>
      <div class="dsec"><div class="sec-h">Ground</div>
        ${d.quakes ? row('Earthquakes M≥4.5', `${d.quakes.day} in 24 h · ${d.quakes.week} in 7 days`, 'live', d.quakes.top ? `largest this week: M${d.quakes.top[4].toFixed(1)} ${esc(d.quakes.top[5])}` : '') : row('Earthquakes', d.quakeNote || 'shown only at the present', 'live')}</div>`;
  }

  showAbout() {
    const host = $('#about'), k = this.app.earth.relief || { land: 0, sea: 0 };
    host.hidden = false;
    const sources = [...new Set(SYSTEMS.flatMap((s) => [...s.layers, ...s.lenses].map((l) => l.source)))];
    host.innerHTML = `<div class="about-box"><button class="ghost sm about-x">×</button>
      <h1>The World <small>a living atlas</small></h1>
      <p class="lead">The Earth is one coupled machine. Sunlight drives the air and the water; life follows the water; people follow both. This atlas renders one year of the planet, entered at the present moment, so that you can point at any place and ask what the Sun, the air, the sea, the ground and the people are doing there now.</p>
      <h3>What you are looking at</h3>
      <p>Every pixel is a place. Nothing on screen is a finished picture of the Earth: the surface is composed at each pixel from measured fields (twelve months of land reflectance, elevation, a water mask, night lights, climatologies of the air and sea) and lit by the Sun from where the Sun actually is. Click anywhere to read the fields at that point.</p>
      <h3>How much to believe</h3>
      <div class="tiers">${Object.entries(TIERS).map(([k2, t]) => `<div><span class="tier tier-${k2}">${t.label}</span> ${esc(t.title)}.</div>`).join('')}</div>
      <p>The record this atlas holds stops at <b>now</b>. It carries no weather history and no forecast. Move the clock and the live layers switch off; what remains is a typical year, and the clock says so. The clouds are real cloud shapes carried by a mean wind: right from orbit, wrong about any particular town on any particular day.</p>
      <h3>Stated choices</h3>
      <ul><li>Borders follow who administers the ground (Natural Earth’s de facto worldview). Disputed lines are dashed and contested ground is hatched in the Atlas style; each dispute has a card.</li>
      <li>Relief is shaded from the elevation field with a vertical exaggeration of <b>${k.land.toFixed(1)}×</b> on land at this zoom${k.sea ? ` and <b>${k.sea.toFixed(1)}×</b> on the sea floor` : ''}. From orbit real slopes would be invisible without it.</li>
      <li>Cloud shadows and aircraft are drawn with exaggerated height. Cloud drift is sped up 2.5× so that it reads at the scale of the globe.</li>
      <li>Brightness, colour and the limb of the Space style are set against NASA EPIC full-disc photographs taken from the same place at the same instant. The exposure is fitted to cloud tops and clear ocean, whose reflectance is known independently; the ground’s albedo is Blue Marble re-read against a cloud-free composite of about a hundred EPIC frames. Ocean, desert, vegetated land and the brightness of cloud now land within a few display levels of the photographs. Where the clouds are is not compared at all: that is a typical year against one day.</li>
      <li>Air traffic and ship motion are modelled flows, not tracked vehicles. Live positions are licence-restricted and are not used.</li>
      <li>Latitude is treated as spherical on a 6371 km sphere; the error is below a pixel at every scale offered.</li></ul>
      <h3>What this page asks the network for</h3>
      <p>Closer in than 5 km a pixel, with <i>Finer ground, close in</i> switched on (it is by default), the page fetches map tiles for the part of the Earth on screen from three hosts: imagery, night lights and a water mask from NASA (gibs.earthdata.nasa.gov), elevation from Amazon Web Services (s3.amazonaws.com), and, closer in than about 0.6 km a pixel, Sentinel-2 imagery from EOX in Vienna (tiles.maps.eox.at). Those requests tell the hosts roughly where you are looking, as any tiled map does. Nothing else about you is sent, and with the layer off none of them is asked for anything. The live layers (earthquakes, aurora, satellites, today’s Earth) fetch whole-Earth files that say nothing about where you look.</p>
      <div id="updlog"></div>
      <h3>Sources</h3><ul class="srcs">${sources.map((s) => `<li>${esc(s)}</li>`).join('')}<li>Country statistics: World Bank Open Data, CC BY 4.0.</li>
      <li>Where the sea, the land and the lakes are: Natural Earth 5.1.2, 1:10m land, minor islands and lakes (public domain); Antarctica’s ice front from Blue Marble. The wide rivers, and the lakes strung along them: NASA’s MODIS land-water mask (MOD44W), along Natural Earth’s 1:10m river lines. The colour of shallow and silty water is Blue Marble’s own.</li>
      <li>We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).</li>
      <li>The ground closer in than about 0.6 km a pixel: <a href="https://s2maps.eu" target="_blank" rel="noopener noreferrer">Sentinel-2 cloudless</a> by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2016), CC BY 4.0, fetched as tiles while you look. It is named on the map whenever it is on screen.</li>
      <li>Terrain Tiles (Mapzen, a Linux Foundation project; Registry of Open Data on AWS), used closer in than 5 km a pixel: ArcticDEM terrain data DEM(s) were created from DigitalGlobe, Inc., imagery and funded under National Science Foundation awards 1043681, 1559691, and 1542736; Australia terrain data © Commonwealth of Australia (Geoscience Australia) 2017; Austria terrain data © offene Daten Österreichs – Digitales Geländemodell (DGM) Österreich; Canada terrain data contains information licensed under the Open Government Licence – Canada; Europe terrain data produced using Copernicus data and information funded by the European Union - EU-DEM layers; Global ETOPO1 terrain data U.S. National Oceanic and Atmospheric Administration; Mexico terrain data source: INEGI, Continental relief, 2016; New Zealand terrain data Copyright 2011 Crown copyright (c) Land Information New Zealand and the New Zealand Government (All rights reserved); Norway terrain data © Kartverket; United Kingdom terrain data © Environment Agency copyright and/or database right 2015. All rights reserved; United States 3DEP (formerly NED) and global GMTED2010 and SRTM terrain data courtesy of the U.S. Geological Survey.</li><li>Reference for layout and coverage (not reproduced): National Geographic, <i>The World — Political</i>.</li></ul>
      <p class="dim">Keys: space play/pause · N now · G globe/sheet · A atlas/space · / search · Esc close.</p></div>`;
    host.onclick = (e) => { if (e.target === host || e.target.closest('.about-x')) host.hidden = true; };
    // what changed, release by release: data, so a returning reader can see it (data/updatelog.json)
    fetch('data/updatelog.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : [])).then((log) => {
      const el = $('#updlog');
      if (!el || !log.length) return;
      el.innerHTML = '<h3>What changed</h3>' + log.map((v) => `<p><b>${esc(v.version)} · ${esc(v.date)} · ${esc(v.title)}</b><br>${esc(v.summary)}</p>` +
        v.sections.map((sec) => `<p class="dim">${esc(sec.name)}</p><ul>${sec.items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>`).join('')).join('');
    }).catch(() => {});
  }
}
