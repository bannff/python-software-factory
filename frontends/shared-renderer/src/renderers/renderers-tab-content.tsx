"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import { useToolData } from "./use-tool-data";
import { resolve } from "./renderers-item-list-utils";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

/* ── Types ── */

export type ChartProps = {
  chart_type?: "line";
  x_key?: string;
  y_key?: string;
  color?: string;
  height?: number;
  empty_message?: string;
};

export type AlertProps = {
  intent_field?: string;
  intent_map?: Record<string, string>;
};

export type TabSpec = {
  id: string;
  label: string;
  tool?: string;
  args?: Record<string, unknown>;
  data_path?: string;
  empty_message?: string;
  render_as?: string;
  chart_props?: ChartProps;
  alert_props?: AlertProps;
};

function InlineLoading() {
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] text-muted-foreground/75">
      <Loader2 className="h-3 w-3 animate-spin" />
      Loading
    </span>
  );
}

/* ── Chart tab ── */

export function ChartTabContent({ tab }: { tab: TabSpec }) {
  const { data, loading, error } = useToolData(tab.tool, tab.args);
  if (loading) return <InlineLoading />;
  if (error) return <span className="text-[10px] text-destructive">{error}</span>;

  const cp = tab.chart_props ?? {};
  const raw = data as Record<string, unknown> | null;
  const buckets = Array.isArray(raw?.buckets)
    ? (raw!.buckets as Record<string, unknown>[])
    : [];

  if (buckets.length === 0 && cp.empty_message) {
    return <p className="text-[10px] text-muted-foreground/60 italic py-1">{cp.empty_message}</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={cp.height ?? 120}>
      <LineChart data={buckets}>
        <XAxis
          dataKey={cp.x_key ?? "start"}
          tick={{ fontSize: 9 }}
          tickFormatter={(v) => {
            const ms = typeof v === "number" && v < 1e12 ? v * 1000 : v;
            return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
          }}
        />
        <YAxis tick={{ fontSize: 9 }} width={28} />
        <Tooltip contentStyle={{ fontSize: 10 }} />
        <Line
          type="monotone"
          dataKey={cp.y_key ?? "value"}
          stroke={cp.color ?? "#6366f1"}
          dot={false}
          strokeWidth={1.5}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ── Alert tab ── */

const INTENT_STYLES: Record<string, string> = {
  warning: "bg-yellow-500/10 border border-yellow-500/30 text-yellow-400",
  success: "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400",
};

const INTENT_MESSAGES: Record<string, string> = {
  warning: "Drift detected — metric has shifted significantly",
  success: "No drift detected — metric is stable",
};

export function AlertTabContent({ tab }: { tab: TabSpec }) {
  const { data, loading, error } = useToolData(tab.tool, tab.args);
  if (loading) return <InlineLoading />;
  if (error) return <span className="text-[10px] text-destructive">{error}</span>;

  const ap = tab.alert_props ?? {};
  const raw = data as Record<string, unknown> | null;
  const boolVal = raw && ap.intent_field ? Boolean(raw[ap.intent_field]) : false;
  const intentKey = boolVal ? "true" : "false";
  const intent = ap.intent_map?.[intentKey] ?? (boolVal ? "warning" : "success");
  const message = INTENT_MESSAGES[intent] ?? intent;

  return (
    <div className={cn("rounded px-2 py-1 text-[10px]", INTENT_STYLES[intent] ?? INTENT_STYLES.success)}>
      {message}
    </div>
  );
}

/* ── List tab ── */

export function ListTabContent({ tab }: { tab: TabSpec }) {
  const { data, loading, error } = useToolData(tab.tool, tab.args);
  if (loading) return <InlineLoading />;
  if (error) return <span className="text-[10px] text-destructive">{error}</span>;

  const raw = data as Record<string, unknown> | null;
  const pathData = tab.data_path && raw ? resolve(raw, tab.data_path) : undefined;
  const arr = Array.isArray(pathData) ? pathData
    : Array.isArray(raw) ? raw
    : Array.isArray(raw?.runs) ? raw!.runs as unknown[]
    : Array.isArray(raw?.case_results) ? raw!.case_results as unknown[]
    : Array.isArray(raw?.moves) ? raw!.moves as unknown[]
    : Array.isArray(raw?.transactions) ? raw!.transactions as unknown[]
    : Array.isArray(raw?.bounties) ? raw!.bounties as unknown[]
    : Array.isArray(raw?.items) ? raw!.items as unknown[]
    : null;

  if (!arr || arr.length === 0) {
    return <p className="text-[10px] text-muted-foreground italic">{tab.empty_message ?? "No items"}</p>;
  }
  return (
    <div className="space-y-0.5">
      {arr.map((item, i) => {
        const r = item as Record<string, unknown>;
        const label = String(
          r.case_name
          ?? r.name
          ?? r.id
          ?? r.filename
          ?? r.tx_id
          ?? r.bounty_id
          ?? (r.action ? `${r.player != null ? `P${r.player} · ` : ""}${String(r.action).replaceAll("_", " ")}` : undefined)
          ?? (r.step != null ? `Step ${r.step}` : undefined)
          ?? `item-${i}`,
        );
        const score = r.score != null ? `${Math.round(Number(r.score) * 100)}%` : "";
        const reason = typeof r.reason === "string"
          ? r.reason
          : typeof r.evidence === "string"
            ? r.evidence
            : typeof r.memo === "string"
              ? r.memo
              : "";
        const isError = reason.includes("Exception") || reason.includes("error:") || reason.includes("Error");
        const verdict = isError ? "⚠" : r.passed === true ? "✓" : r.passed === false ? "✗" : "";
        const verdictColor = isError
          ? "text-orange-400"
          : r.passed === true ? "text-emerald-400" : r.passed === false ? "text-red-400" : "";
        const sub = score
          || (r.status ?? r.phase ?? (r.column != null ? `column ${r.column}` : ""));
        return (
          <div key={i} className="py-1 border-b border-border/10 last:border-0">
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span className={cn("shrink-0 font-medium", verdictColor)}>{verdict}</span>
              <span className="text-foreground/70 font-mono flex-1 truncate">{label}</span>
              {sub && <span className="text-muted-foreground/60 shrink-0">{String(sub)}</span>}
            </div>
            {reason && (
              <p className="mt-0.5 ml-4 text-[10px] text-muted-foreground/70 line-clamp-2 border-l-2 border-indigo-500/20 pl-2">
                {reason}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
