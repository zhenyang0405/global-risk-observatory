"use client";

import { useEffect } from "react";

import { api } from "@/lib/api";
import { subscribe } from "@/lib/sse";
import type { PersistedEvent } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

interface RawEnvelope {
  kind?: string;
  event?: PersistedEvent;
}

export function useEventsStream() {
  const applyEvent = useObservatoryStore((s) => s.applyEvent);

  useEffect(() => {
    const off = subscribe<RawEnvelope | PersistedEvent>(api.eventsStream(), (payload) => {
      if ((payload as RawEnvelope).event) {
        const e = (payload as RawEnvelope).event!;
        if (e.lat !== null && e.lng !== null) applyEvent(e);
      }
    });
    return off;
  }, [applyEvent]);
}
