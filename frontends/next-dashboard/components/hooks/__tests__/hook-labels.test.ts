import { describe, expect, it } from "vitest";
import { eventLabel, toolLabel } from "../hook-labels";

describe("eventLabel", () => {
  it("uses the curated label for a known lifecycle event", () => {
    expect(eventLabel("workflow.failed")).toBe("Workflow run fails");
  });
  it("humanizes an event code with no curated label", () => {
    expect(eventLabel("reward.computed")).toBe("Reward computed");
    expect(eventLabel("eval.freshness.due")).toBe("Eval freshness due");
  });
  it("describes a wildcard pattern", () => {
    expect(eventLabel("*.completed")).toBe("Any completed event");
  });
});

describe("toolLabel", () => {
  it("drops the internal mcp: transport prefix", () => {
    expect(toolLabel("mcp:freshness_dispatch")).toBe("freshness_dispatch");
    expect(toolLabel("memory_search")).toBe("memory_search");
  });
});
