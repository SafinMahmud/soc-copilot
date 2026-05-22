import type { MitreTechnique } from "@/lib/types";

export function MitreCards({ techniques }: { techniques: MitreTechnique[] }) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">MITRE ATT&CK Mapping</h3>
      <div className="grid gap-4 md:grid-cols-2">
        {techniques.map((t) => (
          <article
            key={t.technique_id}
            className="rounded-lg border border-soc-border bg-soc-panel/60 p-4"
          >
            <div className="mb-2 flex items-start justify-between gap-2">
              <span className="font-mono text-lg font-bold text-blue-400">
                {t.technique_id}
              </span>
              <span className="shrink-0 rounded-full bg-purple-600/20 px-2 py-0.5 text-xs text-purple-300">
                {t.tactic}
              </span>
            </div>
            <h4 className="text-base font-semibold text-white">{t.name}</h4>
            <p className="mt-2 text-sm text-gray-400">{t.description}</p>
            <a
              href={`https://attack.mitre.org/techniques/${t.technique_id}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-block text-sm text-blue-400 hover:underline"
            >
              View on attack.mitre.org →
            </a>
          </article>
        ))}
      </div>
    </div>
  );
}
