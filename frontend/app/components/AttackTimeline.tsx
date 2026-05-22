"use client";

import { useState } from "react";
import clsx from "clsx";
import type { TimelineEvent } from "@/lib/types";

const DOT_COLORS: Record<string, string> = {
  auth: "bg-red-500",
  network: "bg-blue-500",
  process: "bg-orange-500",
  file: "bg-purple-500",
};

const LEGEND = [
  { type: "auth", label: "Auth", color: "bg-red-500" },
  { type: "network", label: "Network", color: "bg-blue-500" },
  { type: "process", label: "Process", color: "bg-orange-500" },
  { type: "file", label: "File", color: "bg-purple-500" },
];

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return {
      date: d.toLocaleDateString(),
      time: d.toLocaleTimeString(),
    };
  } catch {
    return { date: iso.slice(0, 10), time: iso.slice(11, 19) };
  }
}

export function AttackTimeline({ events }: { events: TimelineEvent[] }) {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Attack Timeline</h3>
      <div className="flex flex-wrap gap-4 text-xs text-gray-400">
        {LEGEND.map((item) => (
          <span key={item.type} className="flex items-center gap-2">
            <span className={clsx("h-2.5 w-2.5 rounded-full", item.color)} />
            {item.label}
          </span>
        ))}
      </div>

      <div className="relative space-y-0">
        {sorted.map((event, i) => (
          <TimelineRow
            key={`${event.timestamp}-${i}`}
            event={event}
            isLast={i === sorted.length - 1}
          />
        ))}
        {sorted.length === 0 && (
          <p className="text-sm text-gray-500">No timeline events.</p>
        )}
      </div>
    </div>
  );
}

function TimelineRow({
  event,
  isLast,
}: {
  event: TimelineEvent;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { date, time } = formatTime(event.timestamp);
  const dot = DOT_COLORS[event.event_type] ?? "bg-gray-500";

  return (
    <div className="flex gap-4 pb-6">
      <div className="w-24 shrink-0 text-right text-xs text-gray-500">
        <div>{date}</div>
        <div className="font-mono text-gray-400">{time}</div>
      </div>

      <div className="relative flex w-6 shrink-0 flex-col items-center">
        <span className={clsx("z-10 h-3 w-3 rounded-full ring-4 ring-soc-bg", dot)} />
        {!isLast && (
          <span className="absolute top-3 bottom-0 w-0.5 bg-soc-border" />
        )}
      </div>

      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex-1 rounded-lg border border-soc-border bg-soc-panel/80 p-4 text-left transition hover:border-gray-500"
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold text-white">{event.description}</p>
          <span className="rounded bg-white/10 px-2 py-0.5 text-xs capitalize text-gray-300">
            {event.event_type}
          </span>
          <span className="rounded bg-white/5 px-2 py-0.5 text-xs capitalize text-gray-400">
            {event.severity}
          </span>
        </div>
        {expanded && (
          <pre className="mt-3 max-h-40 overflow-auto rounded bg-black/40 p-2 font-mono text-xs text-gray-400">
            {event.raw_log}
          </pre>
        )}
        {!expanded && (
          <p className="mt-1 text-xs text-gray-500">Click to view raw log</p>
        )}
      </button>
    </div>
  );
}
