import { describe, expect, it } from "vitest";
import {
  formatTimestamp, parseInbox, targetRoute, unreadCount,
} from "@/lib/notifications";

const listResult = {
  tool: "notification_inbox_list",
  result: {
    notifications: [
      {
        notification_id: "ntf_1", kind: "schedule_fired", title: "Schedule fired",
        body: "Nightly scan started", priority: "critical",
        target: { kind: "artifact", slug: "scan-report" },
        created_at: "2026-09-13T18:00:00Z", read_at: null, revision: 2,
      },
      {
        notification_id: "ntf_2", kind: "crew_ready", title: "Crew ready",
        body: "", priority: "default",
        target: { kind: "crew", crew_id: "redteam-crew" },
        created_at: "2026-09-13T17:00:00Z", read_at: "2026-09-13T17:05:00Z", revision: 1,
      },
    ],
    count: 2,
  },
};

describe("notifications parsers", () => {
  it("parses records and maps read_at to a boolean read flag", () => {
    const items = parseInbox(listResult);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({
      notificationId: "ntf_1", title: "Schedule fired", priority: "critical",
      read: false, revision: 2, target: { kind: "artifact", id: "scan-report" },
    });
    expect(items[1].read).toBe(true);
    expect(items[1].target).toEqual({ kind: "crew", id: "redteam-crew" });
  });

  it("drops malformed records and unknown targets", () => {
    const items = parseInbox({
      notifications: [
        { title: "no id", target: { kind: "crew", crew_id: "c" } },
        { notification_id: "x", title: "bad target", target: { kind: "wormhole", id: "z" } },
      ],
    });
    expect(items).toHaveLength(0);
  });

  it("defaults an unknown priority to 'default'", () => {
    const items = parseInbox({
      notifications: [{
        notification_id: "n", title: "t", priority: "screaming",
        target: { kind: "canvas", view_id: "graph" }, created_at: "", read_at: null, revision: 1,
      }],
    });
    expect(items[0].priority).toBe("default");
  });

  it("counts only unread items", () => {
    expect(unreadCount(parseInbox(listResult))).toBe(1);
  });

  it("routes direct Operations, artifact, and crew targets", () => {
    expect(targetRoute({ kind: "artifact", id: "my doc" })).toBe("/artifacts/my%20doc");
    expect(targetRoute({ kind: "crew", id: "blue" })).toBe("/crews/blue");
    expect(targetRoute({ kind: "session", id: "s1" })).toBe("/sessions/s1");
    expect(targetRoute({ kind: "schedule", id: "sc1" })).toBe("/schedules/sc1");
    expect(targetRoute({ kind: "lesson", id: "l1" })).toBe("/lessons/l1");
    expect(targetRoute({ kind: "workflow_run", id: "r1" })).toBeNull();
    expect(targetRoute({ kind: "canvas", id: "graph" })).toBeNull();
  });

  it("formats timestamps and tolerates empty/invalid input", () => {
    expect(formatTimestamp("")).toBe("");
    expect(formatTimestamp("not-a-date")).toBe("");
    expect(formatTimestamp("2026-09-13T18:00:00Z").length).toBeGreaterThan(0);
  });
});
