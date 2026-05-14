"use client";

import ReactMarkdown from "react-markdown";

import { useObservatoryStore } from "@/store/useObservatoryStore";

export function BriefCard() {
  const brief = useObservatoryStore((s) => s.latestBrief);
  const running = useObservatoryStore((s) => s.briefRunning);

  if (!brief && !running) {
    return (
      <div className="rounded-lg border border-line bg-panel px-3 py-3 text-xs text-muted">
        no brief yet — click <span className="text-[#a78bfa]">Run reasoning</span> to ask the 26B for a world risk brief.
      </div>
    );
  }

  return (
    <div
      className={`relative rounded-lg border border-line bg-panel px-3 py-3 ${
        running ? "ring-2 ring-[#a78bfa] animate-pulse" : ""
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.2em] text-[#a78bfa]">
          world risk brief
        </span>
        {brief && (
          <span className="font-mono text-[10px] text-muted">
            {brief.model} · {brief.latency_ms}ms
          </span>
        )}
      </div>
      {brief ? (
        <div className="prose prose-invert prose-sm max-w-none text-fg [&_h2]:mt-3 [&_h2]:mb-1 [&_h2]:text-[12px] [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[#a78bfa] [&_li]:my-0.5 [&_p]:my-1 [&_ul]:my-1 [&_ul]:pl-4">
          <ReactMarkdown>{brief.markdown}</ReactMarkdown>
        </div>
      ) : (
        <div className="py-4 text-center text-xs text-muted">
          gemma4:26b-a4b reasoning…
        </div>
      )}
    </div>
  );
}
