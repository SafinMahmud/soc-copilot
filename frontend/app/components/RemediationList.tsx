"use client";

import clsx from "clsx";
import { Copy } from "lucide-react";
import { useState } from "react";
import type { RemediationStep } from "@/lib/types";

const PRIORITY_STYLES: Record<string, string> = {
  critical: "bg-red-600/20 text-red-400",
  high: "bg-orange-600/20 text-orange-400",
  medium: "bg-yellow-600/20 text-yellow-400",
};

export function RemediationList({ steps }: { steps: RemediationStep[] }) {
  const [copied, setCopied] = useState(false);

  const copyAll = async () => {
    const text = steps
      .map(
        (s, i) =>
          `${i + 1}. [${s.priority}] ${s.action}\n   Rationale: ${s.rationale}`
      )
      .join("\n\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Remediation Playbook</h3>
      <ol className="space-y-4">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-soc-accent/30 text-sm font-bold text-blue-200">
              {i + 1}
            </span>
            <div className="flex-1">
              <span
                className={clsx(
                  "inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase",
                  PRIORITY_STYLES[step.priority.toLowerCase()] ??
                    PRIORITY_STYLES.medium
                )}
              >
                {step.priority}
              </span>
              <p className="mt-1 font-medium text-white">{step.action}</p>
              <p className="mt-1 text-sm text-gray-500">{step.rationale}</p>
            </div>
          </li>
        ))}
      </ol>
      <button
        type="button"
        onClick={copyAll}
        className="flex items-center gap-2 rounded-lg border border-soc-border bg-soc-panel px-4 py-2 text-sm hover:bg-white/5"
      >
        <Copy className="h-4 w-4" />
        {copied ? "Copied!" : "Copy all steps"}
      </button>
    </div>
  );
}
