#version 300 es
// Instanced line segments in geographic coordinates, projected per vertex by the same camera
// code as the substrate, so vectors and pixels can never disagree about where a place is.
precision highp float;
precision highp int;
#include "common.glsl"
layout(location = 0) in vec2 aCorner;   // x: 0 = start, 1 = end;  y: -1 / +1 side
layout(location = 1) in vec4 aSeg;      // lonA, latA, lonB, latB (radians)
layout(location = 2) in vec4 aColor;
layout(location = 3) in vec3 aParam;    // width px, km at A, km at B (for dashes)
uniform float uHeight;                  // lift above the surface, Earth radii
uniform float uWidthScale;
uniform float uAlpha;
out vec4 vColor;
out float vVis;
out float vSide;
out float vKm;
out float vHalfW;
void main() {
  float va, vb;
  vec4 ca = projectPoint(lonLatToVec(aSeg.xy) * (1.0 + uHeight), va);
  vec4 cb = projectPoint(lonLatToVec(aSeg.zw) * (1.0 + uHeight), vb);
  vec2 sa = ca.xy * uViewport * 0.5, sb = cb.xy * uViewport * 0.5;
  vec2 d = sb - sa;
  float len = length(d);
  vec2 dir = len > 1e-5 ? d / len : vec2(1.0, 0.0);
  vec2 nrm = vec2(-dir.y, dir.x);
  float halfW = aParam.x * uWidthScale * 0.5 + 0.8;                 // + antialias fringe
  vec2 p = mix(sa, sb, aCorner.x) + nrm * aCorner.y * halfW + dir * (aCorner.x * 2.0 - 1.0) * 0.4;
  vVis = min(va, vb);
  if (uView == 1 && abs(aSeg.x - aSeg.z) > PI) vVis = -1.0;       // crosses the sheet's cut meridian
  if (len > 0.5 * uViewport.x) vVis = -1.0;
  vColor = vec4(aColor.rgb, aColor.a * uAlpha);
  vSide = aCorner.y * halfW;
  vHalfW = halfW;
  vKm = mix(aParam.y, aParam.z, aCorner.x);
  gl_Position = vec4(p / (uViewport * 0.5), 0.0, 1.0);
}
