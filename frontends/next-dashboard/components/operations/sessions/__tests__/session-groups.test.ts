import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { groupSessions } from "../session-groups";

const row = (id: string, updated: Date): SessionSummary =>
  ({ session_id: id, updated_at: updated.toISOString(), pinned_rank: null }) as SessionSummary;

const labelOf = (groups: ReturnType<typeof groupSessions>, id: string) =>
  groups.find((g) => g.sessions.some((s) => s.session_id === id))?.label;

describe("groupSessions across a clock change", () => {
  const previousTz = process.env.TZ;
  // US DST ended 2026-11-01 02:00, so that calendar day is 25 hours long.
  beforeAll(() => { process.env.TZ = "America/Chicago"; });
  afterAll(() => { process.env.TZ = previousTz; });

  it("puts a session from the previous calendar day under Yesterday", () => {
    const now = new Date(2026, 10, 2, 0, 45).getTime();
    const groups = groupSessions([
      row("same-time-yesterday", new Date(2026, 10, 1, 0, 45)),
      row("late-yesterday", new Date(2026, 10, 1, 23, 59)),
      row("earlier-today", new Date(2026, 10, 2, 0, 5)),
      row("six-days-ago", new Date(2026, 9, 27, 12, 0)),
      row("ten-days-ago", new Date(2026, 9, 23, 12, 0)),
    ], now);
    expect(labelOf(groups, "same-time-yesterday")).toBe("Yesterday");
    expect(labelOf(groups, "late-yesterday")).toBe("Yesterday");
    expect(labelOf(groups, "earlier-today")).toBe("Today");
    expect(labelOf(groups, "six-days-ago")).toBe("Previous 7 days");
    expect(labelOf(groups, "ten-days-ago")).toBe("Older");
  });
});
