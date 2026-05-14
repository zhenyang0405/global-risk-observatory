"use client";

import { Stars as DreiStars } from "@react-three/drei";

export function Stars() {
  return (
    <DreiStars
      radius={50}
      depth={50}
      count={4000}
      factor={3}
      saturation={0}
      fade
      speed={0.3}
    />
  );
}
