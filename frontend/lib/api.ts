import type { InvestigationReport, SPLResult } from "./types";

// Same-origin /api/* is proxied to the backend via next.config.mjs rewrites.
// BACKEND_URL is read at runtime on the Next server (Cloud Run env var).
const API_BASE = "";

export async function queryNaturalLanguage(
  message: string,
  timeRange = "-24h"
): Promise<SPLResult> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, time_range: timeRange }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function investigateEntity(
  entity: string,
  entityType: string,
  timeRange = "-24h"
): Promise<InvestigationReport> {
  const res = await fetch(`${API_BASE}/api/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      entity,
      entity_type: entityType,
      time_range: timeRange,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface HealthResponse {
  status: "ok";
  ai_provider?: "hf" | "mock" | string;
  model?: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
