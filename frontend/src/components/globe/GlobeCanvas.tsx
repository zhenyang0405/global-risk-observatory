"use client";

import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";

import { Atmosphere } from "./Atmosphere";
import { CameraRig } from "./CameraRig";
import { EarthMesh } from "./EarthMesh";
import { EventArcs } from "./EventArcs";
import { EventMarkers } from "./EventMarkers";
import { Stars } from "./Stars";

export function GlobeCanvas() {
  return (
    <Canvas
      camera={{ position: [0, 0.8, 3.0], fov: 45, near: 0.01, far: 100 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: false }}
      style={{ background: "#06080c" }}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[5, 3, 5]} intensity={0.85} />
        <Stars />
        <Atmosphere />
        <EarthMesh />
        <EventArcs />
        <EventMarkers />
        <CameraRig />
      </Suspense>
    </Canvas>
  );
}
