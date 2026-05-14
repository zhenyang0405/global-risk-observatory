import { create } from "zustand";

import type {
  ModelInfo,
  PersistedBrief,
  PersistedEvent,
  RiskCategory,
} from "@/lib/types";
import { ALL_CATEGORIES } from "@/lib/types";

interface ObservatoryState {
  events: Map<string, PersistedEvent>;
  latestBrief: PersistedBrief | null;
  autoRotate: boolean;
  filters: Set<RiskCategory>;
  selectedEventId: string | null;
  modelInfo: ModelInfo | null;
  briefRunning: boolean;

  applyEvent: (e: PersistedEvent) => void;
  applyBrief: (b: PersistedBrief) => void;
  toggleAutoRotate: () => void;
  setAutoRotate: (v: boolean) => void;
  toggleFilter: (c: RiskCategory) => void;
  selectEvent: (id: string | null) => void;
  setModelInfo: (info: ModelInfo) => void;
  setBriefRunning: (b: boolean) => void;
}

export const useObservatoryStore = create<ObservatoryState>((set) => ({
  events: new Map(),
  latestBrief: null,
  autoRotate: true,
  filters: new Set(ALL_CATEGORIES),
  selectedEventId: null,
  modelInfo: null,
  briefRunning: false,

  applyEvent: (e) =>
    set((s) => {
      const next = new Map(s.events);
      next.set(e.id, e);
      if (next.size > 2000) {
        const oldest = next.keys().next().value;
        if (oldest !== undefined) next.delete(oldest);
      }
      return { events: next };
    }),

  applyBrief: (b) => set({ latestBrief: b, briefRunning: false }),

  toggleAutoRotate: () => set((s) => ({ autoRotate: !s.autoRotate })),

  setAutoRotate: (v) => set({ autoRotate: v }),

  toggleFilter: (c) =>
    set((s) => {
      const next = new Set(s.filters);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return { filters: next };
    }),

  selectEvent: (id) => set({ selectedEventId: id }),

  setModelInfo: (info) => set({ modelInfo: info }),

  setBriefRunning: (b) => set({ briefRunning: b }),
}));
