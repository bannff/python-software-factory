import type { TimelineEntry } from "@/lib/types";

export type MetricTone = "neutral" | "good" | "warn" | "bad";

export interface RuntimeSummary {
  bufferedEvents: number;
  toolCalls: number;
  failedCalls: number;
  successRate: number | null;
  avgLatencyMs: number | null;
  callsPerMinute: number;
  activeEntries: number;
  uniqueBricks: number;
  coverageMinutes: number;
  volumeSeries: number[];
  topTools: Array<{ name: string; count: number }>;
  topBricks: Array<{ name: string; count: number }>;
  recentFailures: TimelineEntry[];
  rlEvents: number;
  rlRuns: number;
  rlCompletedRuns: number;
  rlFailedRuns: number;
  latestRlScore: number | null;
  latestRlRunId?: string;
  latestRlContext?: string;
}

function toMs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

function getRlEntries(entries: TimelineEntry[]): TimelineEntry[] {
  return entries.filter((entry) => entry.swarmEventType?.startsWith("rl."));
}

function getLatestRlScoreEntry(entries: TimelineEntry[]): TimelineEntry | undefined {
  return [...entries]
    .filter((entry) => entry.swarmEventType === "rl.scored")
    .sort((a, b) => toMs(b.timestamp) - toMs(a.timestamp))[0];
}

function readNumericMeta(entry: TimelineEntry | undefined, key: string): number | null {
  const value = entry?.swarmMeta?.[key];
  return typeof value === "number" ? value : null;
}

function formatRlContext(entry: TimelineEntry | undefined): string | undefined {
  if (!entry) return undefined;
  const meta = entry.swarmMeta ?? {};
  const workflowType = typeof meta.workflow_type === "string" ? meta.workflow_type : "";
  const targetApp = typeof meta.target_app === "string" ? meta.target_app : "";
  // bd:python-factory-ttru9 — read domain_class first; vuln_class is the
  // legacy field name (mirrored on BE in hadbi.qer1z's
  // game_pipeline.py::_store_learnings).
  const domainClass =
    (typeof meta.domain_class === "string" ? meta.domain_class : "") ||
    (typeof meta.vuln_class === "string" ? meta.vuln_class : "");
  const bits = [workflowType, targetApp, domainClass].filter(Boolean);
  return bits.length > 0 ? bits.join(" · ") : entry.workflow_run_id;
}

export function newestFirst(entries: TimelineEntry[]): TimelineEntry[] {
  return [...entries].sort((a, b) => toMs(b.timestamp) - toMs(a.timestamp));
}

export function summarizeRuntimeMetrics(entries: TimelineEntry[]): RuntimeSummary {
  const sorted = [...entries].sort((a, b) => toMs(a.timestamp) - toMs(b.timestamp));
  const toolCalls = entries.filter((entry) => entry.type === "tool_call");
  const failedCalls = toolCalls.filter((entry) => entry.status === "failed");
  const completedCalls = toolCalls.filter((entry) => entry.status === "completed");
  const latencySamples = toolCalls
    .map((entry) => entry.duration)
    .filter((duration): duration is number => typeof duration === "number" && Number.isFinite(duration));
  const oldestMs = sorted[0] ? toMs(sorted[0].timestamp) : Date.now();
  const newestMs = sorted[sorted.length - 1] ? toMs(sorted[sorted.length - 1].timestamp) : oldestMs;
  const spanMs = Math.max(newestMs - oldestMs, 1);
  const toolCounts = new Map<string, number>();
  const brickCounts = new Map<string, number>();

  for (const entry of toolCalls) {
    toolCounts.set(entry.title, (toolCounts.get(entry.title) ?? 0) + 1);
    if (entry.detail) {
      brickCounts.set(entry.detail, (brickCounts.get(entry.detail) ?? 0) + 1);
    }
  }

  const bucketCount = Math.min(Math.max(sorted.length, 1), 12);
  const bucketWidth = Math.max(spanMs / bucketCount, 1);
  const volumeSeries = Array.from({ length: bucketCount }, () => 0);
  for (const entry of toolCalls) {
    const index = Math.min(
      bucketCount - 1,
      Math.floor((toMs(entry.timestamp) - oldestMs) / bucketWidth),
    );
    volumeSeries[index] += 1;
  }

  const rlEntries = getRlEntries(entries);
  const rlRunIds = new Set(rlEntries.map((entry) => entry.workflow_run_id).filter((value): value is string => Boolean(value)));
  const rlCompletedRunIds = new Set(
    rlEntries
      .filter((entry) => entry.swarmEventType === "rl.completed")
      .map((entry) => entry.workflow_run_id)
      .filter((value): value is string => Boolean(value)),
  );
  const rlFailedRunIds = new Set(
    rlEntries
      .filter((entry) => entry.swarmEventType === "rl.failed")
      .map((entry) => entry.workflow_run_id)
      .filter((value): value is string => Boolean(value)),
  );
  const latestRlScoreEntry = getLatestRlScoreEntry(rlEntries);

  return {
    bufferedEvents: entries.length,
    toolCalls: toolCalls.length,
    failedCalls: failedCalls.length,
    successRate: toolCalls.length > 0 ? (completedCalls.length / toolCalls.length) * 100 : null,
    avgLatencyMs: latencySamples.length > 0
      ? latencySamples.reduce((sum, sample) => sum + sample, 0) / latencySamples.length
      : null,
    callsPerMinute: toolCalls.length > 0 ? toolCalls.length / Math.max(spanMs / 60_000, 1 / 60) : 0,
    activeEntries: entries.filter((entry) => entry.status === "running").length,
    uniqueBricks: brickCounts.size,
    coverageMinutes: Math.max(spanMs / 60_000, 0),
    volumeSeries,
    topTools: [...toolCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name, count]) => ({ name, count })),
    topBricks: [...brickCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name, count]) => ({ name, count })),
    recentFailures: failedCalls.slice(0, 5),
    rlEvents: rlEntries.length,
    rlRuns: rlRunIds.size,
    rlCompletedRuns: rlCompletedRunIds.size,
    rlFailedRuns: rlFailedRunIds.size,
    latestRlScore: readNumericMeta(latestRlScoreEntry, "f1"),
    latestRlRunId: latestRlScoreEntry?.workflow_run_id,
    latestRlContext: formatRlContext(latestRlScoreEntry),
  };
}

export function selectRuntimeMetricEntries(
  focusedRunId: string | null,
  focusedEntries: TimelineEntry[],
  broadEntries: TimelineEntry[],
): TimelineEntry[] {
  if (!focusedRunId) return broadEntries;
  return focusedEntries.filter((entry) => entry.workflow_run_id === focusedRunId);
}
