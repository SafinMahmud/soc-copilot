export interface SPLResult {
  spl: string;
  results: Record<string, string>[];
  result_count: number;
  error?: string;
}

export interface MitreTechnique {
  technique_id: string;
  name: string;
  tactic: string;
  description: string;
}

export interface TimelineEvent {
  timestamp: string;
  event_type: "auth" | "network" | "process" | "file";
  description: string;
  raw_log: string;
  severity: "critical" | "high" | "medium" | "low";
}

export interface RemediationStep {
  priority: string;
  action: string;
  rationale: string;
}

export interface InvestigationReport {
  entity: string;
  entity_type: string;
  severity: string;
  severity_rationale: string;
  summary: string;
  timeline: TimelineEvent[];
  mitre_techniques: MitreTechnique[];
  remediation_steps: RemediationStep[];
  queries_run: string[];
  raw_findings: Record<string, unknown>;
}

export type InputMode = "query" | "investigate";

export type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      type: "text";
      content: string;
    }
  | {
      id: string;
      role: "assistant";
      type: "query_preview";
      spl: string;
      resultCount: number;
    }
  | {
      id: string;
      role: "assistant";
      type: "investigation_progress";
      entity: string;
    }
  | {
      id: string;
      role: "assistant";
      type: "investigation_complete";
      severity: string;
      summary: string;
    };
