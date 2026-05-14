"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { useObservatoryStore } from "@/store/useObservatoryStore";

import { EARTH_FRAGMENT_SHADER, EARTH_VERTEX_SHADER } from "./shaders";

// Procedural fallback: an equirectangular noise+continents stand-in so the
// globe is visible even before the Blue Marble JPEG is dropped in.
function makeFallbackTexture(): THREE.DataTexture {
  const w = 512;
  const h = 256;
  const data = new Uint8Array(w * h * 4);
  for (let y = 0; y < h; y++) {
    const lat = (y / h) * Math.PI - Math.PI / 2;
    for (let x = 0; x < w; x++) {
      const lng = (x / w) * Math.PI * 2 - Math.PI;
      // Multi-octave value noise stand-in using sin/cos products.
      const n =
        Math.sin(lat * 4 + Math.cos(lng * 3)) * 0.5 +
        Math.sin(lng * 5) * 0.25 +
        Math.cos(lat * 7 + lng * 2) * 0.25;
      const land = n > 0.05 ? 1 : 0;
      const i = (y * w + x) * 4;
      if (land) {
        // green/brown landmasses
        data[i + 0] = 60 + Math.floor(40 * Math.abs(n));
        data[i + 1] = 90 + Math.floor(30 * Math.abs(n));
        data[i + 2] = 55 + Math.floor(20 * Math.abs(n));
      } else {
        // deep ocean
        data[i + 0] = 14;
        data[i + 1] = 30 + Math.floor(10 * Math.cos(lat * 3));
        data[i + 2] = 60 + Math.floor(20 * Math.sin(lng * 2));
      }
      data[i + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.needsUpdate = true;
  return tex;
}

export function EarthMesh() {
  const matRef = useRef<THREE.ShaderMaterial>(null!);
  const gl = useThree((s) => s.gl);

  const fallback = useMemo(() => makeFallbackTexture(), []);
  const [texture, setTexture] = useState<THREE.Texture>(fallback);

  useEffect(() => {
    const loader = new THREE.TextureLoader();
    loader.load(
      "/textures/earth-day.jpg",
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.wrapS = THREE.RepeatWrapping;
        tex.wrapT = THREE.ClampToEdgeWrapping;
        tex.anisotropy = gl.capabilities.getMaxAnisotropy?.() ?? 1;
        tex.needsUpdate = true;
        setTexture(tex);
      },
      undefined,
      () => {
        // file missing — keep the procedural fallback
      }
    );
  }, [gl]);

  const uniforms = useMemo(
    () => ({
      uMorph: { value: 0 },
      uDayMap: { value: texture },
    }),
    [texture]
  );

  // Keep uDayMap pointed at the latest texture without recreating the material.
  useEffect(() => {
    if (matRef.current) {
      (matRef.current.uniforms.uDayMap as { value: THREE.Texture }).value = texture;
    }
  }, [texture]);

  useFrame(() => {
    const t = useObservatoryStore.getState().morphT;
    if (matRef.current) {
      (matRef.current.uniforms.uMorph as { value: number }).value = t;
    }
  });

  return (
    <mesh>
      <sphereGeometry args={[1, 256, 128]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={EARTH_VERTEX_SHADER}
        fragmentShader={EARTH_FRAGMENT_SHADER}
        uniforms={uniforms}
      />
    </mesh>
  );
}
