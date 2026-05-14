"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import * as THREE from "three";

import {
  CATEGORY_COLOR,
  SEVERITY_SCALE,
  type PersistedEvent,
} from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

const TEX = "https://cdn.jsdelivr.net/npm/three-globe/example/img";
const EARTH_DAY = `${TEX}/earth-blue-marble.jpg`;
const EARTH_BUMP = `${TEX}/earth-topology.png`;
const NIGHT_SKY = `${TEX}/night-sky.png`;

// Local clouds texture lives in frontend/public/textures/clouds.png
const CLOUDS_PNG = "/textures/clouds.png";

// Constants pulled directly from the canonical clouds example:
// https://github.com/vasturiano/globe.gl/blob/master/example/clouds/index.html
const CLOUDS_ALT = 0.004;
const CLOUDS_ROTATION_SPEED = -0.006; // deg/frame (counter-rotation)

interface PointDatum {
  id: string;
  lat: number;
  lng: number;
  color: string;
  severity: PersistedEvent["severity"];
  event: PersistedEvent;
}

interface ArcDatum {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color: string;
}

export function GlobeCanvas() {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  const events = useObservatoryStore((s) => s.events);
  const filters = useObservatoryStore((s) => s.filters);
  const selectedId = useObservatoryStore((s) => s.selectedEventId);
  const selectEvent = useObservatoryStore((s) => s.selectEvent);
  const autoRotate = useObservatoryStore((s) => s.autoRotate);

  const points = useMemo<PointDatum[]>(() => {
    const out: PointDatum[] = [];
    for (const e of events.values()) {
      if (e.lat == null || e.lng == null) continue;
      if (!filters.has(e.category)) continue;
      out.push({
        id: e.id,
        lat: e.lat,
        lng: e.lng,
        color: CATEGORY_COLOR[e.category] ?? "#9ca3af",
        severity: e.severity,
        event: e,
      });
    }
    return out;
  }, [events, filters]);

  const arcs = useMemo<ArcDatum[]>(() => {
    const byCat = new Map<string, PersistedEvent[]>();
    for (const e of events.values()) {
      if (e.lat == null || e.lng == null) continue;
      if (e.severity !== "high" && e.severity !== "critical") continue;
      if (!filters.has(e.category)) continue;
      const list = byCat.get(e.category) ?? [];
      list.push(e);
      byCat.set(e.category, list);
    }
    const out: ArcDatum[] = [];
    for (const list of byCat.values()) {
      for (let i = 0; i + 1 < list.length && out.length < 16; i += 2) {
        const a = list[i];
        const b = list[i + 1];
        out.push({
          startLat: a.lat as number,
          startLng: a.lng as number,
          endLat: b.lat as number,
          endLng: b.lng as number,
          color: CATEGORY_COLOR[a.category] ?? "#9ca3af",
        });
      }
    }
    return out;
  }, [events, filters]);

  // Track container size for Globe's explicit width/height props.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Mount: configure controls + inject the rotating clouds mesh.
  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;

    const controls = g.controls() as unknown as {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableZoom: boolean;
      enableDamping: boolean;
      dampingFactor: number;
    };
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 0.35;
    controls.enableZoom = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;

    g.pointOfView({ altitude: 2.4 }, 0);

    // Clouds: load the texture, build a slightly-inflated sphere, and start a
    // counter-rotation. Matches the canonical globe.gl clouds example.
    let cloudsMesh: THREE.Mesh | null = null;
    let raf = 0;
    let cancelled = false;
    new THREE.TextureLoader().load(CLOUDS_PNG, (cloudsTexture) => {
      if (cancelled) {
        cloudsTexture.dispose();
        return;
      }
      const radius = g.getGlobeRadius();
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(radius * (1 + CLOUDS_ALT), 75, 75),
        new THREE.MeshPhongMaterial({ map: cloudsTexture, transparent: true })
      );
      g.scene().add(mesh);
      cloudsMesh = mesh;

      const step = (CLOUDS_ROTATION_SPEED * Math.PI) / 180;
      const tick = () => {
        mesh.rotation.y += step;
        raf = requestAnimationFrame(tick);
      };
      tick();
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      if (cloudsMesh) {
        g.scene().remove(cloudsMesh);
        cloudsMesh.geometry.dispose();
        const mat = cloudsMesh.material as THREE.MeshPhongMaterial;
        mat.map?.dispose();
        mat.dispose();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    const controls = g.controls() as unknown as { autoRotate: boolean };
    controls.autoRotate = autoRotate;
  }, [autoRotate]);

  return (
    <div ref={containerRef} className="absolute inset-0">
      <Globe
        ref={globeRef}
        width={size.w || undefined}
        height={size.h || undefined}
        animateIn={false}
        globeImageUrl={EARTH_DAY}
        bumpImageUrl={EARTH_BUMP}
        backgroundImageUrl={NIGHT_SKY}
        atmosphereColor="#7c9cff"
        atmosphereAltitude={0.18}
        pointsData={points}
        pointLat={(d) => (d as PointDatum).lat}
        pointLng={(d) => (d as PointDatum).lng}
        pointColor={(d) => (d as PointDatum).color}
        pointAltitude={(d) =>
          (d as PointDatum).id === selectedId ? 0.025 : 0.008
        }
        pointRadius={(d) =>
          0.22 *
          (SEVERITY_SCALE[(d as PointDatum).severity] ?? 1) *
          ((d as PointDatum).id === selectedId ? 1.6 : 1)
        }
        pointResolution={8}
        pointLabel={(d) => {
          const p = d as PointDatum;
          const e = p.event;
          return `<div style="font:12px -apple-system,system-ui,sans-serif;color:#d6dbe5;background:#0e131b;border:1px solid #1c2230;border-radius:6px;padding:6px 9px;max-width:240px"><b style="color:${p.color}">${e.category}</b> · ${e.severity}<br/>${e.title}</div>`;
        }}
        onPointClick={(d) => {
          const p = d as PointDatum;
          selectEvent(p.id === selectedId ? null : p.id);
        }}
        arcsData={arcs}
        arcStartLat={(d) => (d as ArcDatum).startLat}
        arcStartLng={(d) => (d as ArcDatum).startLng}
        arcEndLat={(d) => (d as ArcDatum).endLat}
        arcEndLng={(d) => (d as ArcDatum).endLng}
        arcColor={(d: object) => (d as ArcDatum).color}
        arcDashLength={0.4}
        arcDashGap={0.2}
        arcDashAnimateTime={2200}
        arcStroke={0.35}
        arcAltitudeAutoScale={0.35}
      />
    </div>
  );
}
