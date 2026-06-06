"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { InvestigationLoadingPanel } from "./components/InvestigationLoadingPanel";
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
type ReportHistoryItem =
  | {
      id: string;
      kind: "query";
      label: string;
      result: SPLResult;
    }
  | {
      id: string;
      kind: "investigation";
      label: string;
      result: InvestigationReport;
    };

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
  const [aiProvider, setAiProvider] = useState("hf");
  const [aiModel, setAiModel] = useState("fdtn-ai/Foundation-Sec-1.1-8B-Instruct:featherless-ai");
  const [reportHistory, setReportHistory] = useState<ReportHistoryItem[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [pendingInvestigation, setPendingInvestigation] = useState<{
    entity: string;
    entityType: string;
  } | null>(null);

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const openReportPanel = useCallback(() => {
    setMobileTab("report");
  }, []);

  const selectHistoryItem = useCallback((item: ReportHistoryItem) => {
    setSelectedReportId(item.id);
    setMobileTab("report");
    if (item.kind === "query") {
      setCurrentResult("query");
      setQueryResult(item.result);
      setInvestigationReport(null);
      return;
    }
    setCurrentResult("investigation");
    setInvestigationReport(item.result);
    setQueryResult(null);
  }, []);

  const handleSend = async (text: string) => {
    const intent = detectIntent(text);
    setInputMode(intent.mode);
    setError(null);
    addMessage({ id: crypto.randomUUID(), role: "user", content: text });
    setIsLoading(true);

    try {
      if (intent.mode === "investigate" && intent.entity && intent.entityType) {
        setMobileTab("report");
        setCurrentResult(null);
        setInvestigationReport(null);
        setPendingInvestigation({
          entity: intent.entity,
          entityType: intent.entityType,
        });
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
        const historyItem: ReportHistoryItem = {
          id: crypto.randomUUID(),
          kind: "investigation",
          label: `Investigation: ${intent.entity}`,
          result: report,
        };
        setReportHistory((prev) => [historyItem, ...prev]);
        setSelectedReportId(historyItem.id);

        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          type: "investigation_complete",
          severity: report.severity,
          summary: report.summary,
        });
      } else {
        setMobileTab("chat");
        const result = await queryNaturalLanguage(text);
        setQueryResult(result);
        setCurrentResult("query");
        setInvestigationReport(null);
        const historyItem: ReportHistoryItem = {
          id: crypto.randomUUID(),
          kind: "query",
          label: `Query: ${text.slice(0, 48)}${text.length > 48 ? "..." : ""}`,
          result,
        };
        setReportHistory((prev) => [historyItem, ...prev]);
        setSelectedReportId(historyItem.id);

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
      setPendingInvestigation(null);
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
            onOpenReport={openReportPanel}
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

          {reportHistory.length > 0 && (
            <div className="mb-4 rounded-lg border border-soc-border bg-soc-panel/40 p-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                Report History
              </p>
              <div className="flex flex-wrap gap-2">
                {reportHistory.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectHistoryItem(item)}
                    className={`rounded-md border px-2.5 py-1 text-xs ${
                      selectedReportId === item.id
                        ? "border-blue-500/60 bg-blue-600/20 text-blue-200"
                        : "border-soc-border bg-soc-bg text-gray-300 hover:border-blue-500/40"
                    }`}
                    title={item.label}
                  >
                    {item.kind === "query" ? "Query" : "Investigation"}:{" "}
                    {item.label.replace(/^Query: |^Investigation: /, "")}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-500/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {isLoading && pendingInvestigation && (
            <InvestigationLoadingPanel
              entity={pendingInvestigation.entity}
              entityType={pendingInvestigation.entityType}
            />
          )}

          {isLoading && !pendingInvestigation && currentResult === null && (
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
