"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";

const IP_STEPS = [
  "Connecting to Splunk Enterprise…",
  "Running playbook: authentication failures (EventCode 4625)…",
  "Running playbook: authentication successes (EventCode 4624)…",
  "Running playbook: network activity…",
  "Running playbook: audit trail actions…",
  "Running playbook: raw evidence collection…",
  "Warming Foundation-Sec analysis engine (Ollama)…",
  "Synthesizing severity, timeline, MITRE, and remediation…",
];

const USER_STEPS = [
  "Connecting to Splunk Enterprise…",
  "Running playbook: user authentication activity…",
  "Running playbook: failed logins…",
  "Running playbook: successful logins…",
  "Running playbook: audit trail for user…",
  "Running playbook: raw evidence collection…",
  "Warming Foundation-Sec analysis engine (Ollama)…",
  "Synthesizing investigation report…",
];

const HOST_STEPS = [
  "Connecting to Splunk Enterprise…",
  "Running playbook: host security events…",
  "Running playbook: authentication failures…",
  "Running playbook: process and command activity…",
  "Running playbook: host network activity…",
  "Running playbook: raw evidence collection…",
  "Warming Foundation-Sec analysis engine (Ollama)…",
  "Synthesizing investigation report…",
];

function stepsForEntityType(entityType: string): string[] {
  if (entityType === "user") return USER_STEPS;
  if (entityType === "host") return HOST_STEPS;
  return IP_STEPS;
}

export function InvestigationLoadingPanel({
  entity,
  entityType,
}: {
  entity: string;
  entityType: string;
}) {
  const steps = stepsForEntityType(entityType);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    setActiveStep(0);
    const interval = window.setInterval(() => {
      setActiveStep((prev) => Math.min(prev + 1, steps.length - 1));
    }, 7000);
    return () => window.clearInterval(interval);
  }, [entity, entityType, steps.length]);

  return (
    <div className="rounded-lg border border-blue-500/30 bg-soc-panel/80 p-5">
      <div className="flex items-center gap-3">
        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-blue-400" />
        <h3 className="text-base font-semibold text-white">
          Investigating {entity}
        </h3>
        <span className="rounded bg-white/10 px-2 py-0.5 text-xs uppercase text-gray-400">
          {entityType}
        </span>
      </div>

      <p className="mt-3 text-sm text-gray-300">
        Autonomous Splunk investigation in progress. The deterministic playbook
        runs fixed SPL queries by entity type; Foundation-Sec synthesizes the
        report after evidence is collected.
      </p>

      <p className="mt-2 text-xs text-amber-200/90">
        First run after idle may take 1–3 minutes while the LLM VM warms up.
      </p>

      <ol className="mt-5 space-y-2">
        {steps.map((label, index) => {
          const done = index < activeStep;
          const current = index === activeStep;
          return (
            <li
              key={label}
              className={clsx(
                "flex items-start gap-3 rounded-md px-2 py-2 text-sm transition-colors",
                current && "bg-blue-600/15 text-blue-100",
                done && !current && "text-emerald-300/90",
                !done && !current && "text-gray-500"
              )}
            >
              <span
                className={clsx(
                  "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                  done && "bg-emerald-600/30 text-emerald-200",
                  current && "bg-blue-600/40 text-blue-100 animate-pulse",
                  !done && !current && "bg-white/5 text-gray-500"
                )}
              >
                {done ? "✓" : index + 1}
              </span>
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
