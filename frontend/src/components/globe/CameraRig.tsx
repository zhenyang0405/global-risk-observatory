"use client";

import { OrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { easeInOutCubic } from "@/lib/morph";
import { useObservatoryStore } from "@/store/useObservatoryStore";

const SPHERE_CAM = new THREE.Vector3(0, 0.8, 3.0);
const FLAT_CAM = new THREE.Vector3(0, 0, 8.5);
const SPHERE_FOV = 45;
const FLAT_FOV = 28;
const MORPH_DURATION_S = 1.5;

export function CameraRig() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const tStartRef = useRef<number | null>(null);
  const tFromRef = useRef(0);

  // Auto-spin while sphere mode is idle.
  const spinRef = useRef(0);

  useEffect(() => {
    camera.position.copy(SPHERE_CAM);
    camera.fov = SPHERE_FOV;
    camera.updateProjectionMatrix();
  }, [camera]);

  useFrame((_state, delta) => {
    const s = useObservatoryStore.getState();
    const animating = s.morphAnimating;
    const target = s.targetMorph;
    const now = performance.now() / 1000;

    if (animating) {
      if (tStartRef.current === null) {
        tStartRef.current = now;
        tFromRef.current = s.morphT;
      }
      const elapsed = now - tStartRef.current;
      const frac = Math.min(elapsed / MORPH_DURATION_S, 1);
      const from = tFromRef.current;
      const to = target;
      const next = from + (to - from) * frac;
      useObservatoryStore.getState().setMorphT(next);
      if (frac >= 1) {
        tStartRef.current = null;
        useObservatoryStore.getState().setMorphT(to);
        useObservatoryStore.getState().finishMorph();
      }
    } else {
      tStartRef.current = null;
    }

    // Camera tween follows morphT.
    const t = useObservatoryStore.getState().morphT;
    const e = easeInOutCubic(t);
    camera.position.set(
      SPHERE_CAM.x * (1 - e) + FLAT_CAM.x * e,
      SPHERE_CAM.y * (1 - e) + FLAT_CAM.y * e,
      SPHERE_CAM.z * (1 - e) + FLAT_CAM.z * e
    );
    camera.fov = SPHERE_FOV * (1 - e) + FLAT_FOV * e;
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();

    // Idle spin in sphere mode (purely visual; doesn't affect data).
    if (t < 0.05 && !animating && !s.selectedEventId) {
      spinRef.current += delta * 0.05;
      camera.position.x = Math.sin(spinRef.current) * SPHERE_CAM.z;
      camera.position.z = Math.cos(spinRef.current) * SPHERE_CAM.z;
      camera.lookAt(0, 0, 0);
    }
  });

  return (
    <OrbitControls
      enabled={false}
      enableZoom={false}
      enablePan={false}
      enableRotate={false}
    />
  );
}
