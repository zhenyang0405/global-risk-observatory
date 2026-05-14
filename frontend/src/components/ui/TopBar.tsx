"use client";

import { useEffect } from "react";

import { runBrief } from "@/lib/api";
import { ALL_CATEGORIES, CATEGORY_COLOR } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

export function TopBar() {
  const morphT = useObservatoryStore((s) => s.morphT);
  const animating = useObservatoryStore((s) => s.morphAnimating);
  const startMorph = useObservatoryStore((s) => s.startMorph);
  const filters = useObservatoryStore((s) => s.filters);
  const toggleFilter = useObservatoryStore((s) => s.toggleFilter);
  const briefRunning = useObservatoryStore((s) => s.briefRunning);
  const setBriefRunning = useObservatoryStore((s) => s.setBriefRunning);

  const isFlat = morphT > 0.5;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "f" && !e.metaKey && !e.ctrlKey) {
        startMorph(isFlat ? 0 : 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFlat, startMorph]);

  const handleRun = async () => {
    if (briefRunning) return;
    setBriefRunning(true);
    try {
      await runBrief();
    } catch {
      setBriefRunning(false);
    }
    // useBriefStream will flip briefRunning back to false when the new brief arrives.
  };

  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between p-4">
      <div className="pointer-events-auto flex items-center gap-2">
        <button
          onClick={() => startMorph(isFlat ? 0 : 1)}
          disabled={animating}
          className="rounded-md bg-panel px-3 py-1.5 text-xs font-medium ring-1 ring-line transition-all hover:ring-[#7c9cff]/60 disabled:opacity-50"
        >
          {isFlat ? "🌐 Sphere" : "🗺 Flat"}
          <span className="ml-2 font-mono text-[10px] text-muted">F</span>
        </button>
        <div className="flex items-center gap-1 rounded-md bg-panel px-2 py-1 ring-1 ring-line">
          {ALL_CATEGORIES.map((c) => {
            const active = filters.has(c);
            const color = CATEGORY_COLOR[c];
            return (
              <button
                key={c}
                onClick={() => toggleFilter(c)}
                title={c}
                className={`h-5 w-5 rounded-full transition-all ${
                  active ? "scale-100" : "scale-75 opacity-30"
                }`}
                style={{
                  background: color,
                  boxShadow: active ? `0 0 8px ${color}` : "none",
                }}
              />
            );
          })}
        </div>
      </div>
      <div className="pointer-events-auto">
        <button
          onClick={handleRun}
          disabled={briefRunning}
          className={`rounded-md px-3 py-1.5 text-xs font-medium ring-1 transition-all disabled:opacity-50 ${
            briefRunning
              ? "bg-[#1c1338] text-[#c4b5fd] ring-[#a78bfa]"
              : "bg-panel ring-line hover:ring-[#a78bfa]/60"
          }`}
        >
          {briefRunning ? "🧠 reasoning…" : "🧠 Run reasoning"}
        </button>
      </div>
    </header>
  );
}
