/**
 * Pure helpers for timeline search + sort.
 * No React, no side-effects — easy to unit test.
 */
import type { TimelineEntry } from "@/lib/types";

export type SortMode = "newest" | "oldest" | "slowest";

function normalizeTs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

/** Case-insensitive substring match across title, detail, workflow_run_id, session_id. */
export function matchesSearch(entry: TimelineEntry, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    entry.title.toLowerCase().includes(q) ||
    (entry.detail?.toLowerCase().includes(q) ?? false) ||
    (entry.workflow_run_id?.toLowerCase().includes(q) ?? false) ||
    (entry.session_id?.toLowerCase().includes(q) ?? false)
  );
}

/** Sort entries by the given mode. Returns a new array. */
export function sortEntries(entries: TimelineEntry[], mode: SortMode): TimelineEntry[] {
  const sorted = [...entries];
  switch (mode) {
    case "newest":
      return sorted.sort((a, b) => normalizeTs(b.timestamp) - normalizeTs(a.timestamp));
    case "oldest":
      return sorted.sort((a, b) => normalizeTs(a.timestamp) - normalizeTs(b.timestamp));
    case "slowest":
      return sorted.sort((a, b) => (b.duration ?? 0) - (a.duration ?? 0));
  }
}
