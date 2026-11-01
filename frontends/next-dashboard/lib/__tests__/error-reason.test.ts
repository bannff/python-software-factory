import { describe, expect, it } from "vitest";
import { toolFailure } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";

describe("tool failures keep the server's reason", () => {
  it("call_brick_tool envelope with a typed error object", () => {
    const err = toolFailure("agent_create_crew", {
      ok: false, error: { type: "ToolExecutionError", message: "tool_execution_failed" },
    });
    expect(errorReason(err)).toBe("tool_execution_failed");
  });

  it("transport ok:false with a bare string error", () => {
    expect(errorReason(toolFailure("scheduler_add", { ok: false, error: "tool_execution_failed" })))
      .toBe("tool_execution_failed");
  });

  it("no reason when the server sent none (gate payload)", () => {
    const err = toolFailure("events_authoring_upsert_subscription",
      { ok: false, dry_run: null, would_write: null });
    expect(errorReason(err)).toBeUndefined();
    expect(withReason("Couldn't save.", errorReason(err))).toBe("Couldn't save.");
  });

  it("domain ok:false unwrapped by the framework path surfaces its message", () => {
    const thrown = (() => {
      try { unwrapToolData({ ok: false, error: "owner_secret_unavailable" }); } catch (e) { return e; }
    })();
    expect(withReason("Secret could not be saved.", errorReason(thrown)))
      .toBe("Secret could not be saved. (owner_secret_unavailable)");
  });
});
