// REST API + SSE URL helpers.

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  events: () => `${BASE}/events`,
  eventsStream: () => `${BASE}/events/stream`,
  briefLatest: () => `${BASE}/brief/latest`,
  briefStream: () => `${BASE}/brief/stream`,
  briefRun: () => `${BASE}/brief/run`,
  models: () => `${BASE}/models`,
  healthz: () => `${BASE}/healthz`,
};

export async function runBrief(): Promise<void> {
  const r = await fetch(api.briefRun(), { method: "POST" });
  if (!r.ok && r.status !== 202) {
    throw new Error(`runBrief failed: ${r.status}`);
  }
}

export async function fetchModels(): Promise<unknown> {
  const r = await fetch(api.models());
  return r.json();
}
