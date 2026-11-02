import { describe, expect, it } from "vitest";
import { eventHistoryLabel, hasEventHistory } from "../event-history";
import type { Hook } from "../hooks-api";

const hook = (over: Partial<Hook>): Hook =>
  ({ id: "h", eventType: "agent.completed", tool: "t", description: "", enabled: true, ...over });
const seen = [{ eventId: "e1", timestamp: "2026-11-02T10:00:00Z" }];

describe("event history line", () => {
  it("is not shown for disabled hooks or wildcard patterns", () => {
    for (const h of [hook({ enabled: false }), hook({ eventType: "*.completed" })]) {
      expect(hasEventHistory(h)).toBe(false);
      expect(eventHistoryLabel(h, seen)).toBeNull();
    }
  });

  it("describes event history, never claiming the hook fired", () => {
    expect(eventHistoryLabel(hook({}), seen)).toMatch(/^Event last seen /);
    expect(eventHistoryLabel(hook({}), [])).toBe("No recent events of this type.");
    expect(eventHistoryLabel(hook({}), seen)).not.toMatch(/fired/i);
  });
});
