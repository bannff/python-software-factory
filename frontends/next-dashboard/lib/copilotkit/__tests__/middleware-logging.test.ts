/**
 * Tests for the CopilotKit v2 logging middleware (bd-w5zk).
 *
 * These pin the contract of `requestLogger` / `responseLogger`:
 *   - exactly one structured `console.log` line per invocation
 *   - JSON shape is grep-friendly (`stage`, `path`, `msgCount`, etc.)
 *   - PII discipline: msgCount only, never message content
 *   - graceful behaviour when the SSE parser yields no messages[]
 *
 * Style mirrors `dispatcher-canary.test.tsx` — vitest, vi.spyOn on
 * console.log, restored in afterEach.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  requestLogger,
  responseLogger,
} from "@/lib/copilotkit/middleware/logging";

// The middleware fn parameter shapes are derived from the public
// CopilotRuntimeOptions but we don't have the discrete `Parameters<...>`
// helpers exported; reconstruct minimal types here for the test harness.
// This stays in sync with `runtime.d.cts:39-46` and `middleware.d.cts`.
type BeforeParams = Parameters<typeof requestLogger>[0];
type AfterParams = Parameters<typeof responseLogger>[0];

const fakeRuntime = {} as BeforeParams["runtime"];

describe("copilotkit middleware logging (bd-w5zk)", () => {
  let logSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
  });

  it("requestLogger emits a single before-stage log line for a POST request", () => {
    const request = new Request("http://localhost:3000/api/copilotkit/agent/companion_x/run", {
      method: "POST",
    });
    const params: BeforeParams = {
      runtime: fakeRuntime,
      request,
      path: "/agent/companion_x/run",
    };

    const result = requestLogger(params);

    expect(result).toBeUndefined();
    expect(logSpy).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(logSpy.mock.calls[0]?.[0] as string);
    expect(payload).toEqual({
      stage: "before",
      method: "POST",
      path: "/agent/companion_x/run",
    });
  });

  it("responseLogger emits a single after-stage log line with msgCount from messages[]", () => {
    const params: AfterParams = {
      runtime: fakeRuntime as AfterParams["runtime"],
      response: new Response(),
      path: "/agent/companion_x/run",
      threadId: "t1",
      runId: "r1",
      messages: [
        { id: "m1", role: "assistant", content: "hi" },
        { id: "m2", role: "tool", toolCallId: "tc1", content: "ok" },
      ],
    };

    const result = responseLogger(params);

    expect(result).toBeUndefined();
    expect(logSpy).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(logSpy.mock.calls[0]?.[0] as string);
    expect(payload).toEqual({
      stage: "after",
      path: "/agent/companion_x/run",
      threadId: "t1",
      runId: "r1",
      msgCount: 2,
    });
  });

  it("responseLogger does not blow up on missing messages", () => {
    const params: AfterParams = {
      runtime: fakeRuntime as AfterParams["runtime"],
      response: new Response(),
      path: "/agent/companion_x/run",
      threadId: undefined,
      runId: undefined,
      messages: undefined,
    };

    const result = responseLogger(params);

    expect(result).toBeUndefined();
    expect(logSpy).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(logSpy.mock.calls[0]?.[0] as string);
    expect(payload.stage).toBe("after");
    expect(payload.msgCount).toBe(0);
  });
});
