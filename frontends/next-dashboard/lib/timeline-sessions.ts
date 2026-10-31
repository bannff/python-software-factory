import type { TimelineEntry } from "@/lib/types";

export interface SessionGroup {
  id: string;
  startTime: number;
  endTime: number;
  entries: TimelineEntry[];
  successRate: number;
  toolCount: number;
  errorCount: number;
  duration: number;
  /** Workflow run ID when the session was grouped by run (undefined = time-gap grouping). */
  workflowRunId?: string;
  /** Distinct agent ids represented in the grouped entries. */
  agentIds: string[];
  /** Distinct principal ids represented in the grouped entries. */
  principalIds: string[];
}

const SESSION_GAP_MS = 30 * 60 * 1000; // 30 minutes

/** Normalise any timestamp to ms epoch. Handles: ms epoch, s epoch, NaN (uses index offset). */
export function normaliseTimelineTimestamp(ts: number, fallbackIndex: number): number {
  if (!Number.isFinite(ts) || ts === 0) return Date.now() - fallbackIndex * 60_000;
  // Unix seconds (< year 2001 in ms = 978307200000)
  if (ts < 1_000_000_000_000) return ts * 1000;
  return ts;
}

export function groupTimelineSessions(entries: TimelineEntry[]): SessionGroup[] {
  if (entries.length === 0) return [];

  const normalised = entries.map((entry, index) => ({
    ...entry,
    timestamp: normaliseTimelineTimestamp(entry.timestamp, index),
  }));

  const withRun: TimelineEntry[] = [];
  const withoutRun: TimelineEntry[] = [];
  for (const entry of normalised) {
    (entry.workflow_run_id ? withRun : withoutRun).push(entry);
  }

  const groups: SessionGroup[] = [];
  const byRun = new Map<string, TimelineEntry[]>();
  for (const entry of withRun) {
    const bucket = byRun.get(entry.workflow_run_id!) ?? [];
    bucket.push(entry);
    byRun.set(entry.workflow_run_id!, bucket);
  }
  for (const [runId, bucket] of byRun) {
    groups.push(buildSessionGroup(bucket, runId));
  }

  if (withoutRun.length > 0) {
    const sorted = [...withoutRun].sort((a, b) => a.timestamp - b.timestamp);
    let current: TimelineEntry[] = [sorted[0]!];
    for (let index = 1; index < sorted.length; index++) {
      const gap = sorted[index]!.timestamp - sorted[index - 1]!.timestamp;
      if (gap > SESSION_GAP_MS) {
        groups.push(buildSessionGroup(current));
        current = [sorted[index]!];
      } else {
        current.push(sorted[index]!);
      }
    }
    if (current.length > 0) groups.push(buildSessionGroup(current));
  }

  return groups.sort((a, b) => b.startTime - a.startTime);
}

function buildSessionGroup(entries: TimelineEntry[], workflowRunId?: string): SessionGroup {
  const timestamps = entries.map((entry) => entry.timestamp);
  const startTime = Math.min(...timestamps);
  const endTime = Math.max(...timestamps);
  const failed = entries.filter((entry) => entry.status === "failed").length;
  const completed = entries.length - failed;
  const successRate = entries.length > 0 ? completed / entries.length : 0;
  const agentIds = [...new Set(entries.map((entry) => entry.agent_id).filter((value): value is string => Boolean(value)))];
  const principalIds = [...new Set(entries.map((entry) => entry.principal_id).filter((value): value is string => Boolean(value)))];

  return {
    id: workflowRunId ? `run-${workflowRunId}` : `session-${startTime}`,
    startTime,
    endTime,
    entries: [...entries].sort((a, b) => b.timestamp - a.timestamp),
    successRate,
    toolCount: entries.length,
    errorCount: failed,
    duration: endTime - startTime,
    workflowRunId,
    agentIds,
    principalIds,
  };
}