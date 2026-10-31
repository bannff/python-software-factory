"use client";

import { Activity, AlertTriangle, Clock3, Cpu, Gauge, Radio } from "lucide-react";
import type { TimelineEntry } from "@/lib/types";
import type { RuntimeSummary, MetricTone } from "@/lib/runtime-metrics-summary";
import type { DrilldownState } from "./runtime-metrics-drilldown";
import { MetricCard } from "./metric-card";

function latency(ms: number | null): string {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 1) return `${Math.round(ms * 1000)}μs`;
  return `${Math.round(ms)}ms`;
}
function rate(value: number | null): string { return value == null ? "—" : `${Math.round(value)}%`; }
function minutes(value: number): string { return value < 1 ? "<1m" : value < 60 ? `${Math.round(value)}m` : `${(value / 60).toFixed(1)}h`; }
function tone(value: number | null): MetricTone { return value == null ? "neutral" : value >= 95 ? "good" : value >= 80 ? "warn" : "bad"; }

export function RuntimeMetricsCards({
  summary, entries, toolCalls, failedCalls, activeEntries, slowestCalls, rlEntries,
  activeKey, onToggle,
}: {
  summary: RuntimeSummary;
  entries: TimelineEntry[];
  toolCalls: TimelineEntry[];
  failedCalls: TimelineEntry[];
  activeEntries: TimelineEntry[];
  slowestCalls: TimelineEntry[];
  rlEntries: TimelineEntry[];
  activeKey?: string;
  onToggle: (state: DrilldownState) => void;
}) {
  const cards = [
    {
      key: "buffered-events", icon: Activity, label: "Attributed Events", value: String(summary.bufferedEvents),
      detail: `${summary.toolCalls} tool calls in ${minutes(summary.coverageMinutes)}`,
      subtitle: "Every event in the current metrics source.", rows: entries,
    },
    {
      key: "success-rate", icon: Gauge, label: "Success Rate", value: rate(summary.successRate),
      detail: summary.failedCalls ? `${summary.failedCalls} failed calls` : "No failures in source",
      tone: tone(summary.successRate), subtitle: "Completed and failed attributed tool calls.",
      rows: [...failedCalls, ...toolCalls.filter((entry) => entry.status === "completed")].slice(0, 24),
    },
    {
      key: "avg-latency", icon: Clock3, label: "Average Latency", value: latency(summary.avgLatencyMs),
      detail: `${summary.callsPerMinute.toFixed(1)} calls/min`, subtitle: "Slowest attributed calls, sorted by duration.", rows: slowestCalls,
    },
    {
      key: "active-entries", icon: Radio, label: "Active Entries", value: String(summary.activeEntries),
      detail: "Currently marked running", tone: summary.activeEntries ? "warn" as MetricTone : "neutral" as MetricTone,
      subtitle: "Events still marked as running.", rows: activeEntries,
    },
    {
      key: "bricks-touched", icon: Cpu, label: "Bricks Touched", value: String(summary.uniqueBricks),
      detail: "Unique bricks in attributed calls", subtitle: "Calls grouped by brick.", rows: toolCalls,
    },
    {
      key: "recent-failures", icon: AlertTriangle, label: "Recent Failures", value: String(summary.failedCalls),
      detail: summary.failedCalls ? "Failures in current source" : "No attributed failures",
      tone: summary.failedCalls ? "bad" as MetricTone : "good" as MetricTone,
      subtitle: "Failed calls in the current source.", rows: failedCalls,
    },
    {
      key: "rl-runs", icon: Activity, label: "RL Runs", value: String(summary.rlRuns),
      detail: summary.rlRuns ? `${summary.rlCompletedRuns} completed · ${summary.rlFailedRuns} failed` : "No RL lifecycle events",
      tone: summary.rlFailedRuns ? "warn" as MetricTone : summary.rlCompletedRuns ? "good" as MetricTone : "neutral" as MetricTone,
      subtitle: "RL milestones grouped by workflow run.", rows: rlEntries,
    },
    {
      key: "latest-rl-score", icon: Gauge, label: "Latest RL Score", value: summary.latestRlScore == null ? "—" : summary.latestRlScore.toFixed(2),
      detail: summary.latestRlContext ?? "No RL score in current source",
      tone: summary.latestRlScore == null ? "neutral" as MetricTone : summary.latestRlScore >= 0.8 ? "good" as MetricTone : summary.latestRlScore >= 0.5 ? "warn" as MetricTone : "bad" as MetricTone,
      subtitle: summary.latestRlRunId ? `RL milestones for ${summary.latestRlRunId}.` : "No RL scoring event.",
      rows: summary.latestRlRunId ? rlEntries.filter((entry) => entry.workflow_run_id === summary.latestRlRunId) : [],
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => (
        <MetricCard key={card.key} icon={card.icon} label={card.label} value={card.value} detail={card.detail}
          tone={card.tone} active={activeKey === card.key}
          onClick={() => onToggle({ key: card.key, title: card.label, subtitle: card.subtitle, entries: card.rows })} />
      ))}
    </div>
  );
}
