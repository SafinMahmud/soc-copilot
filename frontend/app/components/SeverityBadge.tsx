import clsx from "clsx";

const STYLES: Record<string, string> = {
  critical: "bg-red-600/20 text-red-400 border-red-500/50",
  high: "bg-orange-600/20 text-orange-400 border-orange-500/50",
  medium: "bg-yellow-600/20 text-yellow-400 border-yellow-500/50",
  low: "bg-green-600/20 text-green-400 border-green-500/50",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const key = severity.toLowerCase();
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-3 py-1 text-sm font-semibold uppercase tracking-wide",
        STYLES[key] ?? STYLES.medium
      )}
    >
      {severity}
    </span>
  );
}
