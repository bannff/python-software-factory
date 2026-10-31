import { describe, it, expect } from "vitest";
import { matchesSearch, sortEntries } from "@/lib/timeline-filters";
import type { TimelineEntry } from "@/lib/types";

function entry(overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return {
    id: "e1",
    type: "tool_call",
    title: "memory_store",
    status: "completed",
    timestamp: 1000,
    ...overrides,
  };
}

describe("matchesSearch", () => {
  it("returns true when query is empty", () => {
    expect(matchesSearch(entry(), "")).toBe(true);
  });

  it("matches title (case-insensitive)", () => {
    expect(matchesSearch(entry({ title: "graph_query" }), "GRAPH")).toBe(true);
  });

  it("matches detail (brick)", () => {
    expect(matchesSearch(entry({ detail: "memory" }), "mem")).toBe(true);
  });

  it("matches workflow_run_id", () => {
    expect(matchesSearch(entry({ workflow_run_id: "run-abc-123" }), "abc")).toBe(true);
  });

  it("matches session_id", () => {
    expect(matchesSearch(entry({ session_id: "ses-xyz-789" }), "xyz")).toBe(true);
  });

  it("returns false on no match", () => {
    expect(matchesSearch(entry({ title: "foo", detail: "bar" }), "qux")).toBe(false);
  });
});

describe("sortEntries", () => {
  const entries: TimelineEntry[] = [
    entry({ id: "a", timestamp: 2000, duration: 50 }),
    entry({ id: "b", timestamp: 1000, duration: 200 }),
    entry({ id: "c", timestamp: 3000, duration: 10 }),
  ];

  it("newest: descending timestamp", () => {
    const result = sortEntries(entries, "newest");
    expect(result.map((e) => e.id)).toEqual(["c", "a", "b"]);
  });

  it("oldest: ascending timestamp", () => {
    const result = sortEntries(entries, "oldest");
    expect(result.map((e) => e.id)).toEqual(["b", "a", "c"]);
  });

  it("slowest: descending duration", () => {
    const result = sortEntries(entries, "slowest");
    expect(result.map((e) => e.id)).toEqual(["b", "a", "c"]);
  });

  it("slowest: entries without duration sort to end", () => {
    const withMissing = [...entries, entry({ id: "d", timestamp: 4000 })];
    const result = sortEntries(withMissing, "slowest");
    expect(result[result.length - 1].id).toBe("d");
  });

  it("does not mutate the original array", () => {
    const original = [...entries];
    sortEntries(entries, "newest");
    expect(entries.map((e) => e.id)).toEqual(original.map((e) => e.id));
  });

  it("handles sub-second timestamps (normalize < 1e12)", () => {
    const mixed: TimelineEntry[] = [
      entry({ id: "s1", timestamp: 1719340000 }),     // seconds
      entry({ id: "s2", timestamp: 1719340000000 }),  // millis (same)
      entry({ id: "s3", timestamp: 1719339000 }),     // earlier
    ];
    const result = sortEntries(mixed, "oldest");
    expect(result.map((e) => e.id)).toEqual(["s3", "s1", "s2"]);
  });
});
