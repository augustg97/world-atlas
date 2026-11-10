#version 300 es
precision highp float;
in vec4 vColor;
in float vVis;
in float vSide;
in float vKm;
in float vHalfW;
uniform float uDashKm;     // 0 = solid
uniform float uDashDuty;
out vec4 fragColor;
void main() {
  if (vVis < 0.0) discard;
  float a = vColor.a * smoothstep(vHalfW, vHalfW - 1.4, abs(vSide));
  if (uDashKm > 0.0) a *= step(fract(vKm / uDashKm), uDashDuty);
  if (a < 0.003) discard;
  fragColor = vec4(vColor.rgb * a, a);       // premultiplied
}
