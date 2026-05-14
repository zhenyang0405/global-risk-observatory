// Geo math helpers shared by markers, arcs, and camera rig.

export const EARTH_RADIUS = 1.0;
export const ATMOSPHERE_RADIUS = 1.05;
export const MARKER_LIFT = 1.012;

function sphereFromLatLng(latDeg: number, lngDeg: number): [number, number, number] {
  const lat = (latDeg * Math.PI) / 180;
  const lng = (lngDeg * Math.PI) / 180;
  const cosLat = Math.cos(lat);
  // Same convention as lib/morph.ts (matches Three's default sphere UV).
  return [Math.cos(lng) * cosLat, Math.sin(lat), -Math.sin(lng) * cosLat];
}

/** Great-circle samples between two (lat, lng) points on a unit sphere. */
export function greatCircleSphere(
  latA: number,
  lngA: number,
  latB: number,
  lngB: number,
  samples = 64,
  lift = MARKER_LIFT
): Array<[number, number, number]> {
  const a = sphereFromLatLng(latA, lngA);
  const b = sphereFromLatLng(latB, lngB);
  const dot = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
  const omega = Math.acos(dot);
  const sinOmega = Math.sin(omega);
  const out: Array<[number, number, number]> = [];
  for (let i = 0; i <= samples; i++) {
    const k = i / samples;
    let cA: number, cB: number;
    if (sinOmega < 1e-6) {
      cA = 1 - k;
      cB = k;
    } else {
      cA = Math.sin((1 - k) * omega) / sinOmega;
      cB = Math.sin(k * omega) / sinOmega;
    }
    const x = a[0] * cA + b[0] * cB;
    const y = a[1] * cA + b[1] * cB;
    const z = a[2] * cA + b[2] * cB;
    const r = lift + 0.04 * Math.sin(Math.PI * k);
    const len = Math.sqrt(x * x + y * y + z * z) || 1;
    out.push([(x / len) * r, (y / len) * r, (z / len) * r]);
  }
  return out;
}
