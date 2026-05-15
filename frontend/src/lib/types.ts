// Lockstep with backend/src/risk_observatory/schemas.py.
// When you change one, change both in the same commit.

export type RiskCategory =
  | "conflict"
  | "protest"
  | "disaster"
  | "disease"
  | "economic"
  | "displacement"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";

export type Escalation = "cooling" | "steady" | "escalating";

export type SourceKind =
  | "gdelt"
  | "reuters"
  | "ap"
  | "bbc"
  | "aljazeera"
  | "manual"
  | "usgs"
  | "eonet";

export interface PersistedEvent {
  id: string;
  url: string;
  title: string;
  summary: string;
  primary_location: string;
  country_iso: string | null;
  lat: number | null;
  lng: number | null;
  category: RiskCategory;
  severity: Severity;
  key_entities: string[];
  sentiment: number;
  source: SourceKind;
  published_at: string;
  classified_at: string;
  model: string;
  latency_ms: number;
  image_url?: string | null;
  image_local_path?: string | null;
  image_caption?: string | null;
}

export interface EventCluster {
  label: string;
  summary: string;
  event_ids: string[];
  escalation: Escalation;
}

export interface PersistedBrief {
  id: string;
  headline: string;
  hotspots: string[];
  escalation_signals: string[];
  regions_to_watch: string[];
  markdown: string;
  cluster_ids: string[];
  created_at: string;
  model: string;
  latency_ms: number;
}

export interface EventEnvelope {
  kind: "event";
  event: PersistedEvent;
}

export interface BriefEnvelope {
  kind: "brief";
  brief: PersistedBrief;
}

export type ModelInfo = {
  active: string[];
  roles: Record<"ingest" | "reason", string>;
  loaded: string[];
};

export const CATEGORY_COLOR: Record<RiskCategory, string> = {
  conflict: "#ef4444",
  protest: "#f59e0b",
  disaster: "#22d3ee",
  disease: "#a3e635",
  economic: "#a78bfa",
  displacement: "#fb923c",
  other: "#94a3b8",
};

export const SEVERITY_SCALE: Record<Severity, number> = {
  low: 0.6,
  medium: 0.9,
  high: 1.3,
  critical: 1.8,
};

export const ALL_CATEGORIES: RiskCategory[] = [
  "conflict",
  "protest",
  "disaster",
  "disease",
  "economic",
  "displacement",
  "other",
];
