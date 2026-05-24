"use client";

import clsx from "clsx";

export type IRPhase =
  | "Triage"
  | "Investigation"
  | "Analysis"
  | "Containment/Remediation";

export const IR_PHASES: IRPhase[] = [
  "Triage",
  "Investigation",
  "Analysis",
  "Containment/Remediation",
];

export type PlaybookStep = {
  id: string;
  label: string;
  phase: IRPhase;
  autoComplete: boolean;
};

export function buildPlaybook(entityType: string): PlaybookStep[] {
  const base = [
    { id: "scope", label: "Validate alert scope and entity context", phase: "Triage" as IRPhase, autoComplete: true },
    { id: "auth-fail", label: "Review failed authentication activity", phase: "Triage" as IRPhase, autoComplete: false },
    { id: "auth-success", label: "Review successful authentication activity", phase: "Investigation" as IRPhase, autoComplete: false },
    { id: "network", label: "Analyze network connections and data movement", phase: "Investigation" as IRPhase, autoComplete: false },
    { id: "audit", label: "Correlate audit trail and analyst actions", phase: "Investigation" as IRPhase, autoComplete: false },
    { id: "raw-evidence", label: "Collect raw event evidence for the entity", phase: "Investigation" as IRPhase, autoComplete: false },
    { id: "mitre", label: "Map findings to MITRE ATT&CK techniques", phase: "Analysis" as IRPhase, autoComplete: true },
    { id: "severity", label: "Confirm severity and confidence rating", phase: "Analysis" as IRPhase, autoComplete: true },
    { id: "remediation", label: "Generate prioritized remediation playbook", phase: "Containment/Remediation" as IRPhase, autoComplete: true },
    { id: "containment", label: "Execute approval-gated containment actions", phase: "Containment/Remediation" as IRPhase, autoComplete: false },
  ];

  if (entityType === "user") {
    return base.map((s) =>
      s.id === "network"
        ? { ...s, label: "Review user network and application activity" }
        : s
    );
  }
  if (entityType === "host") {
    return base.map((s) =>
      s.id === "auth-fail"
        ? { ...s, label: "Review host authentication failures" }
        : s
    );
  }
  return base;
}

export function derivePlaybookCompletion(
  playbook: PlaybookStep[],
  traceDescriptions: string[],
  traceRows: number[],
  hasMitre: boolean,
  hasRemediation: boolean,
  actionCount: number
): Record<string, boolean> {
  const desc = traceDescriptions.map((d) => d.toLowerCase());
  const rows = traceRows;
  const hasKeyword = (keywords: string[]) =>
    desc.some((d, i) => keywords.some((k) => d.includes(k)) && rows[i] > 0);

  return Object.fromEntries(
    playbook.map((step) => {
      let done = step.autoComplete;
      if (step.id === "auth-fail") {
        done = hasKeyword(["failure", "failed", "4625"]);
      } else if (step.id === "auth-success") {
        done = hasKeyword(["success", "4624", "succeeded"]);
      } else if (step.id === "network") {
        done = hasKeyword(["network", "transfer", "tcp", "stream"]);
      } else if (step.id === "audit") {
        done = hasKeyword(["audit"]);
      } else if (step.id === "raw-evidence") {
        done = rows.some((r) => r > 0);
      } else if (step.id === "mitre") {
        done = hasMitre;
      } else if (step.id === "severity") {
        done = hasMitre && rows.some((r) => r > 0);
      } else if (step.id === "remediation") {
        done = hasRemediation;
      } else if (step.id === "containment") {
        done = actionCount > 0;
      }
      return [step.id, done];
    })
  );
}

export function inferCurrentPhase(
  completion: Record<string, boolean>,
  playbook: PlaybookStep[]
): IRPhase {
  const triageDone = playbook
    .filter((s) => s.phase === "Triage")
    .every((s) => completion[s.id]);
  const investigationDone = playbook
    .filter((s) => s.phase === "Investigation")
    .every((s) => completion[s.id]);
  const analysisDone = playbook
    .filter((s) => s.phase === "Analysis")
    .every((s) => completion[s.id]);

  if (!triageDone) return "Triage";
  if (!investigationDone) return "Investigation";
  if (!analysisDone) return "Analysis";
  return "Containment/Remediation";
}

export function buildNextSteps(
  phase: IRPhase,
  completion: Record<string, boolean>,
  playbook: PlaybookStep[],
  severity: string
): string[] {
  const pending = playbook.filter((s) => !completion[s.id]);
  const steps: string[] = [];

  if (pending.length > 0) {
    steps.push(`Complete playbook step: ${pending[0].label}`);
  }

  if (phase === "Triage") {
    steps.push("Review Copilot query 1-2 outputs and confirm entity ownership.");
  } else if (phase === "Investigation") {
    steps.push("Validate security trace events against Copilot query evidence.");
  } else if (phase === "Analysis") {
    steps.push("Confirm MITRE mapping and severity rationale with peer review.");
  } else {
    steps.push("Approve Copilot suggested containment actions or escalate to Tier 3.");
    if (severity === "Critical" || severity === "High") {
      steps.push("Notify on-call and create incident ticket draft.");
    }
  }

  if (pending.length > 1) {
    steps.push(`Next queued step: ${pending[1].label}`);
  }

  return steps.slice(0, 4);
}

export function PhaseChevronBar({
  currentPhase,
  onSelect,
}: {
  currentPhase: IRPhase;
  onSelect?: (phase: IRPhase) => void;
}) {
  const currentIdx = IR_PHASES.indexOf(currentPhase);

  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-max items-stretch">
        {IR_PHASES.map((phase, idx) => {
          const isCurrent = phase === currentPhase;
          const isComplete = idx < currentIdx;
          return (
            <button
              key={phase}
              type="button"
              onClick={() => onSelect?.(phase)}
              className={clsx(
                "relative flex items-center px-4 py-2 text-xs font-medium transition",
                "first:rounded-l-md last:rounded-r-md",
                isCurrent
                  ? "bg-blue-600/30 text-blue-100 ring-1 ring-blue-500/50"
                  : isComplete
                    ? "bg-emerald-600/15 text-emerald-200"
                    : "bg-soc-bg text-gray-400 hover:bg-soc-panel"
              )}
              style={{
                clipPath:
                  idx < IR_PHASES.length - 1
                    ? "polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%, 10px 50%)"
                    : "polygon(0 0, 100% 0, 100% 100%, 0 100%, 10px 50%)",
                marginLeft: idx === 0 ? 0 : -6,
                paddingRight: idx < IR_PHASES.length - 1 ? 18 : 12,
                paddingLeft: idx === 0 ? 12 : 18,
              }}
            >
              {phase}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function PlaybookChecklist({
  playbook,
  completion,
}: {
  playbook: PlaybookStep[];
  completion: Record<string, boolean>;
}) {
  return (
    <div className="space-y-2">
      {playbook.map((step, idx) => {
        const done = completion[step.id];
        return (
          <div
            key={step.id}
            className={clsx(
              "flex items-start gap-3 rounded border px-3 py-2 text-sm",
              done
                ? "border-emerald-500/30 bg-emerald-600/10"
                : "border-soc-border bg-soc-bg"
            )}
          >
            <span
              className={clsx(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                done ? "bg-emerald-600/30 text-emerald-200" : "bg-white/10 text-gray-400"
              )}
            >
              {done ? "\u2713" : idx + 1}
            </span>
            <div>
              <p className={clsx("font-medium", done ? "text-emerald-100" : "text-white")}>
                {step.label}
              </p>
              <p className="text-xs text-gray-500">{step.phase}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function SecurityTraceTimeline({
  copilotSteps,
  securityEvents,
}: {
  copilotSteps: Array<{
    step: number;
    description: string;
    evidenceRows: number;
    hasError: boolean;
  }>;
  securityEvents: Array<{ step: number; description: string; severity: string }>;
}) {
  const maxSteps = Math.max(copilotSteps.length, securityEvents.length, 1);

  return (
    <div className="space-y-2">
      <div className="hidden grid-cols-[1fr_1fr] gap-3 text-xs font-medium uppercase tracking-wide text-gray-500 md:grid">
        <span>Copilot Steps (1-{maxSteps})</span>
        <span>Security Trace Events (1-{maxSteps})</span>
      </div>
      {Array.from({ length: maxSteps }, (_, i) => {
        const copilot = copilotSteps[i];
        const event = securityEvents[i];
        return (
          <div
            key={i}
            className="grid gap-2 rounded border border-soc-border/60 bg-soc-bg p-3 md:grid-cols-2"
          >
            <div>
              <p className="text-xs font-medium text-blue-300">
                Copilot {i + 1}
                {copilot ? `: ${copilot.description}` : ""}
              </p>
              {copilot ? (
                <p className="mt-1 text-xs text-gray-400">
                  {copilot.hasError
                    ? "Query error - review SPL"
                    : `${copilot.evidenceRows} evidence rows`}
                </p>
              ) : (
                <p className="mt-1 text-xs text-gray-500">-</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-amber-200">
                Event {i + 1}
                {event ? `: ${event.description}` : ""}
              </p>
              {event ? (
                <p className="mt-1 text-xs capitalize text-gray-400">
                  Severity: {event.severity}
                </p>
              ) : (
                <p className="mt-1 text-xs text-gray-500">No correlated event</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
