"use client";

import { useMemo, useState } from "react";
import type { SPLResult } from "@/lib/types";

function getColumns(results: Record<string, string>[]): string[] {
  if (results.length === 0) return [];
  const keys = Object.keys(results[0]).filter(
    (k) => !k.startsWith("_") || k === "_time"
  );
  const display = keys.map((k) => (k === "_time" ? "Time" : k));
  return display.slice(0, 10);
}

function getCell(row: Record<string, string>, col: string): string {
  const key = col === "Time" ? "_time" : col;
  const val = row[key];
  return val != null ? String(val) : "";
}

export function QueryResult({ result }: { result: SPLResult }) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const columns = useMemo(() => getColumns(result.results), [result.results]);

  const sortedRows = useMemo(() => {
    const rows = [...result.results].slice(0, 50);
    if (!sortCol) return rows;
    const key = sortCol === "Time" ? "_time" : sortCol;
    return rows.sort((a, b) => {
      const av = getCell(a, sortCol);
      const bv = getCell(b, sortCol);
      const cmp = av.localeCompare(bv, undefined, { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
  }, [result.results, sortCol, sortAsc]);

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortAsc(!sortAsc);
    else {
      setSortCol(col);
      setSortAsc(true);
    }
  };

  if (result.error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-950/40 p-4 text-red-300">
        <p className="font-semibold">Query error</p>
        <p className="mt-2 text-sm">{result.error}</p>
        <pre className="mt-4 overflow-x-auto rounded bg-black/40 p-3 text-xs text-gray-400">
          {result.spl}
        </pre>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Generated SPL</h2>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-black/50 p-4 font-mono text-sm text-emerald-300/90">
          {result.spl}
        </pre>
      </div>

      <div className="flex items-center gap-2">
        <span className="rounded-full bg-soc-accent/20 px-3 py-1 text-sm font-medium text-blue-300">
          {result.result_count} results
        </span>
      </div>

      {columns.length > 0 ? (
        <div className="overflow-auto rounded-lg border border-soc-border">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-soc-panel sticky top-0">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    className="cursor-pointer whitespace-nowrap px-4 py-2 font-medium text-gray-300 hover:text-white"
                    onClick={() => toggleSort(col)}
                  >
                    {col}
                    {sortCol === col && (sortAsc ? " ↑" : " ↓")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, i) => (
                <tr
                  key={i}
                  className="border-t border-soc-border/50 hover:bg-white/5"
                >
                  {columns.map((col) => (
                    <td
                      key={col}
                      className="max-w-xs truncate px-4 py-2 text-gray-300"
                      title={getCell(row, col)}
                    >
                      {getCell(row, col)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-500">No results returned.</p>
      )}
    </div>
  );
}
