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
uniform sampler2D uWaterNight;     // R: water fraction   G: sqrt(night lights)
uniform sampler2D uElev;           // RG: 16-bit elevation
uniform sampler2D uClouds;         // cloud texture
uniform sampler2DArray uAtmoA;     // u10, v10, t0
uniform sampler2DArray uAtmoB;     // slp, cloud fraction, precip
uniform sampler2DArray uOceanA;    // sst, ice, valid
uniform sampler2D uCountries;      // R: id  G: disputed  B: map colour index * 32
uniform sampler2D uLens2D;         // the selected static lens field (log-companded 0..1)
uniform sampler2D uLut;            // palettes, 256 wide, one per row of 16
uniform sampler2D uLive;           // observed true-colour mosaic for the clock's date (GIBS)
uniform sampler2D uAurora;         // OVATION probability, 360 x 181

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
float dec(float v, vec2 e) { return e.x + (e.y - e.x) * v; }
vec3 toLinear(vec3 c) { return pow(c, vec3(2.2)); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float hash13(vec3 p) { p = fract(p * 0.1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
float hash12(vec2 p) { vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }

float elevation(vec2 uv) {
  vec2 e = tex(uElev, uv).rg;
  return (e.r * 255.0 * 256.0 + e.g * 255.0) / 65535.0 * 20000.0 - 11000.0;
}

float vnoise(vec2 x, float period) {
  vec2 i = floor(x), f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  vec2 j = vec2(mod(i.x + 1.0, period), i.y + 1.0);               // periodic in longitude
  return mix(mix(hash12(i), hash12(vec2(j.x, i.y)), f.x), mix(hash12(vec2(i.x, j.y)), hash12(j), f.x), f.y);
}
// Three octaves of value noise whose coarsest wave is `km` long on the ground; returns about 0..1, mean 0.5.
float clumps(vec2 uv, float km) {
  float fx = floor(40075.0 / km);
  vec2 x = uv * vec2(fx, fx * 0.5);
  return 0.50 * vnoise(x, fx) + 0.30 * vnoise(x * 2.0 + 7.7, fx * 2.0) + 0.20 * vnoise(x * 4.0 + 3.1, fx * 4.0);
}
// how many octaves the pixel is finer (negative) or coarser (positive) than a wave `km` long
float lodOf(float km) { return log2(max(length(gDx) * 40075.0, length(gDy) * 20037.0) / km + 1e-6); }

// Cloud optical density at uv. A real cloud photograph, moved along the monthly-mean surface
// wind (two-phase flow map so the distortion stays bounded) and thinned or thickened by the
// monthly cloud-fraction climatology. Shapes are real; positions are MODELLED.
float cloudAt(vec2 uv, vec2 flowUV, float frac) {
  const float PERIOD = 30.0;                                   // hours per flow cycle
  float ph0 = fract(uHours / PERIOD), ph1 = fract(uHours / PERIOD + 0.5);
  float w0 = 1.0 - abs(2.0 * ph0 - 1.0);
  // slow eastward carry so cycles do not replay in place. Only its fraction is kept: the whole number of
  // turns is hundreds, and subtracting that from uv cost the longitude four digits (seen as vertical streaks)
  float drift = fract(uHours * 2.2e-4);
  vec2 base = vec2(uv.x - drift, uv.y);
  float c0 = textureGrad(uClouds, base - flowUV * (ph0 - 0.5) * PERIOD, gDx, gDy).r;
  float c1 = textureGrad(uClouds, base - flowUV * (ph1 - 0.5) * PERIOD + vec2(0.37, 0.0), gDx, gDy).r;
  float c = mix(c1, c0, w0);
  float gain = mix(0.55, 1.75, smoothstep(0.15, 0.85, frac));
  c = clamp(c * gain - 0.10 * (1.0 - frac), 0.0, 1.0);
  // Below the photograph's 5 km texel the field would only be a blur. Cloud edges are ragged at every
  // scale, so the edge (not the core, not the clear air) is broken up by clumps 4-16 km across, carried
  // with the same drift. It fades out as the pixel grows past the texel: the far view is untouched.
  float fine = 1.0 - smoothstep(-2.0, 0.0, lodOf(16.0));
  if (fine > 0.01) c = clamp(c + (clumps(base, 16.0) - 0.5) * 0.65 * fine * 4.0 * c * (1.0 - c), 0.0, 1.0);
  return c;
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
const float CLOUD_MAX = 0.96;      // ceiling of the cloud photograph read as reflectance
const float CLOUD_MU = 0.75;       // the Sun height (cosine) at which the photograph's brightness IS the reflectance
const float NIGHT_GAIN = 3.0;      // faint light (cities, moonlight, stars, aurora) is not scored by a daylit photograph; this keeps it where it was set by eye

// Cumulus over humid land. Through the morning the ground heats, the air above it overturns and
// small clouds stud every vegetated region until evening; deserts and the open sea stay clear of
// them. Coverage follows the month's rainfall and the local solar time. The cells are the cloud
// photograph again at nine times the frequency (about 1 km a texel), cut at the level that gives
// the wanted coverage: `th` is the texture's own measured quantile curve. MODELLED.
// Why it exists: against NASA EPIC the clearest twentieth of vegetated land was 25 display levels
// brighter than bare ground under clear air, in every latitude band, while desert and ocean matched.
const float CUMULUS_COVER = 0.20;
const float CUMULUS_E2 = 1.2;      // mean of the sharpened field envelope, so sharpening leaves the mean cover alone  // afternoon cover over the wettest land (it was 0.42 while the ground under it was drawn too dark)
float cumulusAt(vec2 uv, float humid, float lst) {
  float heat = 0.12 + 0.88 * smoothstep(8.0, 12.5, lst) * (1.0 - smoothstep(17.0, 21.0, lst));
  float c = CUMULUS_COVER * humid * heat;                         // fraction of the ground under cloud
  if (c < 0.004) return 0.0;
  // cells gather into fields tens of km across: the cloud photograph at 5 and 13 times its frequency
  // sets where the fields are (its mean in this band is 0.194, so each envelope averages 1)
  vec2 q = vec2(uv.x * 5.0 + 0.13, 0.25 + 0.5 * abs(fract(uv.y * 5.0) * 2.0 - 1.0));
  float env = clamp(textureGrad(uClouds, q, gDx * 5.0, gDy * 5.0).r / 0.194, 0.0, 2.4);
  vec2 q2 = vec2(uv.x * 13.0 + 0.61, 0.25 + 0.5 * abs(fract(uv.y * 13.0 + 0.3) * 2.0 - 1.0));
  float env2 = clamp(textureGrad(uClouds, q2, gDx * 13.0, gDy * 13.0).r / 0.194, 0.0, 2.4);
  float e = 0.5 * (env + env2);                                    // fields of two sizes, 30 and 80 km
  c = min(0.60, c * e * sqrt(e) / CUMULUS_E2);                     // sharpened: fields with clear air between them, not a veil
  // Single cells are 1-2 km, under the 2 km zoom floor. What a pixel that size CAN show is how they
  // clump: knots and streets 3 to 12 km across. Coarser pixels than that see only the mean cover.
  float n = clumps(uv, 12.0);
  float th = 0.5 + (0.5 - c) * 0.62;
  float cells = smoothstep(th - 0.15, th + 0.15, n);
  // a crowded field holds taller, thicker cloud: reflectance from 0.45 (scattered fair-weather cells) to 0.70
  return mix(0.45, 0.70, smoothstep(0.15, 0.50, c)) * mix(cells, c, smoothstep(-1.5, 0.5, lodOf(12.0)));
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
  vec3 alb = albedoOf(bm);
  vec2 wn = tex(uWaterNight, uv).rg;
  float water = uHasWater > 0.5 ? smoothstep(0.35, 0.65, wn.r) : 0.0;
  float night = wn.g * wn.g;
  float z = uHasElev > 0.5 ? elevation(uv) : 0.0;
  vec2 grad = vec2(0.0);
  if (uHasRelief > 0.5) {
    vec2 r = clamp((tex(uRelief, uv).rg - 0.5) * 2.0, -0.985, 0.985);
    grad = 0.5 * log((1.0 + r) / (1.0 - r)) / 3.0;                 // atanh / 3 : metres per metre
  }
  vec3 atA = vec3(0.5, 0.5, 0.6), atB = vec3(0.5, 0.5, 0.2);
  if (uHasClimate > 0.5) { atA = arr(uAtmoA, uv); atB = arr(uAtmoB, uv); }
  vec2 wind = vec2(dec(atA.r, uE_u10), dec(atA.g, uE_v10));
  float windSp = length(wind);
  float cloudFrac = dec(atB.g, uE_cloud);
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
  float cloud = 0.0, cloudSh = 0.0, cloudSun = 0.0, cum = 0.0;
  vec2 sunStep = vec2(sunE / coslat / (2.0 * PI), -sunN / PI);
  if (uCloudsOn > 0.5 && uHasLive < 0.5) {
    cloud = cloudAt(uv, flowUV, cloudFrac);
    float slant = 1.0 / max(mu0, 0.18);
    cloudSh = cloudAt(uv + sunStep * 0.0035 * slant, flowUV, cloudFrac);     // what stands between this ground and the Sun
    cloudSun = cloudAt(uv + sunStep * 0.0016, flowUV, cloudFrac);            // the cloud's own sunward neighbour
    cum = cumulusAt(uv, (1.0 - water) * smoothstep(0.2, 3.0, precip), lst);
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
    float shadow = 1.0 - 0.62 * cloudSh;

    // Rough ground is not a Lambert surface: seen from near the Sun's direction it hides its own
    // shadows and falls off toward the limb more slowly (Lommel-Seeliger). Normalised to 1 with Sun and
    // eye overhead, where the albedo table was measured.
    float nvL = max(dot(N, V), 0.0);
    float rough = (1.0 - LAND_LS) + LAND_LS * 2.0 / (max(mu0, 0.0) + nvL + 1e-3);
    rough = uView == 0 ? min(rough, 1.8) : 1.0;
    vec3 land = alb * (sunL * shade * shadow * rough + skyL + moonL);

    // water: one colour, shaded; a shelf tint; sky reflection; Sun glint whose width is the wind's
    float depth = max(-z, 0.0);
    vec3 seaC = mix(SEA_DEEP, vec3(0.018, 0.085, 0.110), 0.75 * exp(-depth / 75.0) * uHasElev);
    vec3 sea = seaC * (sunL * shadow * 0.9 + skyL * 1.6 + moonL * 2.0);
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
    float cloudA = mix(cRef, tC / (max(mu0, 0.30) + tC), dayF);   // below 17 degrees of Sun, broken cloud shades itself and the gain stops
    cloudA = 1.0 - (1.0 - cloudA) * (1.0 - cum);                   // cumulus under and between the larger systems
    col = mix(col, cloudC, cloudA);
    cloud = max(cloud, cum);                                       // what the air and the city lights below see

    // the dark side: electric light
    if (uNightOn > 0.5) {
      float glow = night * (1.0 - dayF) * (1.0 - 0.72 * cloud);
      col += NIGHT_GAIN * (vec3(1.0, 0.72, 0.38) * glow * 2.6 + vec3(1.0, 0.90, 0.75) * glow * glow * 3.0);
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
    else if (uLens == LENS_SST) { v = (sst + 2.0) / 34.0; a *= water * step(0.5, oc.b); }
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

  // the Atlas register is display-referred already
  fragColor = vec4((uStyle == 0 ? display(col) : pow(max(col, 0.0), vec3(1.0 / 2.2))) + dither, 1.0);
}
