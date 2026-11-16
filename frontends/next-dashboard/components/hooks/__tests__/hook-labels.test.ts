import { describe, expect, it } from "vitest";
import { eventLabel, hookDescription, toolLabel } from "../hook-labels";

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

describe("hookDescription", () => {
  it("drops a leading tracker id and its dash", () => {
    expect(hookDescription("bd:python-factory-v7imt.4 — Cadence-based eval-freshness trigger.\n"))
      .toBe("Cadence-based eval-freshness trigger.");
  });
  it("drops a parenthetical tracker reference", () => {
    expect(hookDescription("Compute improvement after reward computation (bd python-factory-kq6u). Closure."))
      .toBe("Compute improvement after reward computation. Closure.");
    expect(hookDescription("Score the turn and emit reward.computed (bd:python-factory-pfvo9 slice 2)."))
      .toBe("Score the turn and emit reward.computed.");
  });
  it("drops a trailing tracker id with its slice marker", () => {
    expect(hookDescription("Turn a verdict into a reward. bd:python-factory-pfvo9 S2.")).toBe("Turn a verdict into a reward.");
    expect(hookDescription("Isolated from the task reward. bd:python-factory-hv5rv.")).toBe("Isolated from the task reward.");
  });
  it("drops a mid-sentence tracker id in parentheses", () => {
    expect(hookDescription("Policy-driven scoring (bd:python-factory-v7imt.2). Routes events."))
      .toBe("Policy-driven scoring. Routes events.");
  });
  it("leaves authored text untouched", () => {
    expect(hookDescription("Notify me when a workflow fails")).toBe("Notify me when a workflow fails");
  });
});
