"use client";

import { useEffect } from "react";

import { api, fetchModels } from "@/lib/api";
import { subscribe } from "@/lib/sse";
import type { ModelInfo, PersistedBrief } from "@/lib/types";
import { useObservatoryStore } from "@/store/useObservatoryStore";

interface RawEnvelope {
  kind?: string;
  brief?: PersistedBrief;
}

export function useBriefStream() {
  const applyBrief = useObservatoryStore((s) => s.applyBrief);

  useEffect(() => {
    const off = subscribe<RawEnvelope | PersistedBrief>(api.briefStream(), (payload) => {
      if ((payload as RawEnvelope).brief) {
        applyBrief((payload as RawEnvelope).brief!);
      }
    });
    return off;
  }, [applyBrief]);
}

export function useModelInfo() {
  const setModelInfo = useObservatoryStore((s) => s.setModelInfo);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const info = (await fetchModels()) as ModelInfo;
        if (!cancelled) setModelInfo(info);
      } catch {
        // ignore
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [setModelInfo]);
}
