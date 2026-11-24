// The interface: brand and clock, systems panel, time console, legend, card panel, dashboard,
// search and About. All of it is generated from js/catalog.js.

import { SYSTEMS, TIERS, LENS_DEFS, LENS_NOTES, paletteCss, CARD_TEXT_SOURCE } from './catalog.js';
import { coord } from './cards.js';
import { mountDescription } from './wiki.js';
import { STORIES, STORY_BY_ID } from './stories.js';
import { CITY_EXAMPLES } from './cities.js';

const $ = (sel, root = document) => root.querySelector(sel);
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
    this.narrow = matchMedia('(max-width: 860px)');
    this.leftPanel = 'layers';
    this.desktopPlanet = true;
    this.mobilePanel = null;
    this.inspector = null;
    const modes = `<div class="seg view-mode" role="group" aria-label="Map projection"><button data-v="globe">Globe</button><button data-v="sheet">Sheet</button></div>
      <div class="seg view-mode" role="group" aria-label="Map appearance"><button data-s="space">Space</button><button data-s="atlas">Atlas</button></div>`;
    const nav = (id, label, icon, controls) => `<button class="nav-item" data-panel="${id}" aria-controls="${controls}" aria-expanded="false"><i class="nav-icon ${icon}" aria-hidden="true"></i><span>${label}</span></button>`;
    const storiesNav = nav('stories', 'Guided Views', 'icon-stories', 'left');
    const layersNav = nav('layers', 'Systems', 'icon-layers', 'left');
    const planetNav = nav('planet', 'Planet', 'icon-planet', 'dash');
    const close = (panel) => `<button class="ghost icon-button" data-close="${panel}" aria-label="Close panel">×</button>`;
    $('#ui').innerHTML = `
      <header id="top">
        <div class="brand"><span class="brand-mark" aria-hidden="true"></span><div><div class="brand-t">The World</div><div class="brand-s">A living atlas</div></div></div>
        <nav class="desktop-nav" aria-label="Explore the atlas">${storiesNav}${layersNav}${planetNav}</nav>
        <div class="spacer"></div>
        <div class="desktop-modes">${modes}</div>
        <div class="search" id="search-panel">
          <div class="panel-h mobile-only"><h2>Find a place</h2>${close('search')}</div>
          <label class="search-field"><i class="nav-icon icon-search" aria-hidden="true"></i><input id="search" type="search" aria-label="Find a place" placeholder="Find a place…" autocomplete="off" spellcheck="false"><kbd>/</kbd></label>
          <div id="results" hidden></div>
        </div>
        <div class="clock" id="clock"><div class="clock-time"><span id="ck-time">--:--</span><span class="utc">UTC</span></div>
          <div class="clock-date" id="ck-date"></div><div class="clock-mode" id="ck-mode"></div></div>
        <button class="ghost icon-button" id="btn-about" aria-label="About, sources and limits" title="About, sources and limits">i</button>
      </header>
      <aside id="left" aria-label="Explore">
        <section id="story-panel" class="side-content">
          <div class="panel-h"><h2>Guided Views</h2>${close('stories')}</div>
          <div class="side-scroll"><div id="story-now" hidden></div>
          <section class="city-presets"><h3>3D cities</h3><div>${CITY_EXAMPLES.map((city, i) => `<button class="ghost" data-city="${i}">${city.name}</button>`).join('')}</div>
            <p>Search for any city to explore its mapped buildings in 3D.</p></section>
          <div class="story-list">${STORIES.map((story) => `
            <button class="story-tile story-${story.id}" data-story="${story.id}" aria-pressed="false">
              <span class="story-copy"><span class="story-subject">${story.subject}</span><strong>${story.title}</strong><span class="story-summary">${story.summary}</span></span>
            </button>`).join('')}</div></div>
        </section>
        <section id="layer-panel" class="side-content" hidden>
          <div class="panel-h"><h2>Systems</h2>${close('layers')}</div>
          <div class="mobile-modes">${modes}</div>
          <div id="systems"></div>
        </section>
      </aside>
      <section id="spotlight" aria-label="Planet summary">
        <div class="section-label" id="spot-kicker">Planet now</div>
        <div id="spot-metric"></div>
        <button class="ghost spot-play" id="spot-rotation" data-action="rotation" hidden>Play one rotation</button>
        <button class="ghost spot-details" data-panel="planet" aria-controls="dash" aria-expanded="false">Planet details</button>
      </section>
      <aside id="right" aria-label="Map details">
        <section id="card" aria-label="Place details" hidden></section>
        <section id="compare" aria-label="Compare places" hidden>
          <div class="panel-h"><h2>Compare places</h2>${close('compare')}</div>
          <div id="compare-pins"></div><div id="compare-data"></div>
        </section>
        <section id="dash" aria-label="Planet details" hidden>
          <div class="panel-h"><h2 id="dash-title">Planet now</h2>${close('planet')}</div><div id="dash-feature" hidden></div><div id="dash-content"></div>
        </section>
      </aside>
      <section id="legend" aria-label="Map legend" hidden></section>
      <div id="hud"><div id="scale"><div id="scale-bar"></div><span id="scale-txt"></span></div><div id="cursor"></div><div id="detail"></div><div id="credit"></div></div>
      <section id="city-controls" aria-label="City view controls" hidden>
        <div class="city-row"><span><strong>3D buildings</strong> <span class="tier tier-modelled">MODELLED</span></span><button id="city-close" class="ghost">Exit 3D</button></div>
        <div class="city-row">
          <button id="city-left" class="ghost icon-button" aria-label="Rotate city left" title="Rotate city left">↶</button>
          <label for="city-pitch">Tilt</label><input id="city-pitch" type="range" min="0" max="58" value="52">
          <output id="city-angle" for="city-pitch">52°</output>
          <button id="city-right" class="ghost icon-button" aria-label="Rotate city right" title="Rotate city right">↷</button>
        </div>
        <div id="city-status" role="status"></div>
        <p>OpenStreetMap footprints via OpenFreeMap. Tile heights may be estimated. Missing heights use 7 m.</p>
        <button id="city-retry" class="ghost" hidden>Retry building tiles</button>
      </section>
      <div id="map-tools" role="group" aria-label="Map controls">
        <button class="ghost icon-button" id="zoom-in" aria-label="Zoom in" title="Zoom in">+</button>
        <button class="ghost icon-button" id="zoom-out" aria-label="Zoom out" title="Zoom out">−</button>
        <button class="ghost icon-button" id="map-home" aria-label="Fit Earth in view" title="Fit Earth in view"><i class="nav-icon icon-target" aria-hidden="true"></i></button>
        <button class="ghost" id="city-open" aria-pressed="false" title="Show 3D buildings here" hidden>3D</button>
        <button class="ghost" id="compare-open" data-panel="compare" aria-controls="compare" aria-expanded="false" hidden>Compare</button>
      </div>
      <footer id="time" aria-label="Time controls">
        <div class="panel-h mobile-only"><h2>Time</h2>${close('time')}</div>
        <div class="tc-buttons">
          <button id="btn-play" class="pill" title="Play or pause (space)">Pause</button>
          <button id="btn-now" class="pill" title="Return to the present moment">Now</button>
          <select id="speed" aria-label="Playback speed">${SPEEDS.map((s) => `<option value="${s.id}">${s.label}</option>`).join('')}</select>
        </div>
        <div class="tc-sliders">
          <div class="tc-row"><label for="sl-year">Year</label><div class="track"><input id="sl-year" type="range" min="0" max="365" step="1"><div class="ticks" id="tk-year" aria-hidden="true"></div></div><output id="out-year" for="sl-year"></output></div>
          <div class="tc-row"><label for="sl-day">Day</label><div class="track"><input id="sl-day" type="range" min="0" max="1439" step="1"><div class="ticks" id="tk-day" aria-hidden="true"></div></div><output id="out-day" for="sl-day"></output></div>
        </div>
      </footer>
      <nav id="mobile-nav" aria-label="Explore the atlas">${storiesNav}${layersNav}${nav('time', 'Time', 'icon-time', 'time')}${nav('search', 'Search', 'icon-search', 'search-panel')}${planetNav}</nav>
      <div id="about" hidden></div>`;
    this._buildSystems();
    this._bind();
    this.syncPanels();
  }

  _buildSystems() {
    const host = $('#systems');
    host.innerHTML = SYSTEMS.map((s) => `
      <section class="sys" data-sys="${s.id}">
        <button class="sys-h" aria-expanded="true" aria-controls="system-${s.id}"><span class="sys-name">${s.name}</span><span class="sys-count" data-count="${s.id}" aria-hidden="true"></span><span class="chev" aria-hidden="true">▾</span></button>
        <div class="sys-b" id="system-${s.id}"><p class="blurb">${esc(s.blurb)}</p>
          ${s.layers.map((l) => `<div class="layer" data-layer="${l.id}"><label class="sw"><input type="checkbox" data-layer="${l.id}" aria-label="${esc(l.name)}"><i></i></label>
            <button class="lname" data-info="layer:${l.id}">${esc(l.name)}</button><span class="tier tier-${l.tier}" title="${esc(TIERS[l.tier].title)}">${TIERS[l.tier].label}</span><div class="lstat" data-stat="${l.id}"></div></div>`).join('')}
          ${s.note ? `<p class="blurb dim">${esc(s.note)}</p>` : ''}
          ${s.lenses.length ? `<div class="lens-h">Lens</div><div class="lenses">${s.lenses.map((l) => `<button class="lens" data-lens="${l.id}" title="${esc(l.what)}">${esc(l.name)}</button>`).join('')}</div>` : ''}
        </div>
      </section>`).join('');
  }

  _buildTicks(y) {
    this.tickYear = y;
    const start = Date.UTC(y, 0, 1), len = (Date.UTC(y + 1, 0, 1) - start) / 86400000;
    $('#tk-year').innerHTML = MONTHS.map((m, i) => `<span class="${i % 3 === 0 ? 'quarter' : ''}" style="left:${((Date.UTC(y, i, 1) - start) / 86400000 / len * 100).toFixed(2)}%">${m}</span>`).join('')
      + [[2, 20], [5, 21], [8, 22], [11, 21]].map(([m, d]) => `<b style="left:${((Date.UTC(y, m, d) - start) / 86400000 / len * 100).toFixed(2)}%"></b>`).join('');
    $('#tk-day').innerHTML = [0, 3, 6, 9, 12, 15, 18, 21].map((h) => `<span class="${h % 6 === 0 ? 'quarter' : ''}" style="left:${(h / 24 * 100).toFixed(2)}%">${String(h).padStart(2, '0')}</span>`).join('');
  }

  _bind() {
    const app = this.app, root = $('#ui');
    this.narrow.addEventListener('change', () => { this.mobilePanel = this.narrow.matches ? this.inspector : null; this.syncPanels(); });
    root.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.panel) this.togglePanel(b.dataset.panel);
      if (b.dataset.close) this.closePanel(b.dataset.close);
      if (b.dataset.v) app.setView(b.dataset.v);
      if (b.dataset.s) app.setStyle(b.dataset.s);
      if (b.dataset.city !== undefined) {
        app.openCity(CITY_EXAMPLES[Number(b.dataset.city)]);
        if (this.narrow.matches) this.closePanel('stories');
      }
      if (b.dataset.story) {
        if (app.state.story?.id === b.dataset.story && this.narrow.matches) this.closePanel('stories');
        else { this.inspector = null; app.startStory(b.dataset.story); this.syncPanels(); }
      }
      if (b.dataset.action === 'exit') app.exitStory();
      else if (b.dataset.action) app.storyAction(b.dataset.action, b.dataset.value);
      if (b.hasAttribute('data-unpin')) this.removePin(Number(b.dataset.unpin));
    });
    $('#systems').addEventListener('click', (e) => {
      const h = e.target.closest('.sys-h');
      if (h) { h.setAttribute('aria-expanded', String(!h.parentElement.classList.toggle('closed'))); return; }
      const lens = e.target.closest('[data-lens]');
      if (lens) { app.setLens(app.state.lens === lens.dataset.lens ? 'none' : lens.dataset.lens); return; }
      const info = e.target.closest('[data-info]');
      if (info) app.openLayerCard(info.dataset.info.split(':')[1], false);
    });
    $('#systems').addEventListener('change', (e) => { const c = e.target.closest('input[data-layer]'); if (c) app.setLayer(c.dataset.layer, c.checked); });
    $('#btn-now').addEventListener('click', () => app.goLive());
    $('#btn-play').addEventListener('click', () => app.togglePlay());
    $('#speed').addEventListener('change', (e) => app.setSpeed(e.target.value));
    $('#zoom-in').addEventListener('click', () => app.zoom(0.68));
    $('#zoom-out').addEventListener('click', () => app.zoom(1 / 0.68));
    $('#map-home').addEventListener('click', () => app.home());
    $('#city-open').addEventListener('click', () => { if (app.state.city) app.closeCity(); else app.openCity(); });
    $('#city-close').addEventListener('click', () => { app.closeCity(); $('#city-open').focus(); });
    $('#city-left').addEventListener('click', () => app.turnCity(-45));
    $('#city-right').addEventListener('click', () => app.turnCity(45));
    $('#city-pitch').addEventListener('input', (e) => app.setCityPitch(Number(e.target.value)));
    $('#city-retry').addEventListener('click', () => app.retryBuildings());
    const yr = $('#sl-year'), dy = $('#sl-day');
    const fromSliders = () => {
      const y = new Date(app.state.t).getUTCFullYear();
      app.setTime(Date.UTC(y, 0, 1) + Number(yr.value) * 86400000 + Number(dy.value) * 60000);
    };
    yr.addEventListener('input', fromSliders); dy.addEventListener('input', fromSliders);
    $('#btn-about').addEventListener('click', () => this.showAbout());
    $('#card').addEventListener('click', (e) => {
      if (e.target.closest('.card-x')) { app.closeCard(); return; }
      if (e.target.closest('.card-city')) { app.openCity(this._card.place); return; }
      if (e.target.closest('.card-pin')) { this.pinPlace(); return; }
      const o = e.target.closest('[data-open]');
      if (o?.dataset.open.startsWith('river:')) { const hit = app.data.riverRef(o.dataset.open.slice(6)); if (hit) app.pick(hit); }
      else if (o) app.openRef(o.dataset.open);
      if (e.target.closest('.card-go')) app.flyToSelection();
    });
    const s = $('#search'), res = $('#results');
    let hits = [];
    const render = () => { res.hidden = !hits.length; res.innerHTML = hits.map((h, i) => `<button data-i="${i}"><b>${esc(h.label)}</b><span>${esc(h.sub || '')}</span></button>`).join(''); };
    const pick = (hit) => { if (!hit) return; s.value = ''; hits = []; render(); s.blur(); app.pick(hit); };
    s.addEventListener('input', () => { hits = app.search(s.value); render(); });
    s.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') pick(hits[0]);
      if (e.key === 'Escape') { hits = []; render(); this.closePanel('search'); s.blur(); }
    });
    res.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) pick(hits[Number(b.dataset.i)]); });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !e.target.matches('#search')) {
        if (!$('#about').hidden) { $('#about').hidden = true; $('#btn-about').focus(); }
        else if (this.narrow.matches && this.mobilePanel) this.closePanel(this.mobilePanel);
        else if (this.inspector) this.closePanel(this.inspector);
        return;
      }
      if (e.target.closest('input, select, textarea, button, a, summary') || e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key === ' ') { e.preventDefault(); app.togglePlay(); }
      else if (e.key === 'n') app.goLive();
      else if (e.key === 'g') app.setView(app.cam.view === 'globe' ? 'sheet' : 'globe');
      else if (e.key === 'a') app.setStyle(app.state.style === 'atlas' ? 'space' : 'atlas');
      else if (e.key === '/') { e.preventDefault(); if (this.narrow.matches && this.mobilePanel !== 'search') this.togglePanel('search'); s.focus(); }
    });
  }

  togglePanel(id) {
    if (this.narrow.matches) this.mobilePanel = this.mobilePanel === id ? null : id;
    else if (id === 'stories') this.leftPanel = this.leftPanel === id ? 'layers' : id;
    else if (id === 'layers') this.leftPanel = this.leftPanel === id ? null : id;
    else if (id === 'planet') this.desktopPlanet = !this.desktopPlanet;
    else this.inspector = this.inspector === id ? null : id;
    this.syncPanels();
    if (id === 'search' && this.mobilePanel === 'search') $('#search').focus();
    if (id === 'planet' && this.planetOpen()) this.app.showPlanet();
    if (id === 'compare' && (this.inspector === 'compare' || this.mobilePanel === 'compare')) this.renderCompare();
  }

  planetOpen() { return this.narrow.matches ? this.mobilePanel === 'planet' : this.desktopPlanet; }

  closePanel(id) {
    if (id === 'place') { this.app.closeCard(); return; }
    if (this.narrow.matches) this.mobilePanel = null;
    else if (id === 'stories') this.leftPanel = 'layers';
    else if (id === 'layers') this.leftPanel = null;
    else if (id === 'planet') this.desktopPlanet = false;
    else if (id !== 'search') this.inspector = null;
    this.syncPanels();
    const buttons = [...document.querySelectorAll(`[data-panel="${id}"]`)];
    buttons.find((b) => b.getClientRects().length)?.focus();
  }

  syncPanels() {
    const mobile = this.narrow.matches, left = mobile ? this.mobilePanel : this.leftPanel, right = mobile ? this.mobilePanel : this.inspector;
    const search = $('#search-panel');
    const parent = mobile ? $('#ui') : $('#top');
    if (search.parentElement !== parent) parent.insertBefore(search, mobile ? null : $('#clock'));
    $('#left').hidden = left !== 'stories' && left !== 'layers';
    $('#story-panel').hidden = left !== 'stories';
    $('#layer-panel').hidden = left !== 'layers';
    $('#card').hidden = right !== 'place' || !this._card;
    $('#compare').hidden = right !== 'compare';
    $('#dash').hidden = !this.planetOpen();
    $('#time').hidden = mobile && this.mobilePanel !== 'time';
    $('#search-panel').hidden = mobile && this.mobilePanel !== 'search';
    $('#spotlight').hidden = mobile ? Boolean(this.mobilePanel || this.app.state.city) : Boolean(right || this.planetOpen() || !this.app.state.story);
    document.body.classList.toggle('city-mode', this.app.state.city);
    document.body.classList.toggle('sheet-open', mobile && Boolean(this.mobilePanel));
    for (const b of document.querySelectorAll('[data-panel]')) {
      b.setAttribute('aria-expanded', String(b.dataset.panel === 'planet' ? this.planetOpen() : b.dataset.panel === left || b.dataset.panel === right));
    }
  }

  syncStory() {
    const story = this.app.state.story, host = $('#story-now'), active = STORY_BY_ID[story?.id];
    const key = `${active?.id}|${story?.pole}|${story?.month}|${story?.recent}|${this.app.state.lens}`;
    host.hidden = !active;
    this.syncPanels();
    if (this.storyKey === key) return;
    this.storyKey = key;
    for (const b of document.querySelectorAll('[data-story]')) b.setAttribute('aria-pressed', String(b.dataset.story === story?.id));
    $('#spot-rotation').hidden = active?.id !== 'daylight';
    if (!active) { host.innerHTML = ''; return; }
    const focus = document.activeElement?.dataset;
    const pair = (action, label, options, selected) => `<div class="seg story-seg" role="group" aria-label="${label}">${options.map(([v, text]) => `<button data-action="${action}" data-value="${v}" aria-pressed="${v === selected}">${text}</button>`).join('')}</div>`;
    const controls = active.id === 'daylight' ? '<button class="pill play-story" data-action="rotation">Play one rotation</button>'
      : active.id === 'seasons' ? pair('month', 'Solstice', [['5', 'June'], ['11', 'December']], String(story.month))
        + pair('pole', 'Hemisphere', [['north', 'North'], ['south', 'South']], story.pole)
        + pair('lens', 'What to compare', [['ice', 'Sea ice'], ['solar', 'Sunlight']], this.app.state.lens)
        : pair('earthquakes', 'Earthquake record', [['recent', 'Past 30 days'], ['historical', '2000–2025']], story.recent ? 'recent' : 'historical')
          + '<div class="story-key"><span>Plate boundaries</span><span>Volcanoes</span><span>Earthquakes</span></div>';
    host.innerHTML = `<div class="section-label">${active.subject}</div><h3>${active.title}</h3><p>${active.detail}</p><div class="story-actions">${controls}</div><div class="story-footer"><button class="ghost mobile-only" data-close="stories">View map</button><button class="ghost" data-action="exit">Exit guided view</button></div>`;
    [...host.querySelectorAll('[data-action]')].find((b) => b.dataset.action === focus?.action && b.dataset.value === focus?.value)?.focus();
  }

  pinPlace() {
    const { place } = this._card;
    const { pins } = this.app.state;
    if (!place || pins.length >= 2 || pins.some((p) => p.lon === place.lon && p.lat === place.lat)) return;
    this.app.setPins([...pins, place]);
    this.refreshPinButton();
    $('#compare-open').hidden = false;
    if (pins.length === 1) this.togglePanel('compare');
  }

  removePin(i) {
    this.app.setPins(this.app.state.pins.filter((_, index) => index !== i));
    $('#compare-open').hidden = !this.app.state.pins.length;
    this.refreshPinButton();
    this.renderCompare();
    ($('#compare-pins button') || $('#compare [data-close]')).focus();
  }

  refreshPinButton() {
    const b = $('.card-pin'), place = this._card?.place, { pins } = this.app.state;
    if (!b || !place) return;
    const isPinned = pins.some((p) => p.lon === place.lon && p.lat === place.lat);
    b.disabled = isPinned || pins.length >= 2;
    b.textContent = isPinned ? 'Pinned' : pins.length >= 2 ? '2 places pinned' : 'Pin place';
  }

  renderCompare() {
    const host = $('#compare-pins');
    const { pins } = this.app.state;
    if (this.renderedPins !== pins) {
      this.renderedPins = pins;
      host.innerHTML = pins.map((p, i) => `<div class="compare-pin"><span>${i === 0 ? 'A' : 'B'}</span><strong>${esc(p.title)}</strong><button class="ghost icon-button" data-unpin="${i}" aria-label="Remove ${esc(p.title)}">×</button></div>`).join('');
    }
    const data = $('#compare-data');
    const top = $('#compare').scrollTop;
    const html = pins.length === 2 ? this.app.comparePlaces() : '<p>Select a place on the map or search for it, then choose <strong>Pin place</strong>. Pin two places to compare their daylight and seasons.</p>';
    if (this.compareHTML !== html) { data.innerHTML = html; this.compareHTML = html; $('#compare').scrollTop = top; }
  }

  // ------------------------------------------------------------------------------- updates
  syncControls() {
    const st = this.app.state;
    document.body.dataset.style = st.style;
    document.body.dataset.view = this.app.cam.view;
    for (const c of document.querySelectorAll('input[data-layer]')) c.checked = !!st.layers[c.dataset.layer];
    for (const b of document.querySelectorAll('[data-lens]')) b.setAttribute('aria-pressed', String(b.dataset.lens === st.lens));
    for (const b of document.querySelectorAll('[data-v]')) b.setAttribute('aria-pressed', String(b.dataset.v === this.app.cam.view));
    for (const b of document.querySelectorAll('[data-s]')) b.setAttribute('aria-pressed', String(b.dataset.s === st.style));
    for (const s of SYSTEMS) {
      const n = s.layers.filter((l) => st.layers[l.id]).length + (s.lenses.some((l) => l.id === st.lens) ? 1 : 0);
      $(`[data-count="${s.id}"]`).textContent = n ? String(n) : '';
    }
    $('#speed').value = st.speed;
    this.legend();
    this.syncStory();
    this.cityControls();
  }

  clock() {
    const st = this.app.state, d = new Date(st.t), time = d.toISOString().slice(11, 16);
    const y = d.getUTCFullYear(), start = Date.UTC(y, 0, 1), doy = Math.floor((st.t - start) / 86400000), mins = d.getUTCHours() * 60 + d.getUTCMinutes();
    const month = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
    $('#ck-time').textContent = time;
    $('#ck-date').textContent = `${month} ${y}`;
    const mode = $('#ck-mode'), live = st.clock === 'live';
    mode.classList.toggle('live', live);
    mode.textContent = live ? 'Now' : 'Typical year';
    mode.title = live ? 'Current time. Feed status appears on its layer.' : 'Seasonal averages and modelled conditions at the selected time.';
    $('#btn-now').classList.toggle('on', live);
    $('#btn-now').setAttribute('aria-pressed', String(live));
    $('#btn-play').textContent = st.clock === 'paused' ? 'Play' : 'Pause';
    if (this.tickYear !== y) {
      this._buildTicks(y);
      $('#sl-year').max = (Date.UTC(y + 1, 0, 1) - start) / 86400000 - 1;
    }
    for (const [id, value, text] of [['sl-year', doy, month], ['sl-day', mins, time + ' UTC']]) {
      const slider = $(`#${id}`);
      slider.value = value;
      slider.setAttribute('aria-valuetext', text);
      slider.style.setProperty('--progress', `${value / slider.max * 100}%`);
    }
    $('#out-year').textContent = month;
    $('#out-day').textContent = time;
    if (st.story?.id === 'daylight') {
      const rotation = this.app.rotationState();
      const label = rotation === 'run' ? 'Pause rotation' : rotation === 'paused' ? 'Resume rotation' : 'Play one rotation';
      for (const b of document.querySelectorAll('[data-action="rotation"]')) b.textContent = label;
    }
    if (st.story?.id === 'seasons') {
      for (const b of document.querySelectorAll('[data-action="month"]')) {
        b.setAttribute('aria-pressed', String(Number(b.dataset.value) === d.getUTCMonth() && d.getUTCDate() === 21));
      }
    }
  }

  legend() {
    const st = this.app.state, host = $('#legend'), l = LENS_DEFS[st.lens];
    document.body.classList.toggle('has-lens', Boolean(l));
    if (!l) { host.hidden = true; this.legendKey = ''; return; }
    let ticks = l.ticks;
    if (typeof ticks === 'string') {                      // "log:<field>:v1,v2,..." - positions come from the field's own encoding
      const [, field, vals] = ticks.split(':');
      const m = this.app.fields.meta.human && this.app.fields.meta.human[field];
      ticks = m ? vals.split(',').map((v) => [Math.log1p(+v / m.x0) / Math.log1p(m.xmax / m.x0), (+v).toLocaleString('en-US')]) : [];
    }
    const key = l.id + JSON.stringify(ticks);
    if (key === this.legendKey) return;
    this.legendKey = key;
    host.hidden = false;
    host.innerHTML = `<div class="lg-h"><button class="lname" data-info="lens:${l.id}">${esc(l.name)}</button>${l.units ? `<span class="units">${esc(l.units)}</span>` : ''}<span class="tier tier-${l.tier}">${TIERS[l.tier].label}</span><button class="ghost icon-button lg-x" aria-label="Remove lens">×</button></div>
      <div class="lg-bar" style="background:${paletteCss(l.palette)}"></div><div class="lg-ticks">${ticks.map(([t, s]) => `<span style="left:${(t * 100).toFixed(1)}%">${esc(s)}</span>`).join('')}</div><p class="lg-explain">${esc(LENS_NOTES[l.id].legend)}</p>`;
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
    // sources that ask to be named on the map itself, while their data is on it (Sentinel-2 cloudless by EOX; OpenStreetMap)
    const cr = $('#credit'), key = credit ? credit.map((c) => c.credit).join('|') : '';
    if (cr.dataset.k !== key) {
      cr.dataset.k = key; cr.textContent = '';
      for (const [i, c] of (credit || []).entries()) { const a = document.createElement('a'); a.href = c.link; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = c.credit; cr.append(i ? ' \u00b7 ' : '', c.pre, a, c.post); }
    }
  }

  cityControls() {
    const { state, cam, buildings } = this.app, active = state.city;
    $('#city-open').hidden = !active && (!state.layers.detail || cam.kmPerPx() >= 0.12);
    $('#city-open').setAttribute('aria-pressed', String(active));
    $('#city-controls').hidden = !active;
    document.body.classList.toggle('city-mode', active);
    if (!active) return;
    const slider = $('#city-pitch');
    slider.value = cam.pitch;
    $('#city-angle').textContent = `${cam.pitch}°`;
    slider.setAttribute('aria-valuetext', `${cam.pitch} degrees`);
    const info = buildings.info;
    let text = '';
    if (!state.layers.detail) text = 'Turn on Finer ground in Systems to load building data.';
    else if (buildings.status === 'zoom') text = 'Zoom in to see individual buildings.';
    else if (buildings.status === 'failed') text = 'Building tiles could not be loaded.';
    else if (buildings.status === 'empty') text = 'No building geometry is mapped in these tiles.';
    else if (buildings.status === 'ready') {
      text = `${info.count.toLocaleString('en-US')} rendered footprints`;
      if (info.truncated) text += ' · nearest blocks and taller buildings prioritized';
      else if (info.limited) text += ' · central tiles shown at this scale';
      if (info.failed) text += ' · some tiles unavailable';
    } else text = 'Loading building geometry…';
    const status = $('#city-status');
    if (status.textContent !== text) status.textContent = text;
    $('#city-retry').hidden = buildings.status !== 'failed' && !info?.failed;
  }

  layerStatus(id, text, cls = '') { const n = $(`[data-stat="${id}"]`); if (n) { n.textContent = text || ''; n.className = 'lstat ' + cls; } }

  showCard(card) {
    const host = $('#card'), was = this._card;
    if (!card) {
      host.innerHTML = ''; this._card = null; mountDescription(null);
      if (this.inspector === 'place') this.inspector = null;
      if (this.mobilePanel === 'place') this.mobilePanel = null;
      this.syncPanels();
      return;
    }
    const key = `${card.kind}|${card.lon}|${card.lat}|${(/<h2>(.*?)<\/h2>/.exec(card.html) || [])[1]}`;
    const same = was?.key === key;
    const r = card.lensReading;
    const lens = r ? `<section class="lens-reading" aria-label="Selected map layer at this place"><span>${esc(r.name)}</span><strong>${esc(r.value)}</strong><small><span class="tier tier-${r.tier}">${TIERS[r.tier].label}</span> ${esc(r.vintage)}</small></section>` : '';
    const pin = card.lon !== undefined && card.kind !== 'sat';
    const cities = card.kind === 'city' && Math.abs(card.lat) < 84
      ? '<button class="ghost card-city">Explore in 3D</button>' : '';
    const html = `<div class="card-bar"><div>${card.lon !== undefined ? '<button class="ghost card-go" title="Centre the view here">Centre</button>' : ''}${pin ? '<button class="ghost card-pin">Pin place</button>' : ''}${cities}</div><button class="ghost icon-button card-x" aria-label="Close place details">×</button></div><div class="card-body">${lens}${card.html}</div>`;
    if (same && was.html === html) return;
    const top = host.scrollTop, open = same ? [...host.querySelectorAll('details')].map((d) => d.open) : [];
    const focus = same ? [...host.querySelectorAll('button, summary')].indexOf(document.activeElement) : -1;
    host.innerHTML = html;
    const title = $('h2', host)?.textContent || coord(card.lon ?? 0, card.lat ?? 0);
    this._card = { key, html, place: pin ? { title, lon: card.lon, lat: card.lat } : null };
    this.refreshPinButton();
    host.querySelectorAll('details').forEach((d, i) => { if (open[i]) d.open = true; });
    mountDescription(host);
    if (!same) {
      if (this.narrow.matches) this.mobilePanel = 'place';
      else this.inspector = 'place';
      this.syncPanels();
    }
    host.scrollTop = same ? top : 0;
    if (focus >= 0) host.querySelectorAll('button, summary')[focus]?.focus({ preventScroll: true });
  }

  dashboard(d) {
    const row = (k, v, tier, sub) => `<div class="drow"><span class="k">${k}</span><span class="v">${v}${sub ? `<small>${sub}</small>` : ''}</span><span class="tier tier-${tier}">${TIERS[tier].label}</span></div>`;
    const b = (n) => (n / 1e9).toFixed(2) + ' bn';
    const bar = d.people ? `<div class="pbar" title="People in daylight, twilight and night"><i class="day" style="width:${(d.people.day / d.people.total * 100).toFixed(1)}%"></i><i class="twi" style="width:${(d.people.twilight / d.people.total * 100).toFixed(1)}%"></i><i class="night" style="width:${(d.people.night / d.people.total * 100).toFixed(1)}%"></i></div>` : '';
    const { story, clock, t } = this.app.state;
    const active = STORY_BY_ID[story?.id];
    const percent = d.people?.total ? Math.round(d.people.day / d.people.total * 100) : null;
    let metric = percent === null ? '—' : `${percent}%`, label = 'of people in daylight', tier = 'modelled', vintage = 'Solar position · GHSL 2025', graphic = bar;
    if (active?.id === 'seasons') {
      const north = story.pole === 'north';
      metric = d.ice ? `${(north ? d.ice.n : d.ice.s).toFixed(1)} <small>M km²</small>` : '—';
      label = `${north ? 'Arctic' : 'Antarctic'} sea-ice extent`; tier = 'climatology'; vintage = 'NSIDC · 1991–2020'; graphic = '';
    } else if (active?.id === 'plates') {
      metric = story.recent ? (d.quakes?.week ?? '—') : '2000–2025';
      label = story.recent ? 'M4.5+ earthquakes worldwide in 7 days' : 'M6+ earthquakes in the catalogue';
      tier = story.recent ? 'live' : 'static';
      vintage = story.recent ? (d.quakes ? this.app.live.note.quakes || 'USGS feed' : d.quakeNote) : 'USGS earthquake catalogue';
      graphic = '';
    }
    $('#spot-kicker').textContent = active ? active.title : clock === 'live' ? 'Planet now' : 'Planet in a typical year';
    const spot = `<div class="spot-value">${metric}</div><div class="spot-label">${label}</div>${graphic}<p class="spot-source"><span class="tier tier-${tier}">${TIERS[tier].label}</span> ${esc(vintage)}</p>`;
    if (this.spotHTML !== spot) { $('#spot-metric').innerHTML = spot; this.spotHTML = spot; }
    const feature = $('#dash-feature');
    feature.hidden = !active;
    const featureKey = active ? active.id + '|' + spot : '';
    if (this.featureKey !== featureKey) {
      feature.innerHTML = active ? `<div class="section-label">${active.title}</div>${spot}` : '';
      this.featureKey = featureKey;
    }
    if (!$('#compare').hidden) this.renderCompare();
    if ($('#dash').hidden) return;
    $('#dash-title').textContent = clock === 'live' ? 'Planet now' : 'Planet in a typical year';
    $('#dash-content').innerHTML = `<div class="dash-date">${new Date(t).toISOString().slice(0, 16).replace('T', ' ')} UTC</div>
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
      <p>Closer in than 5 km a pixel, with <i>Finer ground, close in</i> switched on (it is by default), the page fetches map tiles for the part of the Earth on screen from five hosts: imagery and night lights from NASA (gibs.earthdata.nasa.gov), elevation from Amazon Web Services (s3.amazonaws.com), where the water is from the European Commission’s Global Surface Water on Google’s storage (storage.googleapis.com), closer in than about 0.6 km a pixel Sentinel-2 imagery from EOX in Vienna (tiles.maps.eox.at), and closer in than 120 m a pixel OpenStreetMap’s streets and buildings from OpenFreeMap (tiles.openfreemap.org). Those requests tell the hosts roughly where you are looking, as any tiled map does. Nothing else about you is sent, and with the layer off none of them is asked for anything. The live layers (earthquakes, aurora, satellites, today’s Earth) fetch whole-Earth files that say nothing about where you look.</p>
      <p>Opening the card of a place asks English Wikipedia (en.wikipedia.org) for the opening of that place’s article: the request carries the article’s title and nothing else, so it tells Wikipedia which place you opened and nothing more about you.</p>
      <div id="updlog"></div>
      <h3>Sources</h3><ul class="srcs">${sources.map((s) => `<li>${esc(s)}</li>`).join('')}<li>Country statistics: World Bank Open Data, CC BY 4.0.</li><li>${esc(CARD_TEXT_SOURCE)}</li>
      <li>Where the sea, the land and the lakes are: Natural Earth 5.1.2, 1:10m land, minor islands and lakes (public domain); Antarctica’s ice front from Blue Marble. The wide rivers, and the lakes strung along them: NASA’s MODIS land-water mask (MOD44W), along Natural Earth’s 1:10m river lines. The colour of shallow and silty water is Blue Marble’s own.</li>
      <li>We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).</li>
      <li>The ground closer in than about 0.6 km a pixel: <a href="https://s2maps.eu" target="_blank" rel="noopener noreferrer">Sentinel-2 cloudless</a> by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2016), CC BY 4.0, fetched as tiles while you look. It is named on the map whenever it is on screen.</li>
      <li>Land and water closer in than 5 km a pixel: <a href="https://global-surface-water.appspot.com" target="_blank" rel="noopener noreferrer">Global Surface Water</a>, water occurrence 1984–2021 (Pekel et al. 2016, Nature 540). Source: EC JRC/Google. Checked against ESA WorldCover 2021 v200 (© ESA WorldCover project, contains modified Copernicus Sentinel data, CC BY 4.0), which is not shipped.</li>
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
