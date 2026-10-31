"use client";

import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/types";

interface TimelineDetailPanelProps {
  entry: TimelineEntry;
  isNew: boolean;
  /** @deprecated Kept for backward compat with runtime-metrics-drilldown */
  accentColor?: string;
}

function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  return `${Math.round(ms)}ms`;
}

function fmtTs(ts: number): string {
  const ms = ts < 1e12 ? ts * 1000 : ts;
  return new Date(ms).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Expanded detail panel rendered inside a bubble card's Collapsible.Content.
 * Surfaces EVERY populated field on TimelineEntry.
 */
export function TimelineDetailPanel({ entry, isNew }: TimelineDetailPanelProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border/30 bg-accent/[0.04] px-3 py-2 mb-1 mt-1",
        "text-[10px] text-foreground/60",
      )}
    >
      {/* Primary fields grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {/* tool/title — always present */}
        <Field label="tool" value={entry.title} mono />
        {/* status */}
        <Field label="status">
          <span
            className={cn(
              entry.status === "completed" && "text-emerald-400",
              entry.status === "failed" && "text-red-400",
              entry.status === "running" && "text-amber-400",
            )}
          >
            {entry.status}
          </span>
        </Field>
        {/* timestamp */}
        <Field label="ts" value={fmtTs(entry.timestamp)} span2 />
        {/* brick/detail */}
        <Field label="brick" value={entry.detail} />
        {/* type */}
        <Field label="type" value={entry.type} />
        {/* latency/duration */}
        <Field label="latency" value={entry.duration != null ? formatDuration(entry.duration) : undefined} mono />
        {/* source (live vs hist) */}
        <Field label="source">
          <span
            className={cn(
              "rounded px-1 py-0.5 text-[9px] font-medium",
              isNew ? "bg-violet-500/10 text-violet-400" : "bg-blue-500/10 text-blue-400",
            )}
          >
            {isNew ? "live" : "hist"}
          </span>
        </Field>
        {/* caller */}
        {entry.caller && <Field label="caller" value={entry.caller} pill="bg-cyan-500/10 text-cyan-400" />}
        {/* agent_id */}
        {entry.agent_id && <Field label="agent" value={entry.agent_id} pill="bg-indigo-500/10 text-indigo-300" />}
        {/* principal_id */}
        {entry.principal_id && <Field label="user" value={entry.principal_id} pill="bg-teal-500/10 text-teal-300" />}
        {/* session_id */}
        {entry.session_id && <Field label="session" value={entry.session_id} mono span2 />}
        {/* workflow_run_id */}
        {entry.workflow_run_id && (
          <Field label="run" value={entry.workflow_run_id} mono pill="bg-sky-500/10 text-sky-300" span2 />
        )}
        {/* severity */}
        {entry.severity && (
          <Field label="severity">
            <span
              className={cn(
                "rounded px-1 py-0.5 text-[9px] font-medium",
                entry.severity === "critical" && "bg-red-500/15 text-red-300",
                entry.severity === "high" && "bg-orange-500/15 text-orange-300",
                entry.severity === "medium" && "bg-amber-500/15 text-amber-300",
                entry.severity === "low" && "bg-yellow-500/15 text-yellow-300",
                entry.severity === "info" && "bg-blue-500/10 text-blue-300",
              )}
            >
              {entry.severity}
            </span>
          </Field>
        )}
        {/* swarmEventType */}
        {entry.swarmEventType && <Field label="swarm" value={entry.swarmEventType} />}
      </div>

      {/* args_summary */}
      {entry.args_summary && Object.keys(entry.args_summary).length > 0 && (
        <KvSection label="args" data={entry.args_summary} />
      )}

      {/* result_summary */}
      {entry.result_summary && Object.keys(entry.result_summary).length > 0 && (
        <KvSection label="result" data={entry.result_summary} />
      )}

      {/* swarmMeta */}
      {entry.swarmMeta && Object.keys(entry.swarmMeta).length > 0 && (
        <KvSection label="swarmMeta" data={entry.swarmMeta} />
      )}

      {/* error */}
      {entry.error && (
        <div className="mt-1.5 pt-1.5 border-t border-border/20">
          <span className="text-red-400/80">error: </span>
          <span className="text-red-300/70 font-mono break-all">{entry.error}</span>
        </div>
      )}
    </div>
  );
}

/* ─── Helpers ─── */

function Field({
  label,
  value,
  mono,
  pill,
  span2,
  children,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
  pill?: string;
  span2?: boolean;
  children?: React.ReactNode;
}) {
  if (!value && !children) return null;
  return (
    <span className={cn(span2 && "col-span-2")}>
      {label}:{" "}
      {children ?? (
        <span
          className={cn(
            "text-foreground/85",
            mono && "font-mono",
            pill && `rounded px-1 py-0.5 text-[9px] font-medium ${pill}`,
          )}
        >
          {value}
        </span>
      )}
    </span>
  );
}

function KvSection({ label, data }: { label: string; data: Record<string, unknown> }) {
  return (
    <div className="mt-1.5 pt-1.5 border-t border-border/20">
      <span className="text-foreground/40">{label}:</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 mt-0.5 font-mono">
        {Object.entries(data).map(([k, v]) => (
          <span key={k} className="truncate">
            <span className="text-foreground/50">{k}</span>=
            <span className="text-foreground/75">{String(v)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
