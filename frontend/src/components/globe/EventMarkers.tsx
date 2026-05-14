"use client";

import { useFrame } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { morphPosition, morphNormal } from "@/lib/morph";
import { MARKER_LIFT } from "@/lib/projection";
import { CATEGORY_COLOR, SEVERITY_SCALE } from "@/lib/types";
import type { PersistedEvent } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

const MAX_MARKERS = 4000;

const dummy = new THREE.Object3D();
const tmpPos = new THREE.Vector3();
const tmpColor = new THREE.Color();
const UP = new THREE.Vector3(0, 1, 0);

export function EventMarkers() {
  const meshRef = useRef<THREE.InstancedMesh>(null!);

  // Ensure an instanceColor attribute exists before the first frame.
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    if (!mesh.instanceColor) {
      const colorAttr = new THREE.InstancedBufferAttribute(
        new Float32Array(MAX_MARKERS * 3),
        3
      );
      mesh.instanceColor = colorAttr;
    }
  }, []);

  useFrame(() => {
    const s = useObservatoryStore.getState();
    const t = s.morphT;
    const filters = s.filters;
    const selectedId = s.selectedEventId;
    const mesh = meshRef.current;
    if (!mesh) return;

    const list: PersistedEvent[] = [];
    for (const e of s.events.values()) {
      if (e.lat === null || e.lng === null) continue;
      if (!filters.has(e.category)) continue;
      list.push(e);
    }
    const start = Math.max(0, list.length - MAX_MARKERS);
    let i = 0;
    for (let k = start; k < list.length && i < MAX_MARKERS; k++, i++) {
      const e = list[k];
      morphPosition(e.lat as number, e.lng as number, t, tmpPos, MARKER_LIFT);
      const normal = morphNormal(e.lat as number, e.lng as number, t);

      dummy.position.copy(tmpPos);
      const quat = new THREE.Quaternion().setFromUnitVectors(UP, normal);
      dummy.quaternion.copy(quat);
      const scale =
        (SEVERITY_SCALE[e.severity] ?? 1) *
        0.018 *
        (e.id === selectedId ? 1.8 : 1.0);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);

      const hex = CATEGORY_COLOR[e.category] ?? "#9ca3af";
      tmpColor.set(hex);
      mesh.setColorAt(i, tmpColor);
    }

    // Hide remaining instances.
    for (let j = i; j < MAX_MARKERS; j++) {
      dummy.position.set(0, 0, 0);
      dummy.scale.setScalar(0);
      dummy.quaternion.identity();
      dummy.updateMatrix();
      mesh.setMatrixAt(j, dummy.matrix);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.count = MAX_MARKERS;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_MARKERS]} frustumCulled={false}>
      <sphereGeometry args={[1, 12, 8]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}
