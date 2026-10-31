import { describe, expect, it } from "vitest";

import { mapLiveToolEvent } from "@/lib/live-tool-events";

describe("native MCP-v2 tool lifecycle", () => {
  it("maps correlated start and result phases onto one logical row identity", () => {
    const base = {
      brick: "wine",
      tool: "pair",
      success: true,
      latency_ms: 0,
      ts: 1715600000,
      invocation_id: "inv-744",
      correlation_id: "corr-744",
    } as const;
    const start = mapLiveToolEvent({ ...base, phase: "start" }, "live-tool-inv-744");
    const result = mapLiveToolEvent({
      ...base, phase: "result", latency_ms: 12.5,
      result_summary: { status: "ok" },
    }, "live-tool-inv-744");

    expect(start).toMatchObject({ id: "live-tool-inv-744", status: "running" });
    expect(result).toMatchObject({
      id: "live-tool-inv-744", status: "completed", duration: 12.5,
    });
  });

  it("maps terminal native errors as failed tool calls", () => {
    const entry = mapLiveToolEvent({
      brick: "security", tool: "scan", success: false,
      latency_ms: 3, ts: 1715600001, phase: "error",
      invocation_id: "inv-error",
    }, "live-tool-inv-error");
    expect(entry.status).toBe("failed");
  });
});
