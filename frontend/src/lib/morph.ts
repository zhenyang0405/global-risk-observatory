// CPU port of earth.vert.glsl morph math.
// MUST stay byte-identical to the GLSL or markers float off the surface.
//
// Convention is chosen so that Three.js SphereGeometry's default UV mapping
// puts UV (0.5, 0.5) at vertex (1, 0, 0), which is also where Blue Marble's
// Greenwich (lng=0, lat=0) pixel lives. That gives us:
//
//   x =  cos(lng) * cos(lat)
//   y =  sin(lat)
//   z = -sin(lng) * cos(lat)
//
// Plane is equirectangular scaled by 2 to match the shader:
//   plane_x = lng * 2
//   plane_y = lat * 2
//   plane_z = 0

import * as THREE from "three";

export const PLANE_SCALE = 2.0;
export const PEEL_AMPLITUDE = 0.04;
export const PEEL_WAVES = 3.0;

export function easeInOutCubic(t: number): number {
  if (t < 0.5) return 4 * t * t * t;
  const u = -2 * t + 2;
  return 1 - (u * u * u) / 2;
}

/** Convert (lat, lng) in degrees to a unit-sphere position. */
export function latLngToSphere(latDeg: number, lngDeg: number, radius = 1.0): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180;
  const lng = (lngDeg * Math.PI) / 180;
  const cosLat = Math.cos(lat);
  return new THREE.Vector3(
    radius * Math.cos(lng) * cosLat,
    radius * Math.sin(lat),
    -radius * Math.sin(lng) * cosLat
  );
}

/** Equirectangular plane position for the same (lat, lng). */
export function latLngToPlane(latDeg: number, lngDeg: number): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180;
  const lng = (lngDeg * Math.PI) / 180;
  return new THREE.Vector3(lng * PLANE_SCALE, lat * PLANE_SCALE, 0);
}

/** Morph a (lat, lng) location to its surface position at the current morph t. */
export function morphPosition(
  latDeg: number,
  lngDeg: number,
  t: number,
  out: THREE.Vector3 = new THREE.Vector3(),
  liftRadius = 1.0
): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180;
  const lng = (lngDeg * Math.PI) / 180;
  const cosLat = Math.cos(lat);

  const sx = liftRadius * Math.cos(lng) * cosLat;
  const sy = liftRadius * Math.sin(lat);
  const sz = -liftRadius * Math.sin(lng) * cosLat;

  const px = lng * PLANE_SCALE;
  const py = lat * PLANE_SCALE;
  const pz = 0;

  const e = easeInOutCubic(t);

  const mx = sx + (px - sx) * e;
  const my = sy + (py - sy) * e;
  let mz = sz + (pz - sz) * e;

  // Peel wave (matches shader, which keys off the geometry uv.x).
  // Three's SphereGeometry: uv.x = phi/(2π), and phi = lng + π.
  // So uv.x = (lng + π) / (2π).
  const u = (lng + Math.PI) / (2 * Math.PI);
  const peel =
    Math.sin(u * Math.PI * 2 * PEEL_WAVES) *
    PEEL_AMPLITUDE *
    (1.0 - smoothstep(0.0, 0.65, t)) *
    e;
  mz += peel;

  out.set(mx, my, mz);
  return out;
}

function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.min(Math.max((x - edge0) / (edge1 - edge0), 0), 1);
  return t * t * (3 - 2 * t);
}

/** Surface normal at (lat, lng) for a given morph t. Used for marker orientation. */
export function morphNormal(latDeg: number, lngDeg: number, t: number): THREE.Vector3 {
  const e = easeInOutCubic(t);
  const sphereN = latLngToSphere(latDeg, lngDeg).normalize();
  const planeN = new THREE.Vector3(0, 0, 1);
  return new THREE.Vector3()
    .copy(sphereN)
    .multiplyScalar(1 - e)
    .addScaledVector(planeN, e)
    .normalize();
}
