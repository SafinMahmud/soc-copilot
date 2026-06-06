"use client";

import clsx from "clsx";

export type ReportSection = {
  id: string;
  label: string;
};

const DEFAULT_SECTIONS: ReportSection[] = [
  { id: "report-overview", label: "Overview" },
  { id: "report-summary", label: "Summary" },
  { id: "report-queries", label: "Queries" },
  { id: "report-timeline", label: "Timeline" },
  { id: "report-mitre", label: "MITRE" },
  { id: "report-remediation", label: "Remediation" },
];

export function ReportSectionNav({
  sections = DEFAULT_SECTIONS,
  activeId,
  onSelect,
}: {
  sections?: ReportSection[];
  activeId?: string;
  onSelect?: (id: string) => void;
}) {
  const scrollTo = (id: string) => {
    onSelect?.(id);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-0 z-10 -mx-1 mb-6 border-b border-soc-border bg-soc-bg/95 px-1 py-3 backdrop-blur-sm"
    >
      <div className="flex flex-wrap gap-2">
        {sections.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => scrollTo(section.id)}
            className={clsx(
              "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
              activeId === section.id
                ? "border-blue-500/60 bg-blue-600/25 text-blue-100"
                : "border-soc-border bg-soc-panel/60 text-gray-300 hover:border-blue-500/40 hover:text-white"
            )}
          >
            {section.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
