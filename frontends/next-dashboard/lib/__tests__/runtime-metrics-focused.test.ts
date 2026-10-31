import { describe, expect, it } from "vitest";
import { selectRuntimeMetricEntries, summarizeRuntimeMetrics } from "@/lib/runtime-metrics-summary";
import type { TimelineEntry } from "@/lib/types";

function row(id: string, run?: string): TimelineEntry { return { id, type: "tool_call", title: id, detail: "graph", status: "completed", timestamp: 1, workflow_run_id: run }; }

describe("focused runtime metrics attribution", () => {
  it("excludes global, other-run, and unattributed rows before summarizing", () => {
    const exact = [row("exact", "run-a"), row("other", "run-b"), row("none")];
    const selected = selectRuntimeMetricEntries("run-a", exact, [row("global", "run-z")]);
    expect(selected.map((entry) => entry.id)).toEqual(["exact"]);
    expect(summarizeRuntimeMetrics(selected).toolCalls).toBe(1);
  });

  it("keeps authoritative focused empty distinct from broad data", () => {
    const selected = selectRuntimeMetricEntries("run-a", [], [row("global", "run-z")]);
    expect(selected).toEqual([]);
    expect(summarizeRuntimeMetrics(selected).bufferedEvents).toBe(0);
  });
});
