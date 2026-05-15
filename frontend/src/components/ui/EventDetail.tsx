"use client";

import { CATEGORY_COLOR } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

export function EventDetail() {
  const selectedId = useObservatoryStore((s) => s.selectedEventId);
  const selectEvent = useObservatoryStore((s) => s.selectEvent);
  const event = useObservatoryStore((s) =>
    selectedId ? s.events.get(selectedId) : undefined
  );
  if (!event) return null;
  const color = CATEGORY_COLOR[event.category] ?? "#9ca3af";
  // image_local_path is the sha256 stem (no extension); the FastAPI route
  // exposes the cached jpg at /images/<hash>.jpg, proxied under /api/.
  const cachedImage = event.image_local_path
    ? `/api/images/${event.image_local_path}.jpg`
    : null;
  return (
    <div className="pointer-events-auto absolute bottom-4 left-4 z-10 max-w-md rounded-lg border border-line bg-bg/95 px-4 py-3 backdrop-blur">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] text-muted">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: color, boxShadow: `0 0 6px ${color}` }}
            />
            <span className="uppercase tracking-wider">{event.category}</span>
            <span>·</span>
            <span>{event.severity}</span>
            <span>·</span>
            <span className="font-mono">{event.primary_location}</span>
            {event.country_iso && (
              <>
                <span>·</span>
                <span className="font-mono">{event.country_iso}</span>
              </>
            )}
          </div>
          <h3 className="mt-1 text-sm font-medium text-fg">{event.title}</h3>
        </div>
        <button
          onClick={() => selectEvent(null)}
          className="text-muted transition-colors hover:text-fg"
          aria-label="close"
        >
          ✕
        </button>
      </div>
      {cachedImage && (
        <figure className="-mx-1 mb-2 overflow-hidden rounded-md ring-1 ring-line">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={cachedImage}
            alt={event.image_caption ?? event.title}
            className="block max-h-48 w-full object-cover"
            loading="lazy"
          />
          {event.image_caption && (
            <figcaption className="bg-[#0e131b] px-2 py-1 text-[10px] italic text-muted">
              {event.image_caption}
            </figcaption>
          )}
        </figure>
      )}
      <p className="text-[12px] leading-relaxed text-fg/85">{event.summary}</p>
      {event.key_entities.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {event.key_entities.map((e) => (
            <span
              key={e}
              className="rounded bg-[#0e131b] px-1.5 py-0.5 text-[10px] text-muted ring-1 ring-line"
            >
              {e}
            </span>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between text-[10px] text-muted">
        <a
          href={event.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-[#7c9cff] hover:underline"
        >
          source ↗
        </a>
        <span className="font-mono">
          ⚡ {event.model} · {event.latency_ms}ms
        </span>
      </div>
    </div>
  );
}
