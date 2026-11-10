// The layer catalogue: every system, layer and lens the atlas tracks, with its evidence tier,
// source, vintage and known limits. The panel, the legends, the layer cards and the About text
// are all generated from this one table, so what the interface claims and what the model does
// are stated once (SCOPE sections 4 and 5).

export const TIERS = {
  live: { label: 'LIVE', title: 'A network feed, timestamped within its own latency' },
  observed: { label: 'OBSERVED', title: 'A measurement of a specific date' },
  climatology: { label: 'CLIMATOLOGY', title: 'A multi-year mean for this time of year: a typical day, not this day' },
  static: { label: 'STATIC', title: 'One vintage that does not change with the clock' },
  modelled: { label: 'MODELLED', title: 'Computed from a mechanism on the fields' },
};

const S = {
  bmng: 'NASA Blue Marble Next Generation (Stöckli et al. 2005), monthly composites of 2004. Public domain.',
  etopo: 'NOAA NCEI ETOPO 2022, 60 arc-second ice-surface elevation. Public domain.',
  r1: 'NCEP/NCAR Reanalysis 1 (Kalnay et al. 1996), 1991–2020 monthly means, via NOAA PSL. Public domain.',
  gpcp: 'GPCP v2.3 (Adler et al. 2018), 1991–2020 monthly means, via NOAA PSL. Public domain.',
  oisst: 'NOAA OISST v2.1 (Huang et al. 2021), 1991–2020 monthly means. Public domain.',
  nsidc: 'NSIDC Sea Ice Index, Version 4 (G02135; Fetterer et al. 2025), monthly concentration grids for every month of 1991–2020. Public domain; citation requested.',
  godas: 'NCEP GODAS, 5 m currents, 2019–2023 monthly means. Public domain.',
  ne: 'Natural Earth 5.1.2, default (de facto) worldview. Public domain.',
  ghsl: 'JRC GHSL GHS-POP R2023A, epoch 2025 (Schiavina et al. 2023). CC BY 4.0.',
  bm: 'NASA Black Marble 2016 (Román et al. 2018). Public domain.',
  edgar: 'EDGAR v8.0 (Crippa et al. 2023, JRC), year 2022. CC BY 4.0.',
  ais: 'World Bank / IMF Global Shipping Traffic Density, AIS positions 2015–2021. CC BY 4.0.',
  wri: 'WRI Global Power Plant Database v1.3.0 (2021). CC BY 4.0.',
  usgs: 'USGS ANSS Comprehensive Earthquake Catalog. Public domain.',
  pb: 'Bird (2003), PB2002 plate boundary model, G³ 4(3) 1027. ODC PDDL.',
  ncei: 'NOAA NCEI Global Volcano Locations Database. Public domain.',
  oa: 'OurAirports (public domain) for airport positions; flows are this atlas’s own gravity model.',
};

export const SYSTEMS = [
  {
    id: 'sun', name: 'Sun & orbit', blurb: 'Where the Sun and Moon stand over the Earth at this instant. Everything else on the globe is downstream of this.',
    layers: [
      { id: 'daylight', name: 'Day and night', tier: 'modelled', on: true, what: 'The terminator, twilight and the length of the day, from the Sun’s position at this instant. In the Space style the planet is simply lit by the Sun; in the Atlas style this shades the night side.', source: 'Solar ephemeris after Meeus (low precision, about 0.01°).', limits: 'No atmospheric refraction in the terminator; twilight bands are a shading, not a measurement.' },
      { id: 'marks', name: 'Sub-solar and sub-lunar points', tier: 'modelled', on: true, what: 'The two places on Earth where the Sun and the Moon are exactly overhead, with the tropics and polar circles.', source: 'Solar and lunar ephemerides after Meeus (Moon to about 0.3°).' },
      { id: 'sats', name: 'Satellites', tier: 'live', on: false, what: 'Space stations, navigation satellites and the brightest objects in low orbit, propagated from published orbital elements.', source: 'CelesTrak GP element sets; SGP4 via satellite.js.', limits: 'Elements are good for about two weeks either side of their epoch. Away from now the positions are a propagation, and the badge says so.' },
      { id: 'aurora', name: 'Aurora', tier: 'live', on: false, what: 'Where aurora is probable right now.', source: 'NOAA SWPC OVATION nowcast.', limits: 'Exists only at the present moment; absent when the clock is moved or the network is down.' },
    ],
    lenses: [
      { id: 'solar', name: 'Sunlight arriving', tier: 'modelled', units: 'W/m²', ticks: [[0, '0'], [0.25, '340'], [0.5, '680'], [0.75, '1020'], [1, '1361']], palette: [[0, '#3a1a5a'], [0.4, '#c1443a'], [0.75, '#f6b34a'], [1, '#fffbe0']], what: 'Solar power arriving at the top of the atmosphere on a horizontal surface: the solar constant times the cosine of the Sun’s zenith angle.', source: 'Computed. Solar constant 1361 W/m².', limits: 'Top of atmosphere; cloud and air are not subtracted.' },
    ],
  },
  {
    id: 'air', name: 'Atmosphere', blurb: 'The air’s typical state for this time of year: where it is warm, wet and moving.',
    layers: [
      { id: 'clouds', name: 'Clouds', tier: 'modelled', on: true, what: 'A real global cloud photograph, carried along the monthly-mean surface wind and thinned or thickened by the monthly cloud-fraction climatology.', source: 'Texture: NASA Blue Marble Clouds (Stöckli, 2002). Coverage and wind: ' + S.r1, limits: 'The shapes are real clouds; their positions are not today’s weather. Small cumulus over humid land is generated: its amount follows the month’s rainfall and the local time of day, and its clumps are noise, not observed clouds. So is the ragged detail on cloud edges closer in than 5 km a pixel. This is the layer most likely to be wrong about any particular place. Against eight NASA EPIC photographs the brightness of cloud over the ocean matches within 5 display levels in 255 at every percentile; over land it matches to the median within 6 and runs up to 20 levels dim above it.' },
      { id: 'air', name: 'Air and limb', tier: 'modelled', on: true, what: 'Rayleigh scattering and a low layer of haze between the ground and the camera, and the thin blue limb. The air is as thin as the real air: a scale height of 8 km, so from far away the limb is a line.', source: 'Single-scattering Rayleigh and aerosol model with Kasten–Young air mass. Exposure and gamma are fitted to NASA EPIC at two targets of known reflectance, deep convective cloud tops and cloud-free deep ocean; the Libya-4 calibration site, not used in the fit, then lands within 3 display levels.', limits: 'Haze is one global-mean amount everywhere: no dust plumes, no smoke. No ozone, because the reference photographs show none. From the centre of the disc to four fifths of the way out, colour is within 3 levels of the photographs; the outermost ring is about 10 levels too bright.' },
      { id: 'wind', name: 'Surface wind', tier: 'climatology', on: true, what: 'Tracers released into the mean wind near the surface. The trade winds, the westerlies and the monsoon reversal are all here.', source: S.r1, limits: 'A monthly mean on a 2.5° grid: no storms, no fronts, no sea breeze.' },
      { id: 'jet', name: 'Jet stream (250 hPa)', tier: 'climatology', on: false, what: 'Tracers in the mean wind at about 10.5 km, where aircraft cruise.', source: S.r1 },
      { id: 'today', name: 'Today’s Earth', tier: 'observed', on: false, what: 'The true-colour satellite mosaic for the clock’s date, replacing the modelled surface and clouds on the day side.', source: 'NASA GIBS, VIIRS (NOAA-20) corrected reflectance. Public domain.', limits: 'Daytime passes only, with gaps between swaths near the equator. Available for past dates from 2018; never for the future.' },
    ],
    lenses: [
      { id: 'temp', name: 'Air temperature', tier: 'modelled', units: '°C', ticks: [[0.056, '−40'], [0.278, '−20'], [0.5, '0'], [0.722, '20'], [0.944, '40']], palette: [[0, '#2b1a6b'], [0.2, '#3b6fd1'], [0.38, '#7fd0e8'], [0.5, '#f4f6e8'], [0.62, '#f6d264'], [0.8, '#e2622e'], [1, '#7a0f1b']], what: 'Air temperature 2 m above the ground at this instant: the monthly mean, corrected for height at every pixel, plus a daily cycle that follows the local Sun.', source: 'Mean: ' + S.r1 + ' Height correction 6.5 K/km on ETOPO 2022. Daily cycle: modelled from local solar time, aridity and cloud.', limits: 'The daily cycle is a model, not a measurement. Winter inversions over ice sheets are not represented.' },
      { id: 'precip', name: 'Precipitation', tier: 'climatology', units: 'mm/day', ticks: [[0, '0'], [0.25, '1'], [0.5, '4'], [0.75, '9'], [1, '16']], palette: [[0, '#c9b98a'], [0.2, '#b9c98a'], [0.4, '#5fb37a'], [0.6, '#2a8fa8'], [0.8, '#2a56b0'], [1, '#5a2a9a']], what: 'Mean rain and snowfall for this time of year. Watch the tropical rain belt cross the equator with the Sun.', source: S.gpcp, limits: '2.5° grid: mountain rain shadows are blurred.' },
      { id: 'slp', name: 'Sea-level pressure', tier: 'climatology', units: 'hPa', ticks: [[0.167, '990'], [0.5, '1010'], [0.833, '1030']], palette: [[0, '#5b2a86'], [0.35, '#5a8fd0'], [0.5, '#e9e9e2'], [0.7, '#f0b860'], [1, '#b5451f']], what: 'The semi-permanent highs and lows that steer the wind.', source: S.r1 },
      { id: 'wind', name: 'Wind speed', tier: 'climatology', units: 'm/s', ticks: [[0, '0'], [0.25, '4'], [0.5, '8'], [0.75, '12'], [1, '16']], palette: [[0, '#1b2a4a'], [0.3, '#2f7fb5'], [0.55, '#7fd3b0'], [0.8, '#f2e36b'], [1, '#f08a3c']], what: 'Speed of the mean surface wind.', source: S.r1, limits: 'The mean of a varying wind is weaker than the wind on a typical day.' },
      { id: 'cloud', name: 'Cloud cover', tier: 'climatology', units: '%', ticks: [[0, '0'], [0.5, '50'], [1, '100']], palette: [[0, '#1b2b45'], [1, '#f2f4f8']], what: 'Fraction of sky covered, monthly mean.', source: S.r1, limits: 'Reanalysis cloud is the weakest field in the atlas.' },
    ],
  },
  {
    id: 'ocean', name: 'Ocean', blurb: 'The sea surface: its temperature, its ice and the currents that move heat poleward.',
    layers: [
      { id: 'ice', name: 'Sea ice', tier: 'climatology', on: true, what: 'Sea ice in a typical year, growing and shrinking at both poles in opposite seasons. The edge is drawn where the extent equals the 1991–2020 mean for the month; inside it is the mean concentration.', source: S.nsidc + ' Lake ice (Great Lakes, Ladoga): ' + S.oisst, limits: 'The edge is placed so that the extent matches NSIDC’s mean, so that agreement is by construction; the independent check is each of the 720 monthly grids on its own, which the atlas’s raster reproduces within 1% (worst 3.7%). Concentration inside the edge is diluted by open years: ice area runs up to 15% under NSIDC’s in the Antarctic summer. Lake ice comes from a different source that overstates it; Baikal, Great Bear, the Caspian and the Sea of Azov are missing from both and never freeze here.' },
      { id: 'currents', name: 'Surface currents', tier: 'climatology', on: true, what: 'Tracers in the mean current at 5 m depth: the gyres, the western boundary currents and the Circumpolar Current.', source: S.godas, limits: 'No data north of 65°N or south of 74°S; nothing is drawn there. A 1° model does not resolve eddies.' },
    ],
    lenses: [
      { id: 'sst', name: 'Sea-surface temperature', tier: 'climatology', units: '°C', ticks: [[0.059, '0'], [0.353, '10'], [0.647, '20'], [0.941, '30']], palette: [[0, '#1c2a78'], [0.2, '#2b7bd0'], [0.45, '#49c6c0'], [0.65, '#c9e27a'], [0.82, '#f6b34a'], [1, '#d43d2a']], what: 'Mean temperature of the sea surface for this time of year.', source: S.oisst },
      { id: 'ice', name: 'Ice concentration', tier: 'climatology', units: '%', ticks: [[0.15, '15'], [0.5, '50'], [1, '100']], palette: [[0, '#3a6f9f'], [1, '#ffffff']], what: 'Fraction of the sea surface covered by ice.', source: S.nsidc },
    ],
  },
  {
    id: 'solid', name: 'Solid Earth', blurb: 'The ground itself: its shape, the plate edges it is breaking along, and where it shakes and erupts.',
    layers: [
      { id: 'plates', name: 'Plate boundaries', tier: 'static', on: false, what: 'The edges of the tectonic plates. Subduction zones are drawn heavier.', source: S.pb },
      { id: 'quakes', name: 'Earthquakes 2000–2025', tier: 'static', on: false, what: 'Every earthquake of magnitude 6 and above in the instrumental catalogue since 2000, sized by magnitude and coloured by depth.', source: S.usgs },
      { id: 'quakesLive', name: 'Earthquakes, past 30 days', tier: 'live', on: true, what: 'Earthquakes of magnitude 4.5 and above in the past month; the newest pulse.', source: 'USGS real-time feed. Public domain.', limits: 'Shown only while the clock is at the present.' },
      { id: 'volcanoes', name: 'Volcanoes', tier: 'static', on: false, what: 'Volcanoes with known or suspected eruptions in the Holocene.', source: S.ncei },
    ],
    lenses: [
      { id: 'elev', name: 'Elevation and depth', tier: 'static', units: 'm', ticks: [[0.03, '−8000'], [0.167, '−4000'], [0.5, '0'], [0.696, '1000'], [0.84, '3000'], [0.98, '6000']], palette: [[0, '#0b1a4a'], [0.2, '#1d4f9a'], [0.4, '#63a9d6'], [0.495, '#bfe3ef'], [0.505, '#3f7f4f'], [0.6, '#a8b96a'], [0.72, '#d9c489'], [0.85, '#a9785a'], [0.95, '#e6e0dc'], [1, '#ffffff']], what: 'Height of the land and depth of the sea floor.', source: S.etopo },
    ],
  },
  {
    id: 'life', name: 'Biosphere', blurb: 'The living surface: snow retreating, land greening and browning through the year.',
    layers: [],
    lenses: [
      { id: 'green', name: 'Greenness (proxy)', tier: 'modelled', units: '', ticks: [[0, 'bare'], [1, 'green']], palette: [[0, '#b9a57a'], [0.4, '#b7b96a'], [0.7, '#4f9a4a'], [1, '#0f5a2a']], what: 'How green the land surface looks this month, from the visible colour of the reflectance field.', source: 'Derived from ' + S.bmng, limits: 'This is a visible-light proxy, not NDVI and not a measurement of vegetation. A satellite vegetation index is on the list of things to add.' },
    ],
    note: 'The land surface itself is this system’s main layer: it is always on, and it changes with the months.',
  },
  {
    id: 'human', name: 'Humanity', blurb: 'Eight billion people, where they live, what they light, where they move and what they burn.',
    layers: [
      { id: 'lights', name: 'Night lights', tier: 'static', on: true, what: 'Electric light seen from orbit, switched on by the model’s own night.', source: S.bm, limits: 'Lights measure electricity, not people. Compare with Population before reading dark as empty.' },
      { id: 'borders', name: 'Borders', tier: 'static', on: true, what: 'International boundaries as administered on the ground. Disputed boundaries and claim lines are dashed.', source: S.ne, limits: 'About thirty areas are contested. Each has its own card naming the claimants.' },
      { id: 'labels', name: 'Names', tier: 'static', on: true, what: 'Countries, cities, seas and landforms. English name first; the local name second on cards where the source carries one.', source: S.ne },
      { id: 'ships', name: 'Shipping', tier: 'modelled', on: true, what: 'Tracers running along the sea lanes. The lanes are measured; the motion along them is modelled.', source: 'Lanes: ' + S.ais, limits: 'These are not individual ships and not today’s traffic.' },
      { id: 'flights', name: 'Air traffic', tier: 'modelled', on: true, what: 'Aircraft on great circles between large airports. The number aloft rises and falls with local time, so the traffic follows the Sun.', source: S.oa, limits: 'A gravity model on catchment population and national income, not a schedule. It cannot reproduce hub airlines.' },
      { id: 'power', name: 'Power stations', tier: 'static', on: false, what: 'Power stations of 20 MW and above, coloured by fuel and sized by capacity.', source: S.wri, limits: 'The database is incomplete for wind and solar after about 2018.' },
      { id: 'rivers', name: 'Rivers', tier: 'static', on: false, what: 'Major river centrelines.', source: S.ne },
      { id: 'graticule', name: 'Graticule', tier: 'static', on: false, what: 'Meridians and parallels every 15°.', source: 'Computed.' },
    ],
    lenses: [
      { id: 'pop', name: 'Population density', tier: 'static', units: 'people/km²', ticks: 'log:pop:1,10,100,1000,10000', palette: [[0, '#1a1030'], [0.3, '#5a1f6e'], [0.55, '#c13a6a'], [0.78, '#f58a4b'], [1, '#fff2b0']], what: 'Where people live, at about 10 km.', source: S.ghsl, limits: 'Gridded population products disagree by up to a factor of two in rural cells; national totals agree.' },
      { id: 'lights', name: 'Light emitted', tier: 'static', units: '', ticks: [[0.1, 'dim'], [1, 'bright']], palette: [[0, '#201a10'], [0.5, '#f0a03a'], [1, '#fffbe0']], what: 'The night-lights field on its own, day or night.', source: S.bm },
      { id: 'co2', name: 'Fossil CO₂ emissions', tier: 'static', units: 't/km²/yr', ticks: 'log:co2:10,100,1000,10000,100000', palette: [[0, '#20242c'], [0.35, '#6b4a2a'], [0.6, '#c1602a'], [0.8, '#f0a03a'], [1, '#fff0c0']], what: 'Carbon dioxide from fossil fuel and industry, where it is emitted.', source: S.edgar, limits: 'Annual total; no seasonal or daily cycle.' },
      { id: 'ships', name: 'Shipping density', tier: 'static', units: '', ticks: [[0.05, 'few'], [1, 'busiest']], palette: [[0, '#0c2a4a'], [0.4, '#1f7fb0'], [0.7, '#62d5d0'], [1, '#f6ffe8']], what: 'How many ship positions were reported in each cell over seven years.', source: S.ais },
    ],
  },
];

export const LAYERS = Object.fromEntries(SYSTEMS.flatMap((s) => s.layers.map((l) => [l.id, { ...l, system: s.id }])));
export const LENS_DEFS = Object.fromEntries(SYSTEMS.flatMap((s) => s.lenses.map((l) => [l.id, { ...l, system: s.id }])));
export const PALETTE_ROWS = ['temp', 'precip', 'slp', 'wind', 'cloud', 'sst', 'ice', 'pop', 'co2', 'ships', 'elev', 'green', 'solar', 'lights'];

export function paletteCss(stops) { return `linear-gradient(90deg, ${stops.map(([t, c]) => `${c} ${(t * 100).toFixed(1)}%`).join(', ')})`; }

/** The palette texture: 256 x 16, one row per lens in PALETTE_ROWS order. */
export function paletteCanvas() {
  const c = document.createElement('canvas'); c.width = 256; c.height = 16;
  const ctx = c.getContext('2d');
  PALETTE_ROWS.forEach((id, row) => {
    const g = ctx.createLinearGradient(0, 0, 256, 0);
    for (const [t, col] of LENS_DEFS[id].palette) g.addColorStop(t, col);
    ctx.fillStyle = g; ctx.fillRect(0, row, 256, 1);
  });
  return c;
}

export const FUEL_COLORS = { Coal: '#8a8f98', Gas: '#f29e4c', Oil: '#b5651d', Nuclear: '#c77dff', Hydro: '#4cc9f0', Wind: '#b8f2e6', Solar: '#ffd60a', Biomass: '#80b918', Geothermal: '#e63946', Waste: '#a68a64', Other: '#cccccc' };
