import type { InvestigationReport, SPLResult } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export async function queryNaturalLanguage(
  message: string,
  timeRange = "-24h"
): Promise<SPLResult> {
  const res = await fetch(`${BASE_URL}/api/query`, {
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
  const res = await fetch(`${BASE_URL}/api/investigate`, {
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
  ai_provider?: "gemini" | "mock" | string;
  model?: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
