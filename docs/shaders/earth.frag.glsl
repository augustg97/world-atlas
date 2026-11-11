#version 300 es
// The substrate. Every pixel is a place: it finds its lon/lat (ray-cast globe, or inverse
// Winkel Tripel sheet), reads the fields there, and composes rock, vegetation, snow, water,
// ice, cloud, air and electric light under the real Sun. Nothing here samples a finished
// picture of the Earth; see SCOPE section 3.
precision highp float;
precision highp int;
precision highp sampler2D;
precision highp sampler2DArray;
#include "common.glsl"

in vec2 vNdc;
out vec4 fragColor;

uniform sampler2D uAlbA;           // land reflectance, month 0 (sRGB)
uniform sampler2D uAlbB;           // land reflectance, month 1
uniform float uAlbMix;
uniform sampler2D uRelief;         // RG: companded dz/d(east), dz/d(north)
uniform sampler2D uWaterNight;     // R: water fraction   G: sqrt(night lights)   B: water whose colour is the picture's (0 when not shipped)
uniform sampler2D uElev;           // RG: 16-bit elevation
uniform sampler2D uClouds;         // R: the cloud photograph. GBA: cloud grain tiles, 4 x 2 (sheet, cumulus, frontal)
uniform sampler2DArray uAtmoA;     // u10, v10, t0
uniform sampler2DArray uAtmoB;     // layers 0-11: slp, cloud fraction, precip. Layers 12-23 (when uHasCloudT): ISCCP sky share of
                                   // stratocumulus sheets, of thin broken cloud, and the mean reflectance of the rest.
                                   // One array, not two: WebGL2 guarantees only 16 texture units and this shader uses all 16.
uniform sampler2DArray uOceanA;    // sst, ice, valid (255 sea; 215 inland, sst, modelled ice; 200 inland, observed ice; 180 shore; 150 inland, modelled ice, no sst)
uniform float uHasCloudT;
uniform float uHasGrain;          // 1 when uClouds carries the cloud grain in G, B, A (build/cloud_grain.py)
uniform float uHasGrain2;         // 1 when its bottom row is the second grain file (cumulus over land), not a copy of the top
uniform vec2 uE_deck, uE_cu, uE_light;
uniform sampler2D uCountries;      // R: id  G: disputed  B: map colour index * 32
uniform sampler2D uLens2D;         // the selected static lens field (log-companded 0..1)
uniform sampler2D uLut;            // palettes, 256 wide, one per row of 16
uniform sampler2D uLive;           // observed true-colour mosaic for the clock's date (GIBS)
uniform sampler2D uAurora;         // OVATION probability, 360 x 181
// ---- the focus window: finer fields streamed for the part of the Earth in view (register A2) ----
// Both textures cover the same lon/lat rectangle, given in the canonical uv of every other field:
// uDetWin = (u at the west edge, v at the north edge, width in u, height in v). Row 0 is north.
uniform sampler2D uDetAlb;         // RGB: Blue Marble at 500 m - 2 km a texel, in its own display values, WITH mipmaps. A: night lights, 0..1, when uDetNightW > 0
uniform sampler2D uDetElev;        // R: elevation in metres (float), linear-filterable. G: 1 where streamed, 0 where filled from the shipped field
uniform vec4 uDetWin;
uniform float uDetAlbW, uDetElevW; // 0..1: how much of each to use (0 = not loaded; fade in when ready)
uniform float uDetNightW;          // 0..1: the same for the lights in uDetAlb's alpha (0 when the window was fetched without them)
uniform float uDetS2;              // 1 when uDetAlb is Sentinel-2 (joined by ratio, at a coarser scale), 0 when it is Blue Marble
uniform float uDetAlbLod;          // mip level of uDetAlb whose texel is the shipped albedo's (5 km): log2(5 km / texel km)
uniform vec2 uDetElevPx;           // one texel of uDetElev in window units (1 / width, 1 / height)
uniform vec2 uDetElevM;            // one texel of uDetElev in metres at the equator (east-west, north-south)

uniform vec3 uMonth;               // layer0, fraction, layer1
uniform vec3 uSun;                 // unit vector to the Sun, Earth-fixed
uniform vec3 uMoon;
uniform float uMoonLit;            // illuminated fraction of the Moon's disc
uniform float uHours;              // model time in hours, for cloud transport
uniform float uGmst;               // radians

uniform int uStyle;                // 0 space, 1 atlas
uniform int uLens;                 // see LENS_* below
uniform float uLensAlpha;
uniform float uLensRow;            // palette row
uniform float uHasRelief, uHasElev, uHasLive, uHasClimate, uHasOcean, uHasCountries, uHasWater, uHasAurora;
uniform float uCloudsOn, uNightOn, uAtmoOn, uDaylightOn, uIceOn;
uniform float uReliefLand, uReliefSea;   // vertical exaggeration; shown in the About panel
uniform float uLapse;              // K per km
uniform float uSelCountry;         // selected country id (0 = none)

// encodings, from fields/climate.json (lo, hi)
uniform vec2 uE_u10, uE_v10, uE_t0, uE_slp, uE_cloud, uE_precip, uE_sst, uE_ice;

const int LENS_NONE = 0, LENS_TEMP = 1, LENS_PRECIP = 2, LENS_SLP = 3, LENS_WIND = 4, LENS_CLOUD = 5,
          LENS_SST = 6, LENS_ICE = 7, LENS_POP = 8, LENS_CO2 = 9, LENS_SHIPS = 10, LENS_ELEV = 11,
          LENS_GREEN = 12, LENS_SOLAR = 13, LENS_LIGHTS = 14;

// ---------------------------------------------------------------------------------------------
vec2 gUV, gDx, gDy;
// Texture gradients that survive the antimeridian: take them from whichever of the two
// unwrappings of longitude is continuous here.
void setupUV(vec2 ll) {
  gUV = vec2(ll.x / (2.0 * PI) + 0.5, 0.5 - ll.y / PI);
  vec2 b = vec2(fract(gUV.x + 0.5), gUV.y);
  vec2 ax = dFdx(gUV), ay = dFdy(gUV), bx = dFdx(b), by = dFdy(b);
  if (abs(bx.x) + abs(by.x) < abs(ax.x) + abs(ay.x)) { ax = bx; ay = by; }
  gDx = ax; gDy = ay;
}
vec4 tex(sampler2D s, vec2 uv) { return textureGrad(s, uv, gDx, gDy); }
vec3 arr(sampler2DArray s, vec2 uv) {
  return mix(texture(s, vec3(uv, uMonth.x)).rgb, texture(s, vec3(uv, uMonth.z)).rgb, uMonth.y);
}
// the same, for a second atlas stacked `off` layers further into the array
vec3 arrAt(sampler2DArray s, vec2 uv, float off) {
  return mix(texture(s, vec3(uv, uMonth.x + off)).rgb, texture(s, vec3(uv, uMonth.z + off)).rgb, uMonth.y);
}
float dec(float v, vec2 e) { return e.x + (e.y - e.x) * v; }
vec3 toLinear(vec3 c) { return pow(c, vec3(2.2)); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float hash13(vec3 p) { p = fract(p * 0.1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
float hash12(vec2 p) { vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }

float elevation(vec2 uv) {
  vec2 e = tex(uElev, uv).rg;
  return (e.r * 255.0 * 256.0 + e.g * 255.0) / 65535.0 * 20000.0 - 11000.0;
}

// Value noise in SPACE, read at points of the unit sphere. Noise laid out in longitude and latitude is
// stretched north-south by 1 / cos(latitude): at 45 N the generated cloud came out 1.4 times taller than
// wide and scored four times too one-directional against VIIRS. On the sphere there is no such frame.
float vnoise3(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash13(i), hash13(i + vec3(1.0, 0.0, 0.0)), f.x), mix(hash13(i + vec3(0.0, 1.0, 0.0)), hash13(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
             mix(mix(hash13(i + vec3(0.0, 0.0, 1.0)), hash13(i + vec3(1.0, 0.0, 1.0)), f.x), mix(hash13(i + vec3(0.0, 1.0, 1.0)), hash13(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
}
// Three octaves whose coarsest cell is `km` across on the ground; P is a unit vector. About 0..1, mean 0.500, sd 0.114.
float clumps3(vec3 P, float km) {
  vec3 p = P * (6371.0 / km);
  return 0.50 * vnoise3(p) + 0.30 * vnoise3(p * 2.0 + 7.7) + 0.20 * vnoise3(p * 4.0 + 3.1);
}
// how many octaves the pixel is finer (negative) or coarser (positive) than a wave `km` long
float lodOf(float km) { return log2(max(length(gDx) * 40075.0, length(gDy) * 20037.0) / km + 1e-6); }

const float CLOUD_MAX = 0.96;      // ceiling of the cloud photograph read as reflectance
const float LIGHT_GAIN = 1.0;       // ISCCP mean cloud reflectance to the atlas's: 1 if the two instruments agree
// The photographed cloud at uv: fronts, storms, high cloud. Two things come from two places. HOW MUCH
// light cloud sends back here this month is the satellite climatology's (`light`: each kind's amount times
// the reflectance of its own optical thickness). WHAT SHAPE it takes is the photograph's, moved along the
// monthly-mean surface wind (a two-phase flow map so the distortion stays bounded): the photograph divided
// by its own 1200 km mean, so that it carries pattern and no amount. Shapes are real; positions are MODELLED.
// Without the climatology (`light` < 0) the photograph's own brightness is used, as before.
float cloudAt(vec2 uv, vec2 flowUV, float light) {
  // Hours per flow cycle. It was 30: across a wind shear that drew every cloud out into streaks, and at
  // 2 km a pixel the field was three times as one-directional as real cloud (cloud_texture.py, aniso).
  const float PERIOD = 18.0;
  float ph0 = fract(uHours / PERIOD), ph1 = fract(uHours / PERIOD + 0.5);
  float w0 = 1.0 - abs(2.0 * ph0 - 1.0);
  // slow eastward carry so cycles do not replay in place. Only its fraction is kept: the whole number of
  // turns is hundreds, and subtracting that from uv cost the longitude four digits (seen as vertical streaks)
  float drift = fract(uHours * 2.2e-4);
  vec2 base = vec2(uv.x - drift, uv.y);
  vec2 p0 = base - flowUV * (ph0 - 0.5) * PERIOD, p1 = base - flowUV * (ph1 - 0.5) * PERIOD + vec2(0.37, 0.0);
  float c = mix(textureGrad(uClouds, p1, gDx, gDy).r, textureGrad(uClouds, p0, gDx, gDy).r, w0);
  if (light < 0.0) return clamp(c * 1.15 - 0.05, 0.0, 1.0);
  // mip 8: about 1200 km. At mip 6 (300 km) the division flattened every front and storm cluster: a fifth
  // of the variance was left at 64-256 km where VIIRS has half.
  float cbar = mix(textureLod(uClouds, p1, 8.0).r, textureLod(uClouds, p0, 8.0).r, w0);
  // The photograph's faintest third is haze and sensor floor, not cloud: it is cut off, and the rest scaled
  // up by what was measured to keep the mean exactly (over the photograph, E[max(r - 0.35, 0)] = 0.626).
  // Spreading half of this light evenly over heated wet land (cloud raised by the ground, not gathered by
  // weather) was tried, to answer VIIRS's fine cumulus over the Amazon: against NASA EPIC the disc's contrast
  // error rose from 1.5 to 2.4. The photograph's systems stay whole.
  return clamp(light * LIGHT_GAIN * 1.60 * max(c / max(cbar, 0.06) - 0.35, 0.0), 0.0, 1.0);
}

// ---- the air ----------------------------------------------------------------------------------
// Rayleigh scattering, single-scattered, per channel (about 650 / 550 / 450 nm). One model serves
// the haze over the disc and the glow off the limb, so the limb is as thin as the real air is:
// scale height 8 km. Scored against NASA EPIC by Research/modeling/epic_compare.py (register A1).
const vec3 TAU_R = vec3(0.045, 0.100, 0.240);      // vertical optical depth of a clear atmosphere
const float SUN_E = 1.55;                          // the Sun's strength in the units the surface is lit in
const float AIR_MS = 1.00;                         // gain on the single-scattered light. Last round needed 1.25: it was making up for a low exposure
const float H_AIR = 0.001256;                      // 8 km in Earth radii
// relative air mass along a ray at cosine `mu` from the vertical: Kasten & Young (1989); about 38 at the horizon
float airmass(float mu) {
  float h = degrees(asin(clamp(mu, 0.0, 1.0)));
  return 1.0 / (max(mu, 0.0) + 0.50572 * pow(6.07995 + h, -1.6364));
}
float rayleighPhase(float c) { return 0.1875 * (1.0 + c * c); }   // (3/16)(1 + cos^2): radiance factor per unit of scattering
// Aerosol: the haze of dust, salt and smoke in the lowest two kilometres. A global-mean optical depth of
// 0.13 at 550 nm, nearly white, thrown mostly forward with a small rise straight back (where EPIC looks from).
const vec3 TAU_A = vec3(0.110, 0.130, 0.160);
const float AER_W = 0.93;                          // single-scattering albedo
const float AIR_ABOVE_HAZE = 0.78;                 // share of the air column above 2 km (scale height 8 km)
float hg(float g, float c) { return (1.0 - g * g) / pow(1.0 + g * g - 2.0 * g * c, 1.5); }
// c is the cosine of the scattering angle: -1 straight back toward the Sun
float aerosolPhase(float c) { return 0.25 * (0.9 * hg(0.75, c) + 0.1 * hg(-0.3, c)); }
// Ozone is NOT drawn. A 300 Dobson column takes 3% of a vertical green beam and a third of a grazing
// one, which would turn the limb lilac. It was tried: EPIC's green-to-red ratio is 1.04-1.06 from the
// centre of the disc to the edge, so the reference carries no such tint, and neither does the atlas.
const vec3 SKY_L = vec3(0.115, 0.165, 0.275);      // skylight on the ground, in the Sun's units
const vec3 TRANS_K = vec3(0.040, 0.095, 0.225);    // reddening of sunlight through a long air path
// Clear deep water: the light that comes back out of it is 2-3% in the blue, under 1% in the green and
// almost nothing in the red (open-ocean remote-sensing reflectance times pi), plus the reflected sky.
const vec3 SEA_DEEP = vec3(0.001, 0.010, 0.020);
const vec3 SKY_REF = vec3(0.22, 0.36, 0.60);

// ---- scene light to display -------------------------------------------------------------------
// One exposure and one gamma, with a knee so glints and the Sun roll off instead of clipping.
// Fitted to NASA EPIC's natural-colour product at targets whose reflectance is known without
// reference to this atlas: deep convective cloud tops (0.9) and cloud-free deep ocean (Rayleigh
// scattering, computed). The Libya-4 calibration site is the check. Research/modeling/epic_anchors.py.
const float EXPO = 0.700, GAMMA = 1.63;
const float KNEE = 0.85;
vec3 display(vec3 c) {
  vec3 s = max(c, 0.0) * EXPO;
  s = mix(s, KNEE + (1.0 - KNEE) * tanh((s - KNEE) / (1.0 - KNEE)), step(KNEE, s));
  return pow(s, vec3(1.0 / GAMMA));
}
// the scene value that will be displayed as d: palettes and map inks are authored in display values
vec3 fromDisplay(vec3 d) { return pow(d, vec3(GAMMA)) / EXPO; }
const float WIND_SPREAD = 4.5;     // m/s, day-to-day spread of the wind about its monthly mean vector
const float LAND_LS = 0.30;        // share of the ground's light that follows Lommel-Seeliger (rough, self-shadowing) rather than Lambert
const float CLOUD_MU = 0.75;       // the Sun height (cosine) at which the photograph's brightness IS the reflectance
const float NEAR_EXPOSURE = 1.7;   // exposure gain at the zoom floor, by day (see the end of main). BY EYE: a city reads; white roofs do not clip
const float NIGHT_SHIPPED = 0.53;  // the streamed lights' value at which the shipped field is at full scale (js/detail.js, nightLight)
const vec3 NIGHT_NEAR = vec3(0.085, 0.10, 0.14);   // the lifted night ground, close in (see nearT). BY EYE: the land reads, the lights still lead
const float NIGHT_GAIN = 3.0;      // faint light (cities, moonlight, stars, aurora) is not scored by a daylit photograph; this keeps it where it was set by eye

// Cumulus over humid land. Through the morning the ground heats, the air above it overturns and
// small clouds stud every vegetated region until evening; deserts and the open sea stay clear of
// them. Coverage follows the month's rainfall and the local solar time. The cells are the cloud
// photograph again at nine times the frequency (about 1 km a texel), cut at the level that gives
// the wanted coverage: `th` is the texture's own measured quantile curve. MODELLED.
// Why it exists: against NASA EPIC the clearest twentieth of vegetated land was 25 display levels
// brighter than bare ground under clear air, in every latitude band, while desert and ocean matched.
const float CUMULUS_COVER = 0.20;  // fallback only (no cloud-kind field loaded): afternoon cover over the wettest land
const float DECK_R = 0.50;         // reflectance of sheet cloud where there is one (ISCCP: sheet light over sheet share)
const float LAND_CU_SHARE = 0.2;   // share of 'all other cloud' over heated wet land drawn as small cumulus. FITTED to EPIC's clear-ground medians over the Amazon and the Congo (four values); VIIRS is the check
const float CU_FILL = 0.28;        // share of a satellite pixel called "cumulus" that cloud really fills: its 0.14 reflectance over a cell's 0.5
const float CLOUD_SLANT = 0.5;     // how fast the gaps in broken cloud close as the view tilts (towers about half as tall as wide)
const float CLOUD_OPP = 0.50;      // extra brightness of broken cloud seen from the Sun's side. Amplitude from EPIC (4-12 degrees
                                   // from the Sun); it must be nearly gone by 30 degrees, where VIIRS looks and needs none: width 25

// ---- cloud grain ------------------------------------------------------------------------------
// Closer than the cloud photograph resolves (10 km) the atlas knows how much cloud there is and not its
// shape. The shape is taken from real cloud: three scenes photographed by VIIRS at 2 km a pixel, each
// turned into an ORDERING field (build/cloud_grain.py). A pixel's value, 0 to 1, is its rank among its
// neighbours: the answer to "if cloud covered a share p of this sky, would this pixel be under it?" is
// "if its rank is above 1 - p". Amount is still the climatology's; which pixels, and so every cell, fibre
// and ragged edge, is the photograph's. Ranks are uniform, so a cut at 1 - p covers p with nothing to
// tune, and the mean does not move with zoom. x: sheet. y: cumulus. z: frontal.
const float GRAIN_N = 19.568;      // grain tiles round the equator: one tile is 2048 km, 2 km a texel
// One reading of a tile. It is laid along a parallel with a whole number of tiles round it, so it closes
// on itself east-west; `turned` reads it a quarter turn round, for the second layout below. The texture
// holds two ROWS of tiles (row 0: sheet, cumulus, frontal; row 1: cumulus over land), each four tiles
// wide. Across a row the sampler's own wrap carries from tile to tile. Up and down there is no wrap to
// lean on, since the other row is a different cloud: the tile is wrapped by hand inside its own row, one
// texel clear of the row's edge (the tiles are built to close on themselves, so the join is a two-texel
// skip and no more). Reading it mirrored, there and back, was tried first: it turned every cloud street
// to the opposite slant every 2048 km, and the trades lost their direction (0.07 to 0.04, VIIRS 0.13).
const float GRAIN_EDGE = 0.0005;   // one texel of 2048
vec3 grainTile(vec2 uvd, float band, bool turned, float row) {
  float n = max(1.0, floor(GRAIN_N * cos(radians(band * 6.0)) + 0.5));
  float along, across; vec2 dA, dC;                       // tiles along the row, tiles up and down it, and their gradients
  if (turned) { along = uvd.y * GRAIN_N * 0.5 + 1.48; across = uvd.x * n + 0.61; dA = vec2(gDx.y, gDy.y) * GRAIN_N * 0.5; dC = vec2(gDx.x, gDy.x) * n; }
  else        { along = uvd.x * n;                    across = uvd.y * GRAIN_N * 0.5; dA = vec2(gDx.x, gDy.x) * n; dC = vec2(gDx.y, gDy.y) * GRAIN_N * 0.5; }
  float span = 0.5 - 2.0 * GRAIN_EDGE;
  vec2 q = vec2(along * 0.25, row * 0.5 + GRAIN_EDGE + span * fract(across));
  return textureGrad(uClouds, q, vec2(dA.x * 0.25, dC.x * span), vec2(dA.y * 0.25, dC.y * span)).gba;
}
// Two rank fields cross-faded. A plain average of two unrelated fields crowds toward 0.5 and a cut would
// no longer cover what it should; dividing by the length of the weights keeps the spread.
vec3 rankMix(vec3 a, vec3 b, float w) { return 0.5 + ((a - 0.5) * (1.0 - w) + (b - 0.5) * w) / sqrt((1.0 - w) * (1.0 - w) + w * w); }
// The grain at a place. Laid out in longitude and latitude a tile would be stretched east-west by
// 1 / cos(latitude), so each 6-degree band of latitude has its own whole number of tiles and neighbours
// are faded into each other. And a tile repeats every 2048 km: two layouts, one a quarter turn round,
// take turns in irregular patches some 900 km across, so no cloud is seen twice in one view.
vec3 grainLay(vec2 uvd, bool turned, float row) {
  float b = (0.5 - uvd.y) * 30.0, j = floor(b), w = smoothstep(0.25, 0.75, b - j);
  if (w < 0.004) return grainTile(uvd, j, turned, row);
  if (w > 0.996) return grainTile(uvd, j + 1.0, turned, row);
  return rankMix(grainTile(uvd, j, turned, row), grainTile(uvd, j + 1.0, turned, row), w);
}
vec3 grainAt(vec2 uvd, vec3 Pd, float row) {
  float w = smoothstep(0.46, 0.54, clumps3(Pd + 0.43, 900.0));
  if (w < 0.004) return grainLay(uvd, false, row);
  if (w > 0.996) return grainLay(uvd, true, row);
  return rankMix(grainLay(uvd, false, row), grainLay(uvd, true, row), w);
}
// Cloud whose light, averaged over all the sky, is `a`: where it is, and how bright. r is the grain's
// rank here. Two numbers describe a kind of cloud, both MEASURED on eighteen VIIRS scenes at 2 km a pixel,
// none of them a scene the audit scores against (build/cloud_grain.py KIND): m0, the mean reflectance of
// the cloudy part of a broken field, and `ratio`, its brightest core over that mean, chosen so the pieces
// have the photographs' spread of brightness. So the cloud covers a / m0 of the sky until that is all of
// it, and after that it thickens. A piece brightens from its edge to its core as the rank does, with the
// exponent that makes the pieces average exactly `a`: real cloud is mostly thin with a few bright cores,
// not flat white pieces on clear sea.
//                 m0     ratio
//   sheet        0.35    1.5
//   cumulus      0.33    1.8
//   frontal      0.45    1.6
//   land cumulus 0.38    1.95
float pieces(float r, float a, float m0, float ratio) {
  if (a < 1e-4) return 0.0;                    // no light asked for: no cloud (and no 0 / 0 below)
  float p = clamp(a / m0, 0.02, 1.0);
  float m = min(a / p, CLOUD_MAX);
  float peak = min(CLOUD_MAX, m * ratio);
  float t = clamp((r - (1.0 - p)) / p, 0.0, 1.0);
  return peak * pow(max(t, 1e-4), peak / m - 1.0) * step(1e-4, t);
}

// The cloud photograph resolves about 10 km. A value of 0.3 there is not a thin veil over everything:
// seen closer it is broken cloud, some of the sky covered and the rest clear. `a` is the reflectance the
// far view sees; `fade` is 1 where a pixel is too coarse to show pieces (EPIC resolves 10-18 km and shows
// middling brightness widely there: cut into pieces, the far view came out more two-toned than the
// photographs).
// `conv`: how far this is cloud heaped up over heated wet land (0..1) and not the layered cloud of a
// storm: the land-cumulus numbers, not the frontal ones.
float broken(float r, float a, float fade, float conv) {
  if (fade > 0.99 || a < 0.01) return a;
  return mix(pieces(r, a, mix(0.45, 0.38, conv), mix(1.6, 1.95, conv)), a, fade);
}

// Thin broken low cloud: fair-weather cumulus over land, trade cumulus over the sea. `amount` is the
// share of sky it covers. Single cells are 1-2 km, under the 2 km zoom floor; what a pixel that size
// can show is how they gather into knots, arcs and streets, which is the grain's. Where the fields are,
// tens of km across, is MODELLED: the cloud photograph at 5 and 13 times its frequency (its mean in this
// band is 0.194, so each envelope averages 1).
float cumulusAt(vec2 uv, float amount) {
  if (amount < 0.004) return 0.0;
  vec2 q = vec2(uv.x * 5.0 + 0.13, 0.25 + 0.5 * abs(fract(uv.y * 5.0) * 2.0 - 1.0));
  float env = clamp(textureGrad(uClouds, q, gDx * 5.0, gDy * 5.0).r / 0.194, 0.0, 2.4);
  vec2 q2 = vec2(uv.x * 13.0 + 0.61, 0.25 + 0.5 * abs(fract(uv.y * 13.0 + 0.3) * 2.0 - 1.0));
  float env2 = clamp(textureGrad(uClouds, q2, gDx * 13.0, gDy * 13.0).r / 0.194, 0.0, 2.4);
  float e = 0.5 * (env + env2);                                    // fields of two sizes, 30 and 80 km
  // Sharpened: fields with clear air between them, not a veil (1.2 is the mean of e^1.5, so the mean share
  // is kept). Spreading the share evenly was tried when the grain arrived, since the grain gathers cells
  // into knots itself: NASA EPIC's darkest fifth of open ocean then came out 3 levels too bright in every
  // channel. The clear air between fields is real at 16 km, and stays.
  float c = min(0.60, amount * e * sqrt(e) / 1.2);
  // a crowded field holds taller, thicker cloud: reflectance from 0.45 (scattered fair-weather cells) to 0.70
  float a = c * mix(0.45, 0.70, smoothstep(0.15, 0.50, c));
  return a;                                                        // the light of the field; its pieces are cut by the caller
}

// Stratocumulus: the sheets that roof the cold eastern sides of the subtropical oceans. Seen from above
// a sheet is a pavement of cells some 30 km across: closed where it is thick, open rings and scattered
// cells where it thins. `amount` is the share of sky under sheet cloud (ISCCP); the cells are the grain's.
float deckAt(vec3 Pd, float amount) {
  if (amount < 0.02) return 0.0;
  float c = clamp(amount * (0.55 + 0.9 * clumps3(Pd, 480.0)), 0.0, 1.0); // the sheet's own weather: pockets and clearings. MODELLED
  // Light: the share of sky under sheet times the reflectance of a sheet where there is one. That is
  // 0.50 in ISCCP wherever sheets cover more than 0.42 of the sky (0.45-0.51 over the Peruvian, Namibian
  // and Californian decks). The law here before, written by eye, sent back 0.37 off Peru where ISCCP
  // has 0.25, and the scene there was 0.12 brighter than VIIRS.
  // A sheet thinner than a fifth of the sky is not drawn: ISCCP's thin-sheet share is everywhere, and
  // VIIRS agrees without it.
  return c * DECK_R * smoothstep(0.18, 0.42, c);
}

// ---- the ground's albedo from Blue Marble --------------------------------------------------
// Blue Marble is a picture, not a reflectance map: its values are close to LINEAR in reflectance,
// with a different gain in each channel (about 465, 620 and 720 levels per unit of red, green and
// blue reflectance) so that land reads green on a screen. Read as sRGB it gave forest and savanna a
// third of their real brightness. The table is what NASA EPIC's clear-sky view implies, pixel value
// by pixel value, over 170,000 land pixels in six frames (Research/modeling/land_transfer.py):
// fitted on three frames it halves the error on the other three. Above the data it continues each
// channel's line; white stands for snow, which the picture clips, and gets snow's albedo.
const vec3 ALB_LUT[9] = vec3[](vec3(0.000, 0.000, 0.000), vec3(0.070, 0.049, 0.026), vec3(0.120, 0.097, 0.063), vec3(0.172, 0.148, 0.099), vec3(0.229, 0.195, 0.147), vec3(0.284, 0.254, 0.188), vec3(0.369, 0.361, 0.230), vec3(0.440, 0.444, 0.272), vec3(0.510, 0.527, 0.314));
const float SNOW_ALB = 0.90;
float lut1(float x, int c) {
  float t = clamp(x, 0.0, 1.0) * 8.0;
  int i = int(min(floor(t), 7.0));
  return mix(ALB_LUT[i][c], ALB_LUT[i + 1][c], t - float(i));
}
vec3 albedoOf(vec3 c) {
  vec3 a = vec3(lut1(c.r, 0), lut1(c.g, 1), lut1(c.b, 2));
  return mix(a, vec3(SNOW_ALB), smoothstep(0.80, 0.96, min(c.r, min(c.g, c.b))));
}

vec3 palette(float v) { return texture(uLut, vec2(clamp(v, 0.002, 0.998), (uLensRow + 0.5) / 16.0)).rgb; }

// stars, the Sun and the Moon, for rays that leave the planet
vec3 space(vec3 rd, float limbH, vec3 tangentN) {
  vec3 col = vec3(0.0);
  float cg = cos(uGmst), sg = sin(uGmst);
  vec3 d = vec3(cg * rd.x - sg * rd.y, sg * rd.x + cg * rd.y, rd.z);      // inertial frame: stars do not turn with the Earth
  vec3 g = floor(d * 260.0);
  float h = hash13(g);
  if (h > 0.9972) {
    vec3 c = (g + 0.5) / 260.0;
    float fall = smoothstep(0.0013, 0.0, length(d - c));
    col += vec3(0.75, 0.82, 1.0) * fall * (0.25 + 4.0 * (h - 0.9972) / 0.0028) * 0.45 * NIGHT_GAIN;
  }
  float sd = dot(rd, uSun);
  float sunAng = length(cross(rd, uSun));                       // sine of the angle; exact near zero where a dot product is not
  if (sd > 0.0) col += vec3(1.0, 0.95, 0.85) * (smoothstep(0.0050, 0.0044, sunAng) * 40.0 + exp(-sunAng * sunAng / 0.00035) * 1.1 + exp(-sunAng / 0.055) * 0.10);
  float md = dot(rd, uMoon);
  const float RM = 0.0048;
  if (md > cos(RM)) {
    vec3 off = (rd - uMoon * md) / RM;
    float r2 = dot(off, off);
    if (r2 < 1.0) {
      vec3 nrm = normalize(off - uMoon * sqrt(1.0 - r2));
      col = vec3(0.62, 0.60, 0.56) * (0.02 + max(dot(nrm, uSun), 0.0)) * 2.2;
    }
  }
  if (uAtmoOn > 0.5 && limbH < 0.08) {
    // The limb: a ray that misses the ground still crosses air. Its grazing optical depth is the
    // vertical one times sqrt(2 pi R / H), about 70, falling with the tangent height's scale height.
    // Far away the whole glow is thinner than a pixel, so it is spread to half a pixel and dimmed
    // by the same factor: the light is conserved and the edge is anti-aliased.
    float sunT = dot(tangentN, uSun);
    float px = sqrt(max(dot(uCamPos, uCamPos) - 1.0, 0.0)) * 2.0 * uTanHalfFov / uViewport.y;
    float He = max(H_AIR, 0.5 * px);
    float dens = exp(-limbH / He);
    float amS = airmass(sunT);
    vec3 lit = exp(-TAU_R * dens * amS) * smoothstep(-0.12, 0.03, sunT);     // sunlight that reaches the tangent point
    col += SUN_E * AIR_MS * rayleighPhase(dot(uSun, rd)) * (38.0 / (38.0 + amS)) * (1.0 - exp(-TAU_R * 70.7 * dens)) * lit * (H_AIR / He);
  }
  return col;
}

void main() {
  // ---- where is this pixel? -----------------------------------------------------------------
  vec2 ll; vec3 N; vec3 V; vec3 rd = vec3(0.0); bool hit; float limbH = 0.0;
  if (uView == 0) {
    float aspect = uViewport.x / uViewport.y;
    rd = normalize(uCamBasis * vec3(vNdc.x * uTanHalfFov * aspect, vNdc.y * uTanHalfFov, 1.0));
    float b = dot(uCamPos, rd);
    float disc = b * b - (dot(uCamPos, uCamPos) - 1.0);
    hit = disc > 0.0 && b < 0.0;
    vec3 P;
    if (hit) { P = uCamPos + (-b - sqrt(disc)) * rd; }
    else { vec3 q = uCamPos - b * rd; limbH = b < 0.0 ? length(q) - 1.0 : 9.0; P = q; }
    N = normalize(P);
    V = -rd;
    ll = vecToLonLat(N);
  } else {
    vec2 xy = uMapCenter + vNdc * uViewport * 0.5 * uMapScale;
    ll = wtInverse(xy, hit);
    N = lonLatToVec(ll);
    V = N;
  }
  setupUV(ll);
  vec2 uv = gUV;
  float dither = (hash12(gl_FragCoord.xy) - 0.5) / 255.0;

  if (!hit) {
    vec3 bg;
    if (uView == 0) bg = uStyle == 0 ? space(rd, limbH, N) : vec3(0.030, 0.045, 0.075) + vec3(0.25, 0.42, 0.7) * exp(-limbH / 0.02) * 0.25;
    else bg = uStyle == 0 ? vec3(0.010, 0.014, 0.026) : vec3(0.030, 0.045, 0.075);
    bg = uStyle == 0 ? display(bg) : pow(bg / (1.0 + bg), vec3(1.0 / 2.2));
    fragColor = vec4(bg + dither, 1.0);
    return;
  }

  // ---- read the fields ----------------------------------------------------------------------
  vec3 E = vec3(-sin(ll.x), cos(ll.x), 0.0);                       // local east
  vec3 Nn = vec3(-sin(ll.y) * cos(ll.x), -sin(ll.y) * sin(ll.x), cos(ll.y));   // local north
  float coslat = max(cos(ll.y), 0.02);

  vec3 bm = mix(tex(uAlbA, uv).rgb, tex(uAlbB, uv).rgb, uAlbMix);     // Blue Marble's own display values
  // The focus window. Position in it, 0..1 each way (longitude wraps), and a weight that fades to nothing
  // over the outer 6% so the window never shows an edge.
  vec2 dw = vec2(fract(uv.x - uDetWin.x), uv.y - uDetWin.y) / uDetWin.zw;
  float inWin = (uDetAlbW + uDetElevW) > 0.0 ? smoothstep(0.0, 0.06, min(min(dw.x, 1.0 - dw.x), min(dw.y, 1.0 - dw.y))) : 0.0;
  float sceneL = luma(bm);          // how bright this ground is in the shipped picture, at 5 km: what the close-in exposure meters on
  float nightFine = 0.0, nightTex = 1.0;
  if (inWin * uDetAlbW > 0.0) {
    // Frequency split. The month's colour stays the shipped field's (it is the right SEASON); the fine
    // structure is the streamed picture's, with its own coarse part taken out so nothing is counted twice.
    vec4 fineT = textureGrad(uDetAlb, dw, gDx / uDetWin.zw, gDy / uDetWin.zw);
    // HOW THE STREAMED PICTURE AND THE SHIPPED MONTH ARE JOINED.
    // Blue Marble (down to a 0.49 km texel) is the shipped field's own picture: the month's colour stays the
    // shipped field's and the structure finer than its 5 km is ADDED, with the streamed picture's own coarse
    // part taken out so that nothing is counted twice.
    // Sentinel-2 (finer) is another camera with more contrast, and its windows are seen from much nearer:
    //  - added, its sand went past full scale and its fields below zero, and the clamp turned a desert lime and a
    //    delta blue-black. It is joined by RATIO instead: the picture itself, times the shipped month's colour over
    //    the picture's own, both taken coarse. Hue is kept and nothing can clip that the picture did not;
    //  - "coarse" is the shipped field's 5 km wherever that is safe, so each kind of ground gets its own month's
    //    colour (one tint for a whole screen turned the desert beside the Nile delta olive). It is NOT safe near
    //    water: the shipped colour there is a 5 km blur of land and sea, and a coast seen at 20 m a pixel had brown
    //    bleeding 200 pixels out to sea. Within reach of water (the shipped water fraction, itself a 5 km field)
    //    the join is made coarser, 10 km to 39 km with the zoom: wider than the screen at those scales. And there
    //    it carries BRIGHTNESS only: the shipped picture's sea is one dark navy fill, and a colour ratio taken
    //    across land and that fill turned Manhattan and both its rivers olive.
    float boost = uDetS2 > 0.5 ? clamp(uDetAlbLod - 3.0, 1.0, 3.0) : 0.0;
    vec3 lowDet = textureLod(uDetAlb, dw, uDetAlbLod).rgb;
    vec3 joined = bm + fineT.rgb - lowDet;
    if (uDetS2 > 0.5) {
      vec2 lod = boost + log2(vec2(float(textureSize(uAlbA, 0).x), float(textureSize(uAlbB, 0).x)) / 8192.0);   // a preview month is a smaller texture
      vec3 shipC = mix(textureLod(uAlbA, uv, max(lod.x, 0.0)).rgb, textureLod(uAlbB, uv, max(lod.y, 0.0)).rgb, uAlbMix);
      vec3 detC = textureLod(uDetAlb, dw, uDetAlbLod + boost).rgb;
      float nearWater = smoothstep(0.01, 0.12, tex(uWaterNight, uv).r);
      vec3 ratio = mix(clamp(bm / max(lowDet, vec3(0.03)), 0.3, 3.0), vec3(clamp(luma(shipC) / max(luma(detC), 0.03), 0.5, 2.0)), nearWater);
      joined = fineT.rgb * ratio;
      lowDet = mix(lowDet, detC, nearWater);
    }
    // past full scale, come back along the colour's own line: clamping each channel alone turned pale sand green
    if (uDetS2 > 0.5) joined /= max(1.0, max(joined.r, max(joined.g, joined.b)) / 0.97);
    nightFine = fineT.a;
    // not under snow: the streamed picture is one month, and summer ground does not show through winter snow
    float snowy = smoothstep(0.70, 0.90, min(bm.r, min(bm.g, bm.b)));
    bm = clamp(mix(bm, joined, inWin * uDetAlbW * (1.0 - snowy)), 0.0, 1.0);
    // What a city's light falls on. From above, a lit city is its streets and roofs sending the light back, so
    // where the ground is drawn finer than the lights are known (0.5 km) the light takes the ground's own pattern:
    // brighter on pale roofs and roads, darker on parks, by the ground's brightness against its surroundings'.
    // The light's AMOUNT stays Black Marble's. Whole at 100 m a device pixel, none by 330 m.
    float texT = (1.0 - smoothstep(-4.3, -2.6, lodOf(2.0))) * inWin * uDetAlbW;
    // (squared: at the first power a river was lit at a third of a street's brightness and the night read as a
    // sepia photograph of the day. Water and parks, at a third of their surroundings by day, fall to a tenth.)
    float gRel = luma(fineT.rgb) / max(luma(lowDet), 0.05);
    // 0.45: ordinary ground returns under half of the unresolved glow and only the palest roofs and roads all of
    // it, so the picture is points and lines of light on dark, as a city is from above, and nothing clips.
    nightTex = mix(1.0, clamp(0.45 * gRel * gRel, 0.03, 1.0), texT);
  }
  vec3 alb = albedoOf(bm);
  vec3 wn = tex(uWaterNight, uv).rgb;
  float water = uHasWater > 0.5 ? smoothstep(0.35, 0.65, wn.r) : 0.0;
  float night = wn.g * wn.g;
  // In the focus window the lights are the streamed picture's outright: it is the picture the shipped field was
  // made from, at 500 m, so there is no season to keep and nothing to count twice.
  // The streamed value runs on into the white cores; NIGHT_SHIPPED of it is the shipped field's full scale (detail.js).
  night = mix(night, min(1.0, nightFine / NIGHT_SHIPPED), inWin * uDetNightW);
  float z = uHasElev > 0.5 ? elevation(uv) : 0.0;
  vec2 grad = vec2(0.0);
  if (uHasRelief > 0.5) {
    vec2 r = clamp((tex(uRelief, uv).rg - 0.5) * 2.0, -0.985, 0.985);
    grad = 0.5 * log((1.0 + r) / (1.0 - r)) / 3.0;                 // atanh / 3 : metres per metre
  }
  if (inWin * uDetElevW > 0.0) {   // (the texture's G channel then decides texel by texel)
    // streamed elevation: height, and slope by central differences (east positive, north positive)
    // G is 1 where the texel is the streamed tiles' own (land) and 0 where the window was filled from the
    // shipped field (sea floor, beyond 85 degrees): there the shipped height and slope stay in charge.
    float wE = inWin * uDetElevW * texture(uDetElev, dw).g;
    // The slope is taken over at least 90 m each way. At 30 m a texel the tiles carry single-texel pits and
    // spikes where the survey met water it could not measure (river surfaces, bridges, dredged slips), and over
    // one texel each shaded as a dark dot on the Nile and the East River. A hill is much longer than 90 m.
    vec2 st = uDetElevPx * clamp(90.0 / uDetElevM, vec2(1.0), vec2(3.0));
    vec2 stM = uDetElevM * clamp(90.0 / uDetElevM, vec2(1.0), vec2(3.0));
    float zE = texture(uDetElev, dw + vec2(st.x, 0.0)).r, zW = texture(uDetElev, dw - vec2(st.x, 0.0)).r;
    float zN = texture(uDetElev, dw - vec2(0.0, st.y)).r, zS = texture(uDetElev, dw + vec2(0.0, st.y)).r;
    vec2 gD = vec2((zE - zW) / (2.0 * stM.x * max(cos(ll.y), 0.02)), (zN - zS) / (2.0 * stM.y));
    grad = mix(grad, gD, wE);
    z = mix(z, texture(uDetElev, dw).r, wE);
  }
  vec3 atA = vec3(0.5, 0.5, 0.6), atB = vec3(0.5, 0.5, 0.2);
  if (uHasClimate > 0.5) { atA = arr(uAtmoA, uv); atB = arr(uAtmoB, uv); }
  vec2 wind = vec2(dec(atA.r, uE_u10), dec(atA.g, uE_v10));
  float windSp = length(wind);
  float cloudFrac = dec(atB.g, uE_cloud);
  vec3 kinds = vec3(0.0, 0.0, -1.0);                                 // sky share of sheet cloud and of thin broken cloud; mean reflectance of the rest
  if (uHasCloudT > 0.5) { vec3 ct = arrAt(uAtmoB, uv, 12.0); kinds = vec3(dec(ct.r, uE_deck), dec(ct.g, uE_cu), dec(ct.b * ct.b, uE_light)); }
  float precip = dec(atB.b * atB.b, uE_precip);
  float slp = dec(atB.r, uE_slp);
  vec3 oc = uHasOcean > 0.5 ? arr(uOceanA, uv) : vec3(0.5, 0.0, 0.0);
  float sst = dec(oc.r, uE_sst);
  float ice = uHasOcean > 0.5 ? dec(oc.g, uE_ice) * step(0.5, oc.b) * uIceOn : 0.0;

  // ---- the Sun here -------------------------------------------------------------------------
  float mu0 = dot(N, uSun);
  float dayF = smoothstep(-0.07, 0.12, mu0);
  float sunE = dot(uSun, E), sunN = dot(uSun, Nn);
  // local solar time (hours) from the hour angle, and the air temperature model
  float lst = 12.0 + atan(sunE, mu0) * (-12.0 / PI);              // the Sun is in the east in the morning
  float aridity = 1.0 - clamp(precip / 4.0, 0.0, 1.0);
  float dtr = mix(0.4, mix(4.0, 9.5, aridity) * (1.0 - 0.45 * cloudFrac), 1.0 - water);   // half-range, K
  float tAir = dec(atA.b, uE_t0) - uLapse * max(z, 0.0) / 1000.0 - dtr * cos((lst - 14.5) * PI / 12.0);

  // ---- clouds -------------------------------------------------------------------------------
  vec2 flowUV = vec2(wind.x / coslat / (2.0 * PI), -wind.y / PI) * (3600.0 / 6371008.8) * 2.5;   // uv per hour, x2.5 so drift reads at global scale
  // How far inside the cloud's own scale the view is: 0 down to about 0.7 km a device pixel, 1 by 0.15 km.
  float nearCam = 1.0 - smoothstep(-3.7, -1.6, lodOf(2.0));
  float cloud = 0.0, cloudSh = 0.0, cloudSun = 0.0, cum = 0.0, deck = 0.0, cumFar = 0.0, deckFar = 0.0;
  float grainFade = 1.0, conv = 0.0, landCu = 0.5; vec3 grain = vec3(0.5);
  // the generated cloud's own frame: the sphere, turned by the same slow eastward carry as the photograph
  float dA = 2.0 * PI * fract(uHours * 2.2e-4), cdA = cos(dA), sdA = sin(dA);
  vec3 Pd = vec3(cdA * N.x + sdA * N.y, -sdA * N.x + cdA * N.y, N.z);
  vec2 sunStep = vec2(sunE / coslat / (2.0 * PI), -sunN / PI);
  if (uCloudsOn > 0.5 && uHasLive < 0.5) {
    // Three kinds of cloud, each drawn its own way: the photograph for fronts, storms and high cloud,
    // a generated pavement for stratocumulus sheets, generated clumps for broken low cloud.
    float sunUp = smoothstep(8.0, 12.5, lst) * (1.0 - smoothstep(17.0, 21.0, lst));
    // By day over wet land the cloud the satellite files under "everything else" is mostly heaped cloud too:
    // at 13:30 over the Amazon VIIRS shows cumulus and little besides, 0.11 of the light, where ISCCP puts
    // 0.02 under cumulus and 0.09 under middle and high types. It is drawn with the cumulus grain there.
    // Warm ground that is not desert: the same rain gate as the cumulus share, and no heaping over cold land.
    conv = (1.0 - water) * smoothstep(0.1, 0.6, precip) * smoothstep(8.0, 22.0, tAir) * sunUp;
    // Over heated wet land by day, half of that cloud's light is drawn as cumulus fields, not through the
    // photograph's systems (LAND_CU_SHARE). The satellite climatology files a sky of small cumulus mostly under
    // middle and high types (over the Amazon at 13:30: 0.02 of the light as cumulus, 0.09 as the rest, where VIIRS
    // shows cumulus and little besides), and drawn through the photograph that light gathers into a few bright
    // clusters with clear forest between. The total is unchanged.
    float moved = LAND_CU_SHARE * conv;
    float restLight = kinds.z < 0.0 ? kinds.z : kinds.z * (1.0 - moved);
    cloud = cloudAt(uv, flowUV, restLight);
    float slant = 1.0 / max(mu0, 0.18);
    cloudSh = cloudAt(uv + sunStep * 0.0035 * slant, flowUV, restLight); // what stands between this ground and the Sun
    cloudSun = cloudAt(uv + sunStep * 0.0016, flowUV, restLight);        // the cloud's own sunward neighbour
    // Broken low cloud. Over land it follows the day: little at dawn, most in the afternoon (the satellite's
    // amount is a daytime mean, so the cycle is scaled to average 1). The satellite also reports thin low
    // cloud over bright desert that is not there: none is drawn where it does not rain.
    float heat = 0.12 + 0.88 * sunUp;
    float cuAmt = uHasCloudT > 0.5 ? kinds.y * CU_FILL * mix(heat / 0.70, 1.0, water) * smoothstep(0.1, 0.6, precip)
                                   : CUMULUS_COVER * (1.0 - water) * smoothstep(0.2, 3.0, precip) * heat;
    // the grain is read once for all three kinds, and only where a pixel is fine enough to show it:
    // whole to 4 km a pixel, gone by 11
    if (uHasGrain > 0.5) grainFade = smoothstep(1.0, 2.5, lodOf(2.0));
    vec2 uvd = vec2(uv.x - fract(uHours * 2.2e-4), uv.y);
    if (grainFade < 0.99) {
      grain = grainAt(uvd, Pd, 0.0);
      // over land, cumulus is the land's: finer cells, everywhere (the sea's cumulus drawn over the Amazon gave
      // fewer, larger, brighter pieces than the real sky). Read only where there is land to need it.
      landCu = (uHasGrain2 > 0.5 && water < 0.99) ? grainAt(uvd, Pd, 1.0).x : grain.y;
    }
    // each kind twice: its light as the far view has it, and cut into the grain's pieces where a pixel can show them
    if (kinds.z > 0.0) cuAmt += moved * kinds.z / 0.45;                   // as a share of sky: a cell reflects 0.45
    cumFar = cumulusAt(uv, cuAmt); deckFar = deckAt(Pd, kinds.x);
    cum = cumFar; deck = deckFar;
    if (grainFade < 0.99) {
      float cuRank = rankMix(vec3(landCu), vec3(grain.y), water).x;        // the land's cumulus on land, the sea's at sea
      cum = mix(pieces(cuRank, cumFar, mix(0.38, 0.33, water), mix(1.95, 1.8, water)), cumFar, grainFade);
      deck = mix(pieces(grain.x, deckFar, 0.35, 1.5), deckFar, grainFade);
    }
    // CLOSER THAN THE CLOUD HAS ANY SHAPE, IT THINS AND GOES. Its finest structure is the grain's 2 km; at 150 m a
    // pixel a cloud is a white slab with a soft edge lying on streets that are drawn to 40 m, and the ground is
    // what that view is for. Whole down to about 0.7 km a device pixel, gone by 0.15. Not the sky as it is: the
    // Clouds card says so (catalog.js). Every use of the cloud below (shadow, haze, the lights it dims) thins with it.
    float cloudNear = 1.0 - nearCam;
    cloud *= cloudNear; cloudSh *= cloudNear; cloudSun *= cloudNear; cum *= cloudNear; deck *= cloudNear; cumFar *= cloudNear; deckFar *= cloudNear;
  }

  // ---- relief normal ------------------------------------------------------------------------
  float kRel = mix(uReliefLand, uReliefSea, water);
  vec3 n = normalize(N - kRel * (grad.x * E + grad.y * Nn));

  vec3 col;
  float lensShade = 1.0;
  if (uStyle == 0) {
    // =============================== Earth from space ========================================
    vec3 trans = exp(-TRANS_K * (1.0 / (max(mu0, 0.0) + 0.055) - 0.948));   // sunlight reddens through a long air path
    vec3 sunL = SUN_E * trans * max(mu0, 0.0);                    // Lambert: the limb of a full disc darkens as the photograph's does
    vec3 skyL = SKY_L * smoothstep(-0.20, 0.30, mu0);
    vec3 moonL = NIGHT_GAIN * vec3(0.010, 0.013, 0.022) * (0.25 + 0.75 * uMoonLit * smoothstep(-0.1, 0.4, dot(N, uMoon))) * (1.0 - dayF);
    float shade = clamp(dot(n, uSun) / max(mu0, 0.10), 0.0, 2.4);
    shade = mix(1.0, shade, smoothstep(-0.02, 0.10, mu0) * (1.0 - water));
    lensShade = shade;
    float lowCloud = 1.0 - (1.0 - cum) * (1.0 - deck);              // low cloud shades what is straight under it
    float shadow = (1.0 - 0.62 * cloudSh) * (1.0 - 0.75 * lowCloud);

    // Rough ground is not a Lambert surface: seen from near the Sun's direction it hides its own
    // shadows and falls off toward the limb more slowly (Lommel-Seeliger). Normalised to 1 with Sun and
    // eye overhead, where the albedo table was measured.
    float nvL = max(dot(N, V), 0.0);
    float rough = (1.0 - LAND_LS) + LAND_LS * 2.0 / (max(mu0, 0.0) + nvL + 1e-3);
    rough = uView == 0 ? min(rough, 1.8) : 1.0;
    // CLOSE IN, THE NIGHT GROUND IS LIFTED, and this is not the night as it is: under a new Moon the land is
    // black and only the lights show, which from this near leaves nothing to place them on. Nearer than about
    // 5 km a pixel the land is lit as by a bright Moon in the north-west (a map's convention for relief), about
    // ten times moonlight. Stated in the lights card (catalog.js). From further out the night is the real one.
    float nearT = 1.0 - smoothstep(-0.4, 1.8, lodOf(2.0));
    vec3 Lnw = normalize(1.1 * N + Nn - E);
    float reliefN = clamp(dot(n, Lnw) / max(dot(N, Lnw), 0.2), 0.0, 2.2);
    vec3 nearL = NIGHT_GAIN * NIGHT_NEAR * nearT * (1.0 - dayF);
    vec3 land = alb * (sunL * shade * shadow * rough + skyL + moonL + nearL * reliefN * (1.0 - 0.5 * cloud));

    // water: one colour, shaded; a shelf tint; sky reflection; Sun glint whose width is the wind's
    float depth = max(-z, 0.0);
    vec3 seaC = mix(SEA_DEEP, vec3(0.018, 0.085, 0.110), 0.75 * exp(-depth / 75.0) * uHasElev);
    // Where Blue Marble shows the water itself and not its ocean fill (shallow banks, river plumes, silty
    // shelves, lakes: fields/shoal.webp), the light the water sends back is the picture's, read through the
    // same table as the land: the Bahama banks are turquoise and the Amazon's mouth is brown because they
    // are. Not where this month's picture is near white there: that is ice, and the ice field draws ice.
    float picWater = wn.b * (1.0 - smoothstep(0.38, 0.55, min(bm.r, min(bm.g, bm.b))));
    seaC = mix(seaC, alb, picWater);
    vec3 sea = seaC * (sunL * shadow * 0.9 + skyL * 1.6 + moonL * 2.0 + nearL * 0.6);
    float nv = max(dot(N, V), 0.0);
    float fres = 0.02 + 0.98 * pow(1.0 - nv, 5.0);
    sea += fres * SKY_REF * smoothstep(-0.15, 0.3, mu0) * 0.55;
    // Cox & Munk (1954) mean-square slope. The field holds the month's mean wind VECTOR, which is
    // slower than the mean wind speed wherever the wind swings about: add the day-to-day spread.
    float s2 = 0.003 + 0.00512 * sqrt(windSp * windSp + WIND_SPREAD * WIND_SPREAD);
    vec3 H = normalize(uSun + V);
    float nh = max(dot(N, H), 1e-3);
    float D = exp(-(1.0 - nh * nh) / (nh * nh) / s2) / (PI * s2 * nh * nh * nh * nh);
    // radiance factor of a rough sea: Fresnel 0.021 * pi * D / (4 mu_view), in the Sun's units. On the
    // sheet there is no single viewpoint, so the glint is kept as a faint mark of the sub-solar point.
    float glint = D * 0.021 * PI / (4.0 * max(nv, 0.10)) * step(0.0, mu0) * (uView == 0 ? SUN_E : 0.4);
    sea += trans * vec3(1.0, 0.96, 0.88) * glint * (1.0 - cloud) * shadow;
    vec3 iceC = vec3(0.80, 0.86, 0.92) * (sunL * shadow + skyL * 1.2 + moonL * 3.0);
    sea = mix(sea, iceC, smoothstep(0.08, 0.80, ice));

    col = mix(land, sea, water);

    if (uHasLive > 0.5) {
      // an OBSERVED mosaic for the clock's date replaces the modelled daytime surface and its clouds
      vec3 lv = toLinear(tex(uLive, uv).rgb);
      float have = smoothstep(0.004, 0.02, luma(lv));
      col = mix(col, lv * (sunL * 0.85 + skyL), have);
    }

    // Clouds, lit by the same Sun, self-shaded on their sunward gradient. A cloud absorbs almost
    // nothing: what it does not reflect it passes down. The cloud photograph's brightness is taken as
    // the cloud's reflectance with the Sun 40 degrees from overhead, capped near 0.9 (what the thickest
    // storm tops measure), and the two-stream law carries it to other Sun heights: R = t / (mu0 + t),
    // so a cloud sends back a larger share of a slanting beam. That, with the ozone above, is what keeps
    // EPIC's disc level from the centre to a cosine of 0.2 and then drops it at the edge. Checked against
    // EPIC's brightness distribution over open ocean, percentile by percentile (epic_cloud_cdf.py).
    float selfSh = clamp(1.0 - (cloudSun - cloud) * 2.2, 0.55, 1.10);
    vec3 cloudC = sunL * selfSh + skyL * 0.7 + moonL * 4.0;
    float cRef = cloud < 0.55 ? cloud : 0.55 + (CLOUD_MAX - 0.55) * tanh((cloud - 0.55) / (CLOUD_MAX - 0.55));
    float tC = CLOUD_MU * cRef / (1.0 - cRef);
    float cloudFar = mix(cRef, tC / (max(mu0, 0.30) + tC), dayF); // below 17 degrees of Sun, broken cloud shades itself and the gain stops
    float cloudA = broken(rankMix(grain, vec3(landCu), conv).z, cloudFar, grainFade, conv);
    cloudA = 1.0 - (1.0 - cloudA) * (1.0 - lowCloud);              // sheets and cumulus under and between the larger systems
    cloudFar = 1.0 - (1.0 - cloudFar) * (1.0 - cumFar) * (1.0 - deckFar);
    // Two things the eye's position does to broken cloud, neither of which changes what the cloud is.
    // Seen at a slant, the gaps close: towers hide the clear air behind them. And seen from the Sun's
    // own side no cloud shows its shadowed flank or the shadow it throws, so the field reads brighter:
    // the amount of cloud light is fixed by satellites looking straight down in the afternoon (ISCCP,
    // VIIRS), and NASA EPIC, which looks from within 4-12 degrees of the Sun, sees about a third more.
    // Solid cloud has no gaps and no flanks: both effects fade as the cover closes.
    // Both are statements about a FIELD of cloud, so the gain is worked out on the far view's light and
    // then given to whatever is drawn. Applied to each resolved piece instead, a bright core gained
    // nothing and a gap gained nothing, and the same sky came out dimmer the closer it was drawn.
    if (uView == 0 && cloudFar > 1e-3) {
      float nvC = max(dot(N, V), 0.35);
      float seen = 1.0 - pow(1.0 - cloudFar, 1.0 + CLOUD_SLANT * (1.0 / nvC - 1.0));
      float opp = 1.0 + CLOUD_OPP * exp(-(1.0 - dot(uSun, V)) / 0.094) * dayF;      // 0.094 = 1 - cos 25 degrees
      seen = seen * opp / (1.0 + seen * (opp - 1.0));
      cloudA = min(cloudA * seen / cloudFar, 0.98);
    }
    col = mix(col, cloudC, cloudA);
    cloud = max(cloud, lowCloud);                                  // what the air and the city lights below see

    // the dark side: electric light
    if (uNightOn > 0.5) {
      float glow = night * (1.0 - dayF) * (1.0 - 0.72 * cloud);
      // From far off a town is a point and must carry: the gain is high and a city is white. Close in the same
      // gain makes one white sheet of a whole basin, so the curve is the picture's own: amber streets, pale cores.
      vec3 farG = vec3(1.0, 0.72, 0.38) * glow * 2.6 + vec3(1.0, 0.90, 0.75) * glow * glow * 3.0;
      // (display values: dim amber roads and suburbs, bright amber districts, pale gold at the top. NOT white: the
      // picture is at full scale over the whole of a large city, and a white sheet hides the names set on it.)
      vec3 ramp = mix(vec3(0.0), vec3(0.34, 0.21, 0.10), smoothstep(0.0, 0.18, nightFine));
      ramp = mix(ramp, vec3(0.68, 0.45, 0.21), smoothstep(0.18, 0.48, nightFine));
      ramp = mix(ramp, vec3(0.88, 0.65, 0.34), smoothstep(0.48, 0.76, nightFine));
      ramp = mix(ramp, vec3(0.97, 0.82, 0.54), smoothstep(0.76, 1.0, nightFine));
      vec3 nearG = fromDisplay(ramp) * nightTex * (1.0 - dayF) * (1.0 - 0.72 * cloud);
      // the change of curve is spread over the zoom from where the window opens (5 km a pixel) to 2 km
      col += mix(NIGHT_GAIN * farG, nearG, (1.0 - smoothstep(-1.2, 0.5, lodOf(2.0))) * uDetNightW * inWin);
    }
    // aurora (LIVE only): OVATION probability on the dark side
    if (uHasAurora > 0.5) {
      float au = texture(uAurora, uv).r;
      col += NIGHT_GAIN * vec3(0.10, 0.95, 0.45) * smoothstep(0.04, 0.6, au) * (1.0 - dayF) * 0.9;
    }
    // air between the ground and the camera
    if (uAtmoOn > 0.5) {
      // Less air lies above high ground and above cloud tops. The ground's light is dimmed along the
      // view path, and the air adds its own: (3/16)(1+cos^2) * muS/(muS+muV) * (1 - exp(-tau(mV+mS))).
      // The warm band at the terminator is not added here: it is the reddened sunlight (trans) on
      // whatever it lights.
      // most cloud is low (tops at 2 km, three quarters of the air still above); the thickest reaches 8 km
      vec3 tau = TAU_R * exp(-max(z, 0.0) / 8000.0) * mix(1.0, mix(0.75, 0.35, smoothstep(0.5, 0.9, cloud)), smoothstep(0.0, 0.25, cloud));
      vec3 tauA = TAU_A * exp(-max(z, 0.0) / 2000.0) * (1.0 - 0.9 * cloud);   // the haze lies under the cloud tops
      float amV = airmass(nv), amS = airmass(mu0), cSV = dot(uSun, V);
      // the haze lies in the lowest 2 km, under four fifths of the air: its light is screened both ways
      vec3 inscat = SUN_E * (amV / (amV + amS)) * (AIR_MS * rayleighPhase(cSV) * (1.0 - exp(-tau * (amV + amS)))
                                                   + AER_W * aerosolPhase(-cSV) * (1.0 - exp(-tauA * (amV + amS))) * exp(-tau * AIR_ABOVE_HAZE * (amV + amS)));
      // 0.6: about half of what the direct beam loses still arrives as skylight. The +1 is the Sun's
      // own vertical column; `trans` above carries only the extra path of a low Sun.
      col = col * exp(-(tau * 0.6 + tauA * 0.3) * (amV + 1.0)) + inscat * smoothstep(-0.10, 0.02, mu0);
    }
  } else {
    // =================================== Atlas ===============================================
    // The same fields in a cartographic register: political tints, relief by oblique light.
    vec3 cId = uHasCountries > 0.5 ? texture(uCountries, uv).rgb : vec3(0.0);
    int mc = int(cId.b * 255.0 / 32.0 + 0.5);
    vec3 tint = vec3(0.93, 0.92, 0.86);
    if (mc == 1) tint = vec3(0.98, 0.93, 0.66);       // yellow
    else if (mc == 2) tint = vec3(0.80, 0.90, 0.72);  // green
    else if (mc == 3) tint = vec3(0.98, 0.80, 0.76);  // rose
    else if (mc == 4) tint = vec3(0.99, 0.86, 0.66);  // orange
    else if (mc == 5) tint = vec3(0.85, 0.80, 0.92);  // lilac
    else if (mc == 6) tint = vec3(0.76, 0.89, 0.88);  // aqua
    else if (mc == 7) tint = vec3(0.95, 0.88, 0.80);  // buff
    vec3 L = normalize(-E + Nn + 1.35 * N);            // light from the north-west, as on a printed sheet
    float hs = dot(n, L) / dot(N, L);
    lensShade = hs;
    // permanent ice reads white: bright in BOTH bracketing months is not enough in winter, so use latitude and height too
    float iceSheet = smoothstep(0.55, 0.8, luma(toLinear(bm))) * smoothstep(58.0, 66.0, abs(degrees(ll.y)) + max(z, 0.0) / 400.0);
    vec3 land = mix(tint, vec3(0.97, 0.98, 0.99), iceSheet) * mix(1.0, hs, 0.55);
    if (cId.g > 0.5) {                                 // contested ground is hatched, never plain
      float st = step(0.5, fract((gl_FragCoord.x + gl_FragCoord.y) / 7.0));
      land = mix(land, vec3(0.62, 0.60, 0.62), 0.28 * st);
    }
    float depth = max(-z, 0.0);
    vec3 seaC = mix(vec3(0.80, 0.90, 0.96), vec3(0.52, 0.70, 0.86), smoothstep(0.0, 5500.0, depth));
    vec3 sea = seaC * mix(1.0, hs, 0.85);
    sea = mix(sea, vec3(0.96, 0.98, 1.0), smoothstep(0.15, 0.6, ice) * 0.85);
    col = mix(land, sea, water);
    // the coastline is the contour of the water field, not a traced line
    float wr = uHasWater > 0.5 ? wn.r : 0.0;
    float edge = 1.0 - smoothstep(0.0, 1.6, abs(wr - 0.5) / max(fwidth(wr), 1e-5));
    col = mix(col, vec3(0.22, 0.42, 0.62), edge * 0.75);
    if (uSelCountry > 0.5 && abs(cId.r * 255.0 - uSelCountry) < 0.5 && water < 0.5) col = mix(col, vec3(1.0, 0.82, 0.25), 0.35);
    if (uDaylightOn > 0.5) col *= mix(vec3(0.60, 0.64, 0.74), vec3(1.0), dayF);     // night is a cool shade the map stays readable under
    col = toLinear(col);
  }

  // ---- data lens: a field draped over the lit surface ---------------------------------------
  if (uLens != LENS_NONE) {
    float v = 0.0, a = uLensAlpha;
    if (uLens == LENS_TEMP) v = (tAir + 45.0) / 90.0;
    else if (uLens == LENS_PRECIP) v = sqrt(clamp(precip / 16.0, 0.0, 1.0));
    else if (uLens == LENS_SLP) v = (slp - 980.0) / 60.0;
    else if (uLens == LENS_WIND) v = windSp / 16.0;
    else if (uLens == LENS_CLOUD) v = cloudFrac;
    else if (uLens == LENS_SST) { v = (sst + 2.0) / 34.0; a *= water * step(0.66, oc.b); }   // not where the field holds modelled lake ice only (valid 150 of 255)
    else if (uLens == LENS_ICE) { v = ice; a *= water * smoothstep(0.02, 0.15, ice); }
    else if (uLens == LENS_POP) { v = tex(uLens2D, uv).r; a *= smoothstep(0.0, 0.10, v) * (1.0 - water); }
    else if (uLens == LENS_CO2) { v = tex(uLens2D, uv).r; a *= smoothstep(0.02, 0.22, v); }
    else if (uLens == LENS_SHIPS) { v = tex(uLens2D, uv).r; a *= smoothstep(0.03, 0.30, v) * water; }
    else if (uLens == LENS_ELEV) v = z < 0.0 ? 0.5 * (1.0 - sqrt(min(-z / 9000.0, 1.0))) : 0.5 + 0.5 * sqrt(min(z / 6500.0, 1.0));
    else if (uLens == LENS_GREEN) { vec3 s = bm; v = clamp((2.0 * s.g - s.r - s.b) * 3.2, 0.0, 1.0); a *= (1.0 - water); }
    else if (uLens == LENS_SOLAR) { v = max(mu0, 0.0); a *= smoothstep(-0.02, 0.05, mu0); }
    else if (uLens == LENS_LIGHTS) { v = sqrt(night); a *= smoothstep(0.0, 0.15, v); }
    vec3 lc = uStyle == 0 ? fromDisplay(palette(v)) : toLinear(palette(v));
    float lit = uStyle == 0 ? max(dayF, 0.55) : 1.0;
    float relief = (uLens == LENS_SST || uLens == LENS_ICE || uLens == LENS_SHIPS) ? 1.0 : mix(1.0, clamp(lensShade, 0.35, 1.6), 0.5);
    col = mix(col, lc * lit * relief, a);
  }

  // CLOSE IN, THE EXPOSURE RISES, as a camera's does when nothing bright is in frame. The exposure above is the
  // whole disc's, set so that cloud tops do not clip, and it leaves a city or a forest at a tenth of full scale:
  // right for the planet, too dark to read streets by. Where the cloud has thinned away (nearCam) the daylit
  // scene is opened up by NEAR_EXPOSURE, less where the ground is itself bright (desert, salt, snow: metered on the
  // shipped picture at 5 km), which at full gain went to a clipped yellow. Stated in the Finer ground card. Night
  // is left alone: its lights are authored in display values.
  if (uStyle == 0) col *= 1.0 + (NEAR_EXPOSURE - 1.0) * nearCam * dayF * (1.0 - smoothstep(0.38, 0.68, sceneL));
  // the Atlas register is display-referred already
  fragColor = vec4((uStyle == 0 ? display(col) : pow(max(col, 0.0), vec3(1.0 / 2.2))) + dither, 1.0);
}
