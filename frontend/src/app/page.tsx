"use client";

import dynamic from "next/dynamic";

import { EventDetail } from "@/components/ui/EventDetail";
import { Sidebar } from "@/components/ui/Sidebar";
import { TopBar } from "@/components/ui/TopBar";
import { useBriefStream, useModelInfo } from "@/hooks/useBriefStream";
import { useEventsStream } from "@/hooks/useEventsStream";

// R3F v8 dies on SSR (it reads React internals at module-load time).
// Dynamic import with ssr:false keeps it strictly client-only.
const GlobeCanvas = dynamic(
  () => import("@/components/globe/GlobeCanvas").then((m) => m.GlobeCanvas),
  { ssr: false, loading: () => <div className="h-full w-full bg-bg" /> }
);

export default function Page() {
  useEventsStream();
  useBriefStream();
  useModelInfo();

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <main className="relative flex-1">
        <GlobeCanvas />
        <TopBar />
        <EventDetail />
      </main>
      <Sidebar />
    </div>
  );
}
