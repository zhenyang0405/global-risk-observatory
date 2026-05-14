// Vertex + fragment shaders for the Earth mesh and the atmosphere shell.
// The vertex shader lerps each sphere vertex toward its equirectangular plane
// position based on uniform uMorph in [0,1]. A "peel" wave adds a transient
// z-displacement that's zero at t=0, peaks ~t=0.3, and fades by t=0.65 so the
// final flat plane is perfectly flat.

export const EARTH_VERTEX_SHADER = /* glsl */ `
uniform float uMorph;

varying vec2 vUv;
varying vec3 vWorldNormal;
varying float vMorph;

float ease(float t) {
  return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0;
}

vec3 sphereToPlane(vec3 p) {
  // Three.js SphereGeometry with default phi/theta puts the vertex at UV
  // (0.5, 0.5) — Blue Marble's lng=0 (Greenwich) — at position (1, 0, 0).
  // Inverse: (x, y, z) -> (lon, lat) with this convention:
  //   x =  cos(lng) * cos(lat)
  //   y =  sin(lat)
  //   z = -sin(lng) * cos(lat)
  // So lng = atan2(-z, x), lat = asin(y / |p|).
  float lon = atan(-p.z, p.x);
  float lat = asin(clamp(p.y / max(length(p), 1e-6), -1.0, 1.0));
  return vec3(lon * 2.0, lat * 2.0, 0.0);
}

void main() {
  vec3 sph = position;
  vec3 pln = sphereToPlane(position);
  float t = ease(uMorph);
  vec3 pos = mix(sph, pln, t);

  // organic peel wave — vanishes by t=0.65
  float wave = sin(uv.x * 6.2831853 * 3.0) * 0.04
             * (1.0 - smoothstep(0.0, 0.65, uMorph)) * t;
  pos.z += wave;

  vUv = uv;
  vMorph = t;
  vWorldNormal = normalize(mix(normal, vec3(0.0, 0.0, 1.0), t));
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`;

export const EARTH_FRAGMENT_SHADER = /* glsl */ `
uniform sampler2D uDayMap;
uniform float uMorph;
varying vec2 vUv;
varying vec3 vWorldNormal;
varying float vMorph;

void main() {
  vec3 day = texture2D(uDayMap, vUv).rgb;

  // Soft fresnel rim that fades to zero on the flat map.
  float rim = pow(1.0 - clamp(dot(normalize(vWorldNormal), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 2.5);
  vec3 rimColor = vec3(0.30, 0.55, 1.0) * rim * (1.0 - vMorph);

  // Subtle latitude tint that flattens as we unfold.
  vec3 color = day + rimColor;
  gl_FragColor = vec4(color, 1.0);
}
`;

export const ATMOSPHERE_VERTEX_SHADER = /* glsl */ `
uniform float uMorph;
varying vec3 vNormal;
varying float vMorph;

float ease(float t) {
  return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0;
}

void main() {
  vNormal = normalize(normalMatrix * normal);
  vMorph = ease(uMorph);
  // Shrink the atmosphere into nothing as we flatten.
  vec3 pos = position * (1.0 - vMorph);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`;

export const ATMOSPHERE_FRAGMENT_SHADER = /* glsl */ `
varying vec3 vNormal;
varying float vMorph;

void main() {
  float intensity = pow(0.75 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.4);
  vec3 atmoColor = vec3(0.30, 0.55, 1.0) * intensity;
  float alpha = intensity * (1.0 - vMorph);
  gl_FragColor = vec4(atmoColor, alpha);
}
`;
