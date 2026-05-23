"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { InvestigationReportView } from "./components/InvestigationReport";
import { QueryResult } from "./components/QueryResult";
import { getHealth, investigateEntity, queryNaturalLanguage } from "@/lib/api";
import { detectIntent } from "@/lib/detect-mode";
import type {
  ChatMessage,
  InvestigationReport,
  InputMode,
  SPLResult,
} from "@/lib/types";

type ResultView = "query" | "investigation" | null;

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentResult, setCurrentResult] = useState<ResultView>(null);
  const [queryResult, setQueryResult] = useState<SPLResult | null>(null);
  const [investigationReport, setInvestigationReport] =
    useState<InvestigationReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("query");
  const [error, setError] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<"chat" | "report">("chat");
  const [aiProvider, setAiProvider] = useState("gemini");
  const [aiModel, setAiModel] = useState("gemini-2.0-flash");

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const handleSend = async (text: string) => {
    const intent = detectIntent(text);
    setInputMode(intent.mode);
    setError(null);
    addMessage({ id: crypto.randomUUID(), role: "user", content: text });
    setIsLoading(true);
    setMobileTab("report");

    try {
      if (intent.mode === "investigate" && intent.entity && intent.entityType) {
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          type: "investigation_progress",
          entity: intent.entity,
        });

        const report = await investigateEntity(
          intent.entity,
          intent.entityType
        );
        setInvestigationReport(report);
        setCurrentResult("investigation");
        setQueryResult(null);

        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          type: "investigation_complete",
          severity: report.severity,
          summary: report.summary,
        });
      } else {
        const result = await queryNaturalLanguage(text);
        setQueryResult(result);
        setCurrentResult("query");
        setInvestigationReport(null);

        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          type: "query_preview",
          spl: result.spl,
          resultCount: result.result_count,
        });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setError(msg);
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        type: "text",
        content: `Error: ${msg}`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleStarter = (text: string) => {
    const intent = detectIntent(text);
    setInputMode(intent.mode);
    void handleSend(text);
  };

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const health = await getHealth();
        if (health.ai_provider) setAiProvider(health.ai_provider);
        if (health.model) setAiModel(health.model);
      } catch {
        // Keep defaults if health call fails.
      }
    };
    void loadHealth();
  }, []);

  return (
    <main className="flex h-screen flex-col">
      <div className="flex border-b border-soc-border lg:hidden">
        <button
          type="button"
          onClick={() => setMobileTab("chat")}
          className={`flex-1 py-2 text-sm ${
            mobileTab === "chat" ? "bg-soc-panel text-white" : "text-gray-500"
          }`}
        >
          Chat
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("report")}
          className={`flex-1 py-2 text-sm ${
            mobileTab === "report" ? "bg-soc-panel text-white" : "text-gray-500"
          }`}
        >
          Report
        </button>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[2fr_3fr]">
        <div
          className={`min-h-0 ${
            mobileTab === "chat" ? "flex flex-col" : "hidden lg:flex lg:flex-col"
          }`}
        >
          <ChatPanel
            messages={messages}
            onSend={handleSend}
            isLoading={isLoading}
            inputMode={inputMode}
            aiProvider={aiProvider}
            aiModel={aiModel}
            onStarterClick={handleStarter}
          />
        </div>

        <div
          className={`min-h-0 overflow-y-auto p-6 ${
            mobileTab === "report" ? "block" : "hidden lg:block"
          }`}
        >
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wide text-gray-500">
            Results
          </h2>

          {error && (
            <div className="mb-4 rounded-lg border border-red-500/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {isLoading && currentResult === null && (
            <div className="space-y-3 animate-pulse">
              <div className="h-6 w-1/3 rounded bg-white/10" />
              <div className="h-32 rounded bg-white/10" />
            </div>
          )}

          {!isLoading && currentResult === null && !error && (
            <p className="text-gray-500">
              Run a query or investigation to see results here.
            </p>
          )}

          {currentResult === "query" && queryResult && (
            <QueryResult result={queryResult} />
          )}

          {currentResult === "investigation" && investigationReport && (
            <InvestigationReportView report={investigationReport} />
          )}
        </div>
      </div>
    </main>
  );
}
