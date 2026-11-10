// Shared by every shader: the two cameras, and the map between screen and lon/lat.
// Earth-fixed frame: +x through (lon 0, lat 0), +y through (lon 90E, lat 0), +z through the north pole.
const float PI = 3.141592653589793;
const float WT_COSPHI1 = 0.6366197723675814;   // 2/pi : Winkel Tripel standard parallel acos(2/pi)

uniform int uView;            // 0 = globe, 1 = Winkel Tripel sheet
uniform vec2 uViewport;       // drawing buffer size in px
uniform vec3 uCamPos;         // globe camera, Earth radii
uniform mat3 uCamBasis;       // columns: right, up, forward
uniform float uTanHalfFov;    // vertical
uniform vec2 uMapCenter;      // sheet: projected coordinate at the screen centre
uniform float uMapScale;      // sheet: projected units per px

vec3 lonLatToVec(vec2 ll) {
  float c = cos(ll.y);
  return vec3(c * cos(ll.x), c * sin(ll.x), sin(ll.y));
}
vec2 vecToLonLat(vec3 p) {
  return vec2(atan(p.y, p.x), asin(clamp(p.z, -1.0, 1.0)));
}

// Winkel Tripel forward: (lon, lat) radians -> plane. x in +-2.571, y in +-pi/2.
vec2 wtForward(vec2 ll) {
  float cphi = cos(ll.y);
  float a = acos(clamp(cphi * cos(ll.x * 0.5), -1.0, 1.0));
  float sinc = a > 1e-4 ? sin(a) / a : 1.0 - a * a / 6.0;
  return 0.5 * vec2(ll.x * WT_COSPHI1 + 2.0 * cphi * sin(ll.x * 0.5) / sinc,
                    ll.y + sin(ll.y) / sinc);
}

// Winkel Tripel inverse by Newton iteration on the forward map. Returns lon/lat and, in ok,
// whether the point lies on the map.
vec2 wtInverse(vec2 xy, out bool ok) {
  ok = false;
  if (abs(xy.y) > 1.5708 || abs(xy.x) > 2.5709) return vec2(0.0);
  float phi = clamp(xy.y, -1.5707, 1.5707);
  float lam = clamp(2.0 * xy.x / (WT_COSPHI1 + cos(phi)), -PI, PI);
  const float h = 1.5e-3;
  for (int i = 0; i < 9; i++) {
    vec2 f = wtForward(vec2(lam, phi)) - xy;
    vec2 fl = (wtForward(vec2(lam + h, phi)) - wtForward(vec2(lam - h, phi))) / (2.0 * h);
    vec2 fp = (wtForward(vec2(lam, phi + h)) - wtForward(vec2(lam, phi - h))) / (2.0 * h);
    float det = fl.x * fp.y - fp.x * fl.y;
    if (abs(det) < 1e-9) break;
    lam -= (f.x * fp.y - fp.x * f.y) / det;
    phi -= (fl.x * f.y - f.x * fl.y) / det;
    lam = clamp(lam, -PI - 0.05, PI + 0.05);
    phi = clamp(phi, -1.5707963, 1.5707963);
  }
  vec2 r = wtForward(vec2(lam, phi)) - xy;
  ok = dot(r, r) < 1e-8 && abs(lam) <= PI + 1e-4;
  return vec2(lam, phi);
}

// Project a point (unit vector scaled by 1 + height) to clip space. vis > 0 if it can be seen.
vec4 projectPoint(vec3 p, out float vis) {
  if (uView == 0) {
    vec3 v = p - uCamPos;
    float zc = dot(v, uCamBasis[2]);
    float aspect = uViewport.x / uViewport.y;
    vec2 ndc = vec2(dot(v, uCamBasis[0]) / (uTanHalfFov * aspect), dot(v, uCamBasis[1]) / uTanHalfFov) / max(zc, 1e-4);
    // hidden if the ray from the camera to p passes through the unit sphere first
    float r2 = dot(p, p);
    float d2 = dot(uCamPos, uCamPos);
    float pc = dot(p, uCamPos);
    // a surface point is visible iff p.c >= 1; a raised point also beyond the limb
    float horizon = pc - 1.0;
    if (horizon < 0.0 && r2 > 1.0002) {
      vec3 dir = normalize(v);
      float b = dot(uCamPos, dir);
      float perp2 = d2 - b * b;
      horizon = perp2 > 1.0 ? 1.0 : -1.0;
    }
    vis = zc > 0.0 ? horizon : -1.0;
    return vec4(ndc, 0.0, 1.0);
  }
  vec2 ll = vecToLonLat(normalize(p));
  vec2 xy = wtForward(ll);
  vis = 1.0;
  return vec4((xy - uMapCenter) / (uMapScale * uViewport * 0.5), 0.0, 1.0);
}
