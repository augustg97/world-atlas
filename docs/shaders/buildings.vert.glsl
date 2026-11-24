#version 300 es
precision highp float;
#include "common.glsl"
layout(location=0) in vec3 aPosition;
layout(location=1) in vec3 aNormal;
layout(location=2) in float aHeightSupplied;
uniform float uNear, uFar;
out vec3 vNormal, vGround;
out float vHeightSupplied;

void main() {
  vec3 delta = aPosition - uCamPos;
  float z = dot(delta, uCamBasis[2]);
  vec2 xy = vec2(dot(delta, uCamBasis[0]) / (uViewport.x / uViewport.y), dot(delta, uCamBasis[1])) / uTanHalfFov;
  float depth = ((uFar + uNear) * z - 2.0 * uFar * uNear) / (uFar - uNear);
  gl_Position = vec4(xy, depth, z);
  vNormal = aNormal;
  vGround = normalize(aPosition);
  vHeightSupplied = aHeightSupplied;
}
