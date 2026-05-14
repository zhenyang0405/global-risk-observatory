"use client";

import { CATEGORY_COLOR } from "@/lib/types";
import type { PersistedEvent } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

function formatAgo(iso: string): string {
  const d = Date.now() - new Date(iso).getTime();
  if (d < 60_000) return `${Math.floor(d / 1000)}s`;
  if (d < 3_600_000) return `${Math.floor(d / 60_000)}m`;
  if (d < 86_400_000) return `${Math.floor(d / 3_600_000)}h`;
  return `${Math.floor(d / 86_400_000)}d`;
}

export function EventFeed() {
  const events = useObservatoryStore((s) => s.events);
  const selectedId = useObservatoryStore((s) => s.selectedEventId);
  const selectEvent = useObservatoryStore((s) => s.selectEvent);
  const filters = useObservatoryStore((s) => s.filters);

  const list: PersistedEvent[] = [];
  for (const e of events.values()) {
    if (!filters.has(e.category)) continue;
    list.push(e);
  }
  list.reverse(); // newest first (Map keeps insertion order)
  const head = list.slice(0, 60);

  return (
    <div className="flex flex-col gap-px overflow-y-auto pr-1">
      {head.length === 0 && (
        <div className="px-3 py-6 text-center text-xs text-muted">
          waiting for events…
        </div>
      )}
      {head.map((e) => {
        const color = CATEGORY_COLOR[e.category] ?? "#9ca3af";
        const isSelected = e.id === selectedId;
        return (
          <button
            key={e.id}
            onClick={() => selectEvent(isSelected ? null : e.id)}
            className={`group flex items-start gap-2.5 rounded px-2.5 py-2 text-left transition-colors hover:bg-[#0e131b] ${
              isSelected ? "bg-[#10172a] ring-1 ring-[#7c9cff]/40" : ""
            }`}
          >
            <span
              className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
              style={{ background: color, boxShadow: `0 0 8px ${color}` }}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[13px] leading-tight text-fg">
                  {e.title}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-muted">
                  {formatAgo(e.classified_at)}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
                <span className="uppercase tracking-wider">{e.category}</span>
                <span>·</span>
                <span className={severityClass(e.severity)}>{e.severity}</span>
                {e.country_iso && (
                  <>
                    <span>·</span>
                    <span className="font-mono">{e.country_iso}</span>
                  </>
                )}
                <span>·</span>
                <span className="font-mono">{e.latency_ms}ms</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function severityClass(s: string): string {
  switch (s) {
    case "critical":
      return "text-[#ef4444]";
    case "high":
      return "text-[#fb923c]";
    case "medium":
      return "text-[#fbbf24]";
    default:
      return "text-[#4ade80]";
  }
}
