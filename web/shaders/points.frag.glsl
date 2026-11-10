#version 300 es
precision highp float;
in vec4 vColor;
in vec2 vP;
in float vVis;
in float vShape;
in float vR;
out vec4 fragColor;
void main() {
  if (vVis < 0.0) discard;
  float d = length(vP), r = vR - 1.0, a = 0.0;
  vec3 c = vColor.rgb;
  if (vShape < 0.5) {                       // 0: disc with a dark rim
    a = smoothstep(r + 0.6, r - 0.6, d);
    c = mix(c, vec3(0.0), smoothstep(r - 1.6, r - 0.4, d) * 0.55);
  } else if (vShape < 1.5) {                // 1: ring
    a = smoothstep(r + 0.6, r - 0.4, d) * smoothstep(r - 2.4, r - 1.2, d);
  } else if (vShape < 2.5) {                // 2: triangle (volcano)
    float t = max(abs(vP.x) * 1.732 + vP.y, -vP.y * 2.0) - r;
    a = smoothstep(0.7, -0.7, t);
  } else if (vShape < 3.5) {                // 3: square (power station)
    a = smoothstep(0.7, -0.7, max(abs(vP.x), abs(vP.y)) - r * 0.8);
    c = mix(c, vec3(0.0), smoothstep(-1.6, -0.4, max(abs(vP.x), abs(vP.y)) - r * 0.8) * 0.5);
  } else {                                  // 4: soft glow
    a = exp(-d * d / (r * r * 0.22));
  }
  a *= vColor.a;
  if (a < 0.003) discard;
  fragColor = vec4(c * a, a);
}
