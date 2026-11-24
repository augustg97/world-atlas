#version 300 es
precision highp float;
in vec3 vNormal, vGround;
in float vHeightSupplied;
uniform vec3 uSun;
uniform float uAtlas;
out vec4 frag;

void main() {
  vec3 normal = normalize(vNormal), up = normalize(vGround);
  float roof = smoothstep(0.45, 0.9, dot(normal, up));
  float day = smoothstep(-0.15, 0.25, dot(up, uSun));
  float sun = max(0.0, dot(normal, uSun));
  vec3 wall = mix(vec3(0.54, 0.58, 0.62), vec3(0.57, 0.65, 0.69), vHeightSupplied);
  vec3 material = mix(wall, vec3(0.77, 0.76, 0.70), roof);
  vec3 daytime = material * (0.57 + 0.43 * sun);
  vec3 night = material * vec3(0.20, 0.25, 0.32) * (0.63 + roof * 0.32);
  frag = vec4(mix(night, daytime, mix(day, 0.88, uAtlas)), 1.0);
}
