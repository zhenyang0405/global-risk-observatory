"use client";

import { BriefCard } from "./BriefCard";
import { EventFeed } from "./EventFeed";
import { ModelStatusChips } from "./ModelStatusChip";

export function Sidebar() {
  return (
    <aside className="flex h-full w-[380px] shrink-0 flex-col border-l border-line bg-bg/95 backdrop-blur">
      <div className="border-b border-line px-4 py-3">
        <h1 className="font-display text-[15px] font-medium tracking-tight">
          Global Risk Observatory
        </h1>
        <p className="mt-0.5 text-[11px] text-muted">
          live world-risk Earth · Gemma 4
        </p>
        <div className="mt-2.5">
          <ModelStatusChips />
        </div>
      </div>

      <div className="border-b border-line px-4 py-3">
        <BriefCard />
      </div>

      <div className="flex-1 overflow-hidden px-2 py-2">
        <div className="mb-1 px-2 text-[10px] uppercase tracking-[0.2em] text-muted">
          live feed
        </div>
        <EventFeed />
      </div>
    </aside>
  );
}
