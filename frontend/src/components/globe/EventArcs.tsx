"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { morphPosition } from "@/lib/morph";
import { MARKER_LIFT } from "@/lib/projection";
import { useObservatoryStore } from "@/store/useObservatoryStore";

const SAMPLES_PER_ARC = 48;
const MAX_ARCS = 24;

/** Build N arcs connecting recent critical/high events to the nearest cluster centroid.
 *  Cheap and visual; the cluster-set from the backend can later replace this with
 *  authoritative cluster ids.
 */
function pickArcEndpoints(): Array<[number, number, number, number]> {
  const s = useObservatoryStore.getState();
  const list = Array.from(s.events.values()).filter(
    (e) => e.lat !== null && e.lng !== null && (e.severity === "critical" || e.severity === "high")
  );
  if (list.length < 2) return [];
  // Connect each high/critical to its nearest neighbour by category match.
  const byCat = new Map<string, typeof list>();
  for (const e of list) {
    if (!byCat.has(e.category)) byCat.set(e.category, [] as typeof list);
    byCat.get(e.category)!.push(e);
  }
  const arcs: Array<[number, number, number, number]> = [];
  for (const events of byCat.values()) {
    for (let i = 0; i + 1 < events.length && arcs.length < MAX_ARCS; i += 2) {
      const a = events[i];
      const b = events[i + 1];
      arcs.push([a.lat as number, a.lng as number, b.lat as number, b.lng as number]);
    }
    if (arcs.length >= MAX_ARCS) break;
  }
  return arcs;
}

export function EventArcs() {
  const lineRef = useRef<THREE.LineSegments>(null!);
  const positions = useMemo(
    () => new Float32Array(MAX_ARCS * SAMPLES_PER_ARC * 2 * 3),
    []
  );

  useFrame(() => {
    const t = useObservatoryStore.getState().morphT;
    const arcs = pickArcEndpoints();
    let writeIdx = 0;
    const tmpA = new THREE.Vector3();
    const tmpB = new THREE.Vector3();

    for (let aIdx = 0; aIdx < arcs.length && aIdx < MAX_ARCS; aIdx++) {
      const [latA, lngA, latB, lngB] = arcs[aIdx];
      for (let k = 0; k < SAMPLES_PER_ARC; k++) {
        const u = k / SAMPLES_PER_ARC;
        const v = (k + 1) / SAMPLES_PER_ARC;
        const lerpLat1 = latA + (latB - latA) * u;
        const lerpLng1 = lngA + (lngB - lngA) * u;
        const lerpLat2 = latA + (latB - latA) * v;
        const lerpLng2 = lngA + (lngB - lngA) * v;

        morphPosition(lerpLat1, lerpLng1, t, tmpA, MARKER_LIFT + 0.04 * Math.sin(Math.PI * u));
        morphPosition(lerpLat2, lerpLng2, t, tmpB, MARKER_LIFT + 0.04 * Math.sin(Math.PI * v));

        positions[writeIdx++] = tmpA.x;
        positions[writeIdx++] = tmpA.y;
        positions[writeIdx++] = tmpA.z;
        positions[writeIdx++] = tmpB.x;
        positions[writeIdx++] = tmpB.y;
        positions[writeIdx++] = tmpB.z;
      }
    }
    // Zero out the rest.
    for (let z = writeIdx; z < positions.length; z++) positions[z] = 0;

    const geom = lineRef.current?.geometry as THREE.BufferGeometry | undefined;
    if (geom) {
      const attr = geom.attributes.position as THREE.BufferAttribute;
      attr.array = positions;
      attr.needsUpdate = true;
    }
  });

  return (
    <lineSegments ref={lineRef} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <lineBasicMaterial color="#7c9cff" transparent opacity={0.45} />
    </lineSegments>
  );
}
