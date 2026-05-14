"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useObservatoryStore } from "@/store/useObservatoryStore";

import { ATMOSPHERE_FRAGMENT_SHADER, ATMOSPHERE_VERTEX_SHADER } from "./shaders";

export function Atmosphere() {
  const matRef = useRef<THREE.ShaderMaterial>(null!);

  const uniforms = useMemo(() => ({ uMorph: { value: 0 } }), []);

  useFrame(() => {
    const t = useObservatoryStore.getState().morphT;
    if (matRef.current) {
      (matRef.current.uniforms.uMorph as { value: number }).value = t;
    }
  });

  return (
    <mesh>
      <sphereGeometry args={[1.08, 64, 32]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={ATMOSPHERE_VERTEX_SHADER}
        fragmentShader={ATMOSPHERE_FRAGMENT_SHADER}
        uniforms={uniforms}
        side={THREE.BackSide}
        blending={THREE.AdditiveBlending}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}
