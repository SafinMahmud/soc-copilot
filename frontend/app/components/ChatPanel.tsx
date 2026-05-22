"use client";

import { useRef, useEffect, useState } from "react";
import clsx from "clsx";
import type { InputMode } from "@/lib/detect-mode";
import type { ChatMessage } from "@/lib/types";

const STARTER_PROMPTS = [
  "Show me failed logins in the last 6 hours",
  "Investigate IP 23.20.239.12",
  "Find all port scanning activity",
  "Investigate user administrator",
];

export function ChatPanel({
  messages,
  onSend,
  isLoading,
  inputMode,
  onStarterClick,
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  isLoading: boolean;
  inputMode: InputMode;
  onStarterClick: (text: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex h-full flex-col border-r border-soc-border bg-soc-panel/40">
      <div className="flex items-center justify-between border-b border-soc-border px-4 py-3">
        <h1 className="text-sm font-semibold tracking-wide text-white">
          SOC Copilot
        </h1>
        <span
          className={clsx(
            "rounded-full px-2.5 py-0.5 text-xs font-medium",
            inputMode === "investigate"
              ? "bg-red-600/20 text-red-400"
              : "bg-blue-600/20 text-blue-400"
          )}
        >
          {inputMode === "investigate" ? "Investigate Mode" : "Query Mode"}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Ask in plain English — SPL generation or autonomous investigation.
            </p>
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => onStarterClick(prompt)}
                className="block w-full rounded-lg border border-soc-border bg-soc-panel/60 px-3 py-2 text-left text-sm text-gray-300 hover:border-blue-500/50 hover:text-white"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && (
          <div className="space-y-2 animate-pulse">
            <div className="h-4 w-3/4 rounded bg-white/10" />
            <div className="h-4 w-1/2 rounded bg-white/10" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-soc-border p-4">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your Splunk data..."
          rows={3}
          disabled={isLoading}
          className="w-full resize-none rounded-lg border border-soc-border bg-soc-bg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:border-blue-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !input.trim()}
          className="mt-2 w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
        >
          {isLoading ? "Running..." : "Send"}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-blue-600/30 px-3 py-2 text-sm text-white">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.type === "query_preview") {
    const truncated =
      message.spl.length > 80 ? message.spl.slice(0, 80) + "…" : message.spl;
    return (
      <div className="max-w-[90%] rounded-lg bg-soc-panel px-3 py-2 text-sm text-gray-300">
        Found {message.resultCount} results for:{" "}
        <code className="text-xs text-emerald-400/90">{truncated}</code>
        <p className="mt-1 text-xs text-gray-500">See full results in the report panel →</p>
      </div>
    );
  }

  if (message.type === "investigation_progress") {
    return (
      <div className="max-w-[90%] rounded-lg bg-red-950/30 px-3 py-2 text-sm text-red-200/90">
        Investigating {message.entity}… running Splunk queries autonomously…
      </div>
    );
  }

  if (message.type === "investigation_complete") {
    return (
      <div className="max-w-[90%] rounded-lg bg-soc-panel px-3 py-2 text-sm">
        <p className="font-medium text-white">
          Investigation complete. Severity: {message.severity.toUpperCase()}
        </p>
        <p className="mt-1 text-gray-400">{message.summary}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[90%] rounded-lg bg-soc-panel px-3 py-2 text-sm text-gray-300">
      {message.content}
    </div>
  );
}
