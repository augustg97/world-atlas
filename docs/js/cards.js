// Cards. Every drawn thing is clickable, and so is every bare pixel (the probe). A card carries
// an eyebrow, a title, fact rows, values FOR THE CURRENT INSTANT with their evidence tier, the
// vintage of every number, and its sources (SCOPE section 7).

import { TIERS, LAYERS, LENS_DEFS, FUEL_COLORS } from './catalog.js?v=20261111T235202Z';
import { sunElevation, localSolarTime, dayLength, D2R } from './astro.js?v=20261111T235202Z';
import { R_KM } from './camera.js?v=20261111T235202Z';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v, d = 0) => (Number.isFinite(v) ? v.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d }) : '—');
const big = (v) => (!Number.isFinite(v) ? '—' : v >= 1e12 ? fmt(v / 1e12, 2) + ' trillion' : v >= 1e9 ? fmt(v / 1e9, 2) + ' billion' : v >= 1e6 ? fmt(v / 1e6, 1) + ' million' : fmt(v));
const hhmm = (h) => { const m = Math.round(h * 60) % 1440; return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`; };
const dur = (h) => (h >= 24 ? '24 h (polar day)' : h <= 0 ? '0 h (polar night)' : `${Math.floor(h)} h ${String(Math.round((h % 1) * 60)).padStart(2, '0')} m`);
export const coord = (lon, lat) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
const badge = (tier, extra = '') => `<span class="tier tier-${tier}" title="${esc(TIERS[tier].title)}">${TIERS[tier].label}${extra ? ' · ' + esc(extra) : ''}</span>`;
const row = (k, v, tier, extra) => `<div class="row"><span class="k">${k}</span><span class="v">${v}</span>${tier ? badge(tier, extra) : ''}</div>`;
const section = (title, body) => (body ? `<div class="sec"><div class="sec-h">${title}</div>${body}</div>` : '');
const src = (list) => `<div class="src"><div class="sec-h">Sources</div>${list.map((s) => `<p>${esc(s)}</p>`).join('')}</div>`;
const compass = (u, v) => ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round((((Math.atan2(-u, -v) / D2R) % 360) + 360) % 360 / 22.5) % 16];

export function kmBetween(lon1, lat1, lon2, lat2) {
  const p1 = lat1 * D2R, p2 = lat2 * D2R, dl = (lon2 - lon1) * D2R;
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** The air temperature model, identical to the one in shaders/earth.frag.glsl. */
export function airTemp(F, lon, lat, ms, sunNow) {
  const t0 = F.climate('t0', lon, lat, ms);
  if (Number.isNaN(t0)) return { now: NaN, mean: NaN };
  const z = Math.max(0, F.elevation(lon, lat) || 0), lapse = F.meta.climate.lapse_K_per_km;
  const mean = t0 - lapse * z / 1000;
  const precip = F.climate('precip', lon, lat, ms), cloud = F.climate('cloud', lon, lat, ms);
  const water = F.waterFrac(lon, lat) > 0.5 ? 1 : 0;
  const arid = 1 - Math.max(0, Math.min(1, precip / 4));
  const dtr = water ? 0.4 : (4 + 5.5 * arid) * (1 - 0.45 * cloud);
  const lst = localSolarTime(sunNow, lon);
  return { now: mean - dtr * Math.cos((lst - 14.5) * Math.PI / 12), mean, dtr };
}

function sunRows(ctx, lon, lat) {
  const s = ctx.astro.sun;
  const el = sunElevation(s, lon, lat);
  const state = el > 0 ? 'day' : el > -6 ? 'civil twilight' : el > -12 ? 'nautical twilight' : el > -18 ? 'astronomical twilight' : 'night';
  return row('Local solar time', hhmm(localSolarTime(s, lon)), 'modelled') + row('Sun', `${el.toFixed(1)}° ${el >= 0 ? 'above' : 'below'} the horizon · ${state}`) + row('Daylight today', dur(dayLength(lat, s.dec)));
}

function nearestCity(D, lon, lat, maxKm) {
  let best = null, bd = maxKm;
  for (const r of D.places.rows) {
    if (Math.abs(r[2] - lat) > 3) continue;
    const d = kmBetween(lon, lat, r[1], r[2]);
    if (d < bd) { bd = d; best = r; }
  }
  return best ? { row: best, km: bd } : null;
}

// ------------------------------------------ the probe ------------------------------------------
export function probeCard(ctx, lon, lat) {
  const { F, D, astro } = ctx, ms = astro.month;
  const water = F.waterFrac(lon, lat), isWater = water > 0.5;
  const z = F.elevation(lon, lat);
  const c = D.countryAt(lon, lat);
  const near = nearestCity(D, lon, lat, 250);
  const marine = !c && isWater ? D.seaAt(lon, lat) : null;
  const title = c ? c.name : (marine || (isWater ? 'Open ocean' : 'Unclaimed land'));
  const T = airTemp(F, lon, lat, ms, astro.sun);
  const u = F.climate('u10', lon, lat, ms), v = F.climate('v10', lon, lat, ms);
  const monthName = new Date(ctx.t).toLocaleString('en-US', { month: 'long', timeZone: 'UTC' });
  let ground = row(isWater ? 'Depth' : 'Elevation', Number.isFinite(z) ? `${fmt(Math.abs(z))} m ${z < 0 ? 'below' : 'above'} sea level` : 'loading…', 'static', '2022');
  if (c) ground += row('Administered by', esc(c.name), 'static', '2022');
  if (F.isDisputed(lon, lat)) ground += `<div class="note contested">This ground is contested. ${esc(D.disputeNear(lon, lat) || 'See the dispute card for the claimants.')}</div>`;
  if (near) ground += row('Nearest city', `${esc(near.row[0])} · ${fmt(near.km)} km`);
  const air = row('Air temperature now', `${fmt(T.now, 1)} °C`, 'modelled') + row(`${monthName} mean`, `${fmt(T.mean, 1)} °C`, 'climatology', '1991–2020')
    + row('Wind', `${fmt(Math.hypot(u, v), 1)} m/s from the ${compass(u, v)}`, 'climatology') + row('Pressure', `${fmt(F.climate('slp', lon, lat, ms))} hPa`, 'climatology')
    + row('Precipitation', `${fmt(F.climate('precip', lon, lat, ms), 1)} mm/day`, 'climatology') + row('Cloud cover', `${fmt(F.climate('cloud', lon, lat, ms) * 100)} %`, 'climatology');
  let sea = '';
  if (isWater) {
    const sst = F.climate('sst', lon, lat, ms), ice = F.climate('ice', lon, lat, ms), cu = F.climate('ucur', lon, lat, ms), cv = F.climate('vcur', lon, lat, ms);
    // ice: the sea's is NSIDC's; a lake's is OISST's where that has the lake, and otherwise a model of how often it is frozen
    const kind = F.iceKind(lon, lat);
    const iceRow = !(ice > 0.01) ? '' : kind === 'model' ? row('Lake and river ice', `frozen ${fmt(ice * 100)} % of ${monthName}`, 'modelled') : row(kind === 'lake' ? 'Lake ice' : 'Sea ice', `${fmt(ice * 100)} % cover`, 'climatology');
    sea = row(kind === 'sea' ? 'Sea-surface temperature' : 'Water temperature', Number.isNaN(sst) ? 'no data (inland water)' : `${fmt(sst, 1)} °C`, 'climatology') + iceRow
      + row('Surface current', Number.isNaN(cu) ? 'no data here' : `${fmt(Math.hypot(cu, cv) * 100)} cm/s towards the ${compass(-cu, -cv)}`, 'climatology', '2019–23');
  }
  const pop = F.staticValue('pop', lon, lat), co2 = F.staticValue('co2', lon, lat), nl = F.nightLight(lon, lat), sh = F.staticValue('ships', lon, lat);
  let people = '';
  if (!isWater) people += row('Population density', Number.isNaN(pop) ? 'loading…' : pop < 0.5 ? 'under 1 person/km²' : `${fmt(pop)} people/km²`, 'static', '2025');
  people += row('Light at night', Number.isNaN(nl) ? 'loading…' : nl < 0.004 ? 'dark' : nl < 0.06 ? 'dim' : nl < 0.3 ? 'lit' : 'brightly lit', 'static', '2016');
  if (Number.isFinite(co2) && co2 > 6) people += row('Fossil CO₂', `${fmt(co2)} t/km²/yr`, 'static', '2022');
  if (isWater && Number.isFinite(sh) && sh > 6e4) people += row('Shipping', sh > 5e6 ? 'a major lane' : sh > 6e5 ? 'a regular lane' : 'occasional traffic', 'static', '2015–21');
  return {
    kind: 'probe', lon, lat,
    html: `<div class="eyebrow">${isWater ? 'A point at sea' : 'A point on land'} · ${coord(lon, lat)}</div><h2>${esc(title)}</h2>
      <div class="tierhead">Computed from the fields at this place and time</div>
      ${section('Sun', sunRows(ctx, lon, lat))}${section('Ground', ground)}${section('Air', air)}${section('Sea', sea)}${section('People', people)}
      ${c ? `<button class="link" data-open="country:${c.a3}">Open the card for ${esc(c.name)} →</button>` : ''}`,
  };
}

// ------------------------------------------ entities ------------------------------------------
export function countryCard(ctx, c) {
  const { D } = ctx;
  const st = (c.wb && D.stats.by_code[c.wb]) || null;
  const cap = D.places.rows.find((r) => r[6] === c.a3 && r[5] === 1);
  let facts = '';
  if (cap) facts += row('Capital', esc(cap[0]));
  if (st) {
    for (const code of Object.keys(D.stats.indicators)) {
      const v = st[code]; if (!v) continue;
      const ind = D.stats.indicators[code];
      const val = code === 'SP.POP.TOTL' ? big(v[0]) : code === 'NY.GDP.MKTP.CD' ? '$' + big(v[0]) : code === 'NY.GDP.PCAP.CD' ? '$' + fmt(v[0]) : `${fmt(v[0], v[0] < 100 ? 1 : 0)} ${ind.unit}`;
      facts += row(esc(ind.label), val, 'static', String(v[1]));
    }
  } else {
    facts += row('Population', big(c.pop), 'static', String(c.pop_year)) + `<div class="note">The World Bank publishes no series for this unit, so no statistics are shown. Nothing is borrowed from a neighbour or a parent state.</div>`;
  }
  const disputes = D.political.disputes.filter((d) => d.admin === c.short || d.admin === c.name || (d.note && d.note.includes(c.short)));
  const dis = disputes.map((d) => `<button class="link" data-open="dispute:${esc(d.name)}|${esc(d.note)}">${esc(d.name)}: ${esc(d.note)}</button>`).join('');
  const now = cap ? section(`Now in ${esc(cap[0])}`, sunRows(ctx, cap[1], cap[2]) + row('Air temperature now', `${fmt(airTemp(ctx.F, cap[1], cap[2], ctx.astro.month, ctx.astro.sun).now, 1)} °C`, 'modelled')) : '';
  const tier = st ? 'Curated from World Bank series and Natural Earth' : 'Generic — Natural Earth attributes only';
  return {
    kind: 'country', lon: c.lon, lat: c.lat, country: c,
    html: `<div class="eyebrow">${esc(c.type)} · ${esc(c.subregion || c.continent)}</div><h2>${esc(c.name)}</h2>
      ${c.endonym ? `<div class="endonym">${esc(c.endonym)}</div>` : ''}${c.formal && c.formal !== c.name ? `<div class="formal">${esc(c.formal)}</div>` : ''}
      ${c.sov && c.sov !== c.name && c.sov !== c.short ? `<div class="note">Sovereignty: ${esc(c.sov)}.</div>` : ''}
      <div class="tierhead">${tier}</div>
      ${section('Facts', facts)}${now}${dis ? section('Contested', `<div class="note contested">Boundaries here are disputed. This atlas draws who administers the ground and marks the dispute.</div>${dis}`) : ''}
      ${src(['Geometry and names: Natural Earth 5.1.2 (de facto worldview), public domain.', st ? 'Statistics: World Bank Open Data, CC BY 4.0; the year of each value is shown beside it.' : 'No statistical series available.'])}`,
  };
}

export function cityCard(ctx, r) {
  const [name, lon, lat, pop, rank, capital, a3, adm1, alt] = r;
  const c = ctx.D.countryByA3[a3];
  const T = airTemp(ctx.F, lon, lat, ctx.astro.month, ctx.astro.sun);
  const z = ctx.F.elevation(lon, lat);
  const monthName = new Date(ctx.t).toLocaleString('en-US', { month: 'long', timeZone: 'UTC' });
  return {
    kind: 'city', lon, lat,
    html: `<div class="eyebrow">${capital ? 'Capital city' : 'City'} · ${esc(c ? c.name : a3)}${adm1 ? ' · ' + esc(adm1) : ''}</div><h2>${esc(name)}</h2>
      ${alt ? `<div class="endonym">${esc(alt.split('|')[0])}</div>` : ''}
      <div class="tierhead">Computed from the fields at this place and time</div>
      ${section('Facts', row('Urban-area population', big(pop), 'static', 'NE 5.1') + row('Position', coord(lon, lat)) + row('Ground', Number.isFinite(z) ? `${fmt(Math.max(z, 0))} m (10 km mean)` : 'loading…', 'static', '2022'))}
      ${section('Now', sunRows(ctx, lon, lat) + row('Air temperature now', `${fmt(T.now, 1)} °C`, 'modelled') + row(`${monthName} mean`, `${fmt(T.mean, 1)} °C`, 'climatology', '1991–2020') + row('Precipitation', `${fmt(ctx.F.climate('precip', lon, lat, ctx.astro.month), 1)} mm/day`, 'climatology'))}
      ${c ? `<button class="link" data-open="country:${c.a3}">Open the card for ${esc(c.name)} →</button>` : ''}
      ${src(['Natural Earth 5.1.2 populated places (public domain). Population is the source’s estimate for the urban agglomeration and is not a census figure.'])}`,
  };
}

export function featureCard(ctx, f) {
  const kinds = { 'Range/mtn': 'Mountain range', 'Pen/cape': 'Peninsula or cape', Geoarea: 'Region', ocean: 'Ocean', sea: 'Sea', gulf: 'Gulf', bay: 'Bay', strait: 'Strait', channel: 'Channel', mountain: 'Mountain' };
  const z = ctx.F.elevation(f.lon, f.lat);
  const T = airTemp(ctx.F, f.lon, f.lat, ctx.astro.month, ctx.astro.sun);
  const sst = f.realm === 'sea' ? ctx.F.climate('sst', f.lon, f.lat, ctx.astro.month) : NaN;
  return {
    kind: 'feature', lon: f.lon, lat: f.lat,
    html: `<div class="eyebrow">${esc(kinds[f.kind] || f.kind)}</div><h2>${esc(f.name)}</h2>
      <div class="tierhead">Generic — Natural Earth attributes only</div>
      ${section('At its label point', row('Position', coord(f.lon, f.lat)) + (f.elev ? row('Summit', `${fmt(f.elev)} m`, 'static') : row(z < 0 ? 'Depth' : 'Elevation', `${fmt(Math.abs(z))} m`, 'static', '2022'))
        + (Number.isFinite(sst) ? row('Sea-surface temperature', `${fmt(sst, 1)} °C`, 'climatology') : row('Air temperature now', `${fmt(T.now, 1)} °C`, 'modelled')))}
      ${section('Sun', sunRows(ctx, f.lon, f.lat))}
      <div class="note">This atlas has no curated text for this feature yet. What is shown is the name and class from the source, and the fields sampled at one point inside it.</div>
      ${src(['Natural Earth 5.1.2 geography regions and marine areas (public domain).'])}`,
  };
}

export function disputeCard(ctx, d) {
  return {
    kind: 'dispute', lon: d.lon, lat: d.lat,
    html: `<div class="eyebrow">Contested territory</div><h2>${esc(d.name)}</h2>${badge('static', '2022')} <span class="tier tier-contested">CONTESTED</span>
      <div class="tierhead">Curated from Natural Earth’s boundary notes</div>
      ${section('Status', `<p class="prose">${esc(d.note)}.</p><p class="prose">This atlas draws the line of actual control and marks it as disputed. It takes no position on the claims; each party’s own card links here.</p>`)}
      ${src(['Natural Earth 5.1.2 breakaway and disputed areas (public domain). Natural Earth’s notes are brief; they name the administering power and the claimants and nothing more.'])}`,
  };
}

export function quakeCard(ctx, q, live) {
  const [time, lon, lat, depth, mag, place] = q;
  const energy = Math.pow(10, 1.5 * mag + 4.8);        // joules, Gutenberg-Richter
  return {
    kind: 'quake', lon, lat,
    html: `<div class="eyebrow">Earthquake · ${live ? badge('live') : badge('static', '2000–2025')}</div><h2>M ${mag.toFixed(1)}</h2><div class="formal">${esc(place)}</div>
      ${section('Event', row('Time (UTC)', esc(String(time).replace('T', ' ').slice(0, 16))) + row('Depth', `${fmt(depth)} km · ${depth < 70 ? 'shallow' : depth < 300 ? 'intermediate' : 'deep'}`) + row('Position', coord(lon, lat)) + row('Energy released', `${energy.toExponential(1)} J`, 'modelled'))}
      ${src(['USGS ANSS Comprehensive Earthquake Catalog (public domain). Energy from the Gutenberg–Richter relation log E = 1.5 M + 4.8.'])}`,
  };
}

export function volcanoCard(ctx, v) {
  const [name, lon, lat, elev, type, country, code] = v;
  const when = { D1: 'since 1964', D2: '1900–1963', D3: '1800–1899', D4: '1700–1799', D5: '1500–1699', D6: 'AD 1–1499', D7: 'before AD 1 (Holocene)', U: 'undated, probably Holocene', Q: 'Quaternary; possibly Holocene', '?': 'uncertain' }[code] || 'not recorded';
  return {
    kind: 'volcano', lon, lat,
    html: `<div class="eyebrow">Volcano · ${esc(country)}</div><h2>${esc(name)}</h2><div class="tierhead">Generic — catalogue attributes only</div>
      ${section('Facts', row('Type', esc(type || '—')) + row('Summit', Number.isFinite(elev) ? `${fmt(elev)} m` : '—') + row('Last known eruption', when) + row('Position', coord(lon, lat)))}
      ${src(['NOAA NCEI Global Volcano Locations Database (public domain), after the Smithsonian Global Volcanism Program.'])}`,
  };
}

export function plantCard(ctx, P, i) {
  const fuel = P.fuels[P.fuel[i]];
  return {
    kind: 'plant', lon: P.lon[i], lat: P.lat[i],
    html: `<div class="eyebrow">Power station · ${esc(P.country[i])}</div><h2>${esc(P.name[i])}</h2><div class="tierhead">Generic — database attributes only</div>
      ${section('Facts', row('Fuel', `<span class="swatch" style="background:${FUEL_COLORS[fuel]}"></span>${esc(fuel)}`) + row('Capacity', `${fmt(P.mw[i])} MW`, 'static', '2021') + (P.year[i] ? row('Commissioned', String(P.year[i])) : '') + row('Position', coord(P.lon[i], P.lat[i])))}
      ${src(['WRI Global Power Plant Database v1.3.0 (2021), CC BY 4.0. Known to be incomplete for wind and solar built after about 2018.'])}`,
  };
}

export function airportCard(ctx, a, air) {
  const idx = air.airports.indexOf(a);
  const routes = air.routes.filter((r) => r[0] === idx || r[1] === idx).sort((p, q) => q[2] - p[2]).slice(0, 8);
  return {
    kind: 'airport', lon: a.lon, lat: a.lat,
    html: `<div class="eyebrow">Airport · ${esc(a.city)} · ${esc(a.cc)}</div><h2>${esc(a.name)} <small>${esc(a.iata)}</small></h2>${badge('modelled')}
      <div class="tierhead">Position from the record; traffic modelled</div>
      ${section('Largest modelled routes', routes.map((r) => { const o = air.airports[r[0] === idx ? r[1] : r[0]]; return row(`${esc(o.iata)} ${esc(o.city)}`, `${fmt(r[3])} km`); }).join('') || '<div class="note">No route from this airport is among the 2,600 largest modelled flows.</div>')}
      <div class="note">These flows are a gravity model (catchment population × national income per person, over distance). They are not a timetable and they miss hub-and-spoke traffic.</div>
      ${src(['OurAirports (public domain); JRC GHSL population; World Bank GDP per person.'])}`,
  };
}

export function layerCard(id, isLens) {
  const l = isLens ? LENS_DEFS[id] : LAYERS[id];
  return {
    kind: 'layer',
    html: `<div class="eyebrow">${isLens ? 'Data lens' : 'Layer'}</div><h2>${esc(l.name)}</h2>${badge(l.tier)}
      <div class="tierhead">Curated</div>
      ${section('What it is', `<p class="prose">${esc(l.what)}</p>`)}${l.limits ? section('Known limits', `<p class="prose">${esc(l.limits)}</p>`) : ''}
      ${src([l.source])}`,
  };
}
