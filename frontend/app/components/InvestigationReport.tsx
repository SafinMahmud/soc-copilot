"use client";

import { useState } from "react";
import type { InvestigationReport as Report } from "@/lib/types";
import { AttackTimeline } from "./AttackTimeline";
import { MitreCards } from "./MitreCards";
import { RemediationList } from "./RemediationList";
import { SeverityBadge } from "./SeverityBadge";

export function InvestigationReportView({ report }: { report: Report }) {
  const [queriesOpen, setQueriesOpen] = useState(false);

  return (
    <div className="space-y-8 overflow-y-auto pb-8">
      <header className="border-b border-soc-border pb-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-bold text-white">{report.entity}</h2>
          <span className="rounded bg-white/10 px-2 py-0.5 text-xs uppercase text-gray-400">
            {report.entity_type}
          </span>
          <SeverityBadge severity={report.severity} />
        </div>
        <p className="mt-2 text-sm text-gray-500">{report.severity_rationale}</p>
      </header>

      <section className="rounded-lg bg-soc-panel/80 p-4">
        <h3 className="text-sm font-medium uppercase tracking-wide text-gray-500">
          Summary
        </h3>
        <p className="mt-2 leading-relaxed text-gray-200">{report.summary}</p>
        <button
          type="button"
          onClick={() => setQueriesOpen(!queriesOpen)}
          className="mt-4 text-sm text-blue-400 hover:underline"
        >
          Queries run: {report.queries_run.length}
          {queriesOpen ? " (hide)" : " (show)"}
        </button>
        {queriesOpen && (
          <ul className="mt-3 space-y-2">
            {report.queries_run.map((spl, i) => (
              <li key={i}>
                <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-xs text-gray-400">
                  {spl}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </section>

      <AttackTimeline events={report.timeline} />
      <MitreCards techniques={report.mitre_techniques} />
      <RemediationList steps={report.remediation_steps} />
    </div>
  );
}
