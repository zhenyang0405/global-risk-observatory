"use client";

import { useObservatoryStore } from "@/store/useObservatoryStore";

export function ModelStatusChips() {
  const info = useObservatoryStore((s) => s.modelInfo);
  if (!info) {
    return (
      <div className="flex gap-2 text-xs text-muted">
        <span className="opacity-50">models loading…</span>
      </div>
    );
  }
  const loaded = new Set(info.loaded);
  const ingestLoaded = loaded.has(info.roles.ingest);
  const reasonLoaded = loaded.has(info.roles.reason);

  return (
    <div className="flex flex-wrap gap-2 text-[11px]">
      <Chip label={`⚡ ${info.roles.ingest}`} loaded={ingestLoaded} hue="accent" />
      <Chip label={`🧠 ${info.roles.reason}`} loaded={reasonLoaded} hue="violet" />
    </div>
  );
}

function Chip({
  label,
  loaded,
  hue,
}: {
  label: string;
  loaded: boolean;
  hue: "accent" | "violet";
}) {
  const ring = hue === "violet" ? "ring-[#a78bfa]/50" : "ring-[#7c9cff]/60";
  const dot = loaded
    ? hue === "violet"
      ? "bg-[#a78bfa]"
      : "bg-[#7c9cff]"
    : "bg-[#3b4150]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-[#0e131b] px-2.5 py-1 ring-1 ${ring}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      <span className="font-mono tabular-nums">{label}</span>
    </span>
  );
}
