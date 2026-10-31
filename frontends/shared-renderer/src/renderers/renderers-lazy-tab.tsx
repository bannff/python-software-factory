"use client";

import React, { useRef } from "react";
import { unwrapToolResult } from "../tool-result";
import { useBridge } from "../bridge-adapter-context";

export type TabDef = {
  id: string;
  label: string;
  lazy_tool?: string;
  result_hints?: {
    prefer?: string;
    columns?: { key: string; label: string }[];
    searchable?: boolean;
    sortable?: boolean;
    group_by?: string;
  };
};

function extractRows(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data;
  if (typeof data === "object" && data != null) {
    const obj = data as Record<string, unknown>;
    for (const key of ["items", "rows", "definitions", "results", "data", "entries"]) {
      if (Array.isArray(obj[key])) return obj[key] as Record<string, unknown>[];
    }
  }
  return [];
}

function formatCell(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "boolean") return v ? "✓" : "✗";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function LazyTabContent({ tab }: { tab: TabDef }) {
  const [data, setData] = React.useState<unknown>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fetched = useRef(false);
  const bridge = useBridge();

  React.useEffect(() => {
    if (!tab.lazy_tool || fetched.current) return;
    fetched.current = true;
    setLoading(true);
    bridge.callTool(tab.lazy_tool, {})
      .then((res) => {
        setData(unwrapToolResult(res));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed"))
      .finally(() => setLoading(false));
  }, [tab.lazy_tool, bridge]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (data == null) return <p className="text-sm text-muted-foreground">No data</p>;

  const hints = tab.result_hints;
  const prefer = hints?.prefer;
  const columns = hints?.columns;

  if ((prefer === "grouped_table" || prefer === "table") && columns?.length) {
    const rows = extractRows(data);
    return (
      <div className="w-full overflow-auto">
        <table className="w-full caption-bottom text-sm">
          <thead className="[&_tr]:border-b">
            <tr>{columns.map((c) => (
              <th key={c.key} className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">{c.label}</th>
            ))}</tr>
          </thead>
          <tbody className="[&_tr:last-child]:border-0">
            {rows.map((row, i) => (
              <tr key={i} className="border-b transition-colors hover:bg-muted/50">
                {columns.map((c) => (
                  <td key={c.key} className="p-4 align-middle">{formatCell(row[c.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">No rows</p>}
      </div>
    );
  }

  if (prefer === "stat_grid") {
    const entries = Object.entries(data as Record<string, unknown>);
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {entries.map(([k, v]) => (
          <div key={k} className="rounded-lg border bg-card p-3">
            <p className="text-xs text-muted-foreground">{k}</p>
            <p className="text-lg font-semibold">{formatCell(v)}</p>
          </div>
        ))}
      </div>
    );
  }

  return (
    <pre className="max-h-96 overflow-auto rounded-md bg-muted p-4 text-sm">
      {typeof data === "string" ? data : JSON.stringify(data, null, 2)}
    </pre>
  );
}
