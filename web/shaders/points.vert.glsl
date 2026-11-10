#version 300 es
precision highp float;
precision highp int;
#include "common.glsl"
layout(location = 0) in vec2 aCorner;   // -1..1
layout(location = 1) in vec3 aPos;      // lon, lat (radians), height (Earth radii)
layout(location = 2) in vec4 aColor;
layout(location = 3) in vec2 aSize;     // radius px, shape
uniform float uSizeScale;
uniform float uAlpha;
out vec4 vColor;
out vec2 vP;
out float vVis;
out float vShape;
out float vR;
void main() {
  float vis;
  vec4 c = projectPoint(lonLatToVec(aPos.xy) * (1.0 + aPos.z), vis);
  float r = aSize.x * uSizeScale + 1.0;
  vVis = vis;
  vColor = vec4(aColor.rgb, aColor.a * uAlpha);
  vP = aCorner * r;
  vR = r;
  vShape = aSize.y;
  gl_Position = vec4(c.xy + aCorner * r / (uViewport * 0.5), 0.0, 1.0);
}
