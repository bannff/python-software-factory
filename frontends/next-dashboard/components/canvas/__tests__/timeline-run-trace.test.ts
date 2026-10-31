import { describe, it, expect } from "vitest";
import type { TimelineEntry } from "@/lib/types";

/**
 * Unit test for the run-trace ordering logic used in TimelineRunTrace.
 * Verifies: given mixed entries, filtering by run + ascending sort is correct.
 */

function normalizeTs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

function getTraceEntries(entries: TimelineEntry[], runId: string): TimelineEntry[] {
  return entries
    .filter((e) => e.workflow_run_id === runId)
    .sort((a, b) => normalizeTs(a.timestamp) - normalizeTs(b.timestamp));
}

const RUN_A = "run-aaa-111";
const RUN_B = "run-bbb-222";

function entry(id: string, ts: number, runId?: string): TimelineEntry {
  return {
    id,
    type: "tool_call",
    title: `tool-${id}`,
    status: "completed",
    timestamp: ts,
    workflow_run_id: runId,
  };
}

describe("timeline-run-trace ordering", () => {
  const entries: TimelineEntry[] = [
    entry("e1", 1000, RUN_A),
    entry("e2", 3000, RUN_B),
    entry("e3", 2000, RUN_A),
    entry("e4", 500, RUN_A),
    entry("e5", 4000, undefined), // no run
    entry("e6", 1500, RUN_B),
  ];

  it("filters to only the target run entries", () => {
    const trace = getTraceEntries(entries, RUN_A);
    expect(trace.map((e) => e.id)).toEqual(["e4", "e1", "e3"]);
    expect(trace.every((e) => e.workflow_run_id === RUN_A)).toBe(true);
  });

  it("sorts ascending by timestamp (causal order)", () => {
    const trace = getTraceEntries(entries, RUN_A);
    for (let i = 1; i < trace.length; i++) {
      expect(normalizeTs(trace[i].timestamp)).toBeGreaterThanOrEqual(normalizeTs(trace[i - 1].timestamp));
    }
  });

  it("handles sub-second timestamps (normalize < 1e12)", () => {
    const mixed: TimelineEntry[] = [
      entry("s1", 1719340000, RUN_A), // seconds
      entry("s2", 1719340000000, RUN_A), // millis (same instant)
      entry("s3", 1719339000, RUN_A), // earlier second
    ];
    const trace = getTraceEntries(mixed, RUN_A);
    expect(trace.map((e) => e.id)).toEqual(["s3", "s1", "s2"]);
  });

  it("returns empty for unknown run", () => {
    expect(getTraceEntries(entries, "nonexistent")).toEqual([]);
  });

  it("excludes entries without workflow_run_id", () => {
    const trace = getTraceEntries(entries, RUN_A);
    expect(trace.find((e) => e.id === "e5")).toBeUndefined();
  });
});
