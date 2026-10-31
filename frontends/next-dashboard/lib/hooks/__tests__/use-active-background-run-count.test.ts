import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.callTool }));
import { useActiveBackgroundRunCount } from "../use-active-background-run-count";

describe("useActiveBackgroundRunCount", () => {
  it("counts only running/waiting runs from the real workflow registry", async () => {
    mocks.callTool.mockResolvedValueOnce({
      runs: [{ status: "running" }, { status: "waiting" }, { status: "completed" }],
    });
    const { result } = renderHook(() => useActiveBackgroundRunCount());
    await waitFor(() => expect(result.current).toBe(2));
    expect(mocks.callTool).toHaveBeenCalledWith("workflow.list_runs", {
      filter: {}, pagination: { limit: 100 },
    });
  });

  it("stays zero and never fabricates a count on a failed poll", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("unavailable"));
    const { result } = renderHook(() => useActiveBackgroundRunCount());
    await act(async () => { await Promise.resolve(); });
    expect(result.current).toBe(0);
  });

  it("backs off after 3 consecutive failures instead of polling forever (item 12d)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mocks.callTool.mockReset().mockRejectedValue(new Error("down"));
    renderHook(() => useActiveBackgroundRunCount());
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    const callsAtBackoff = mocks.callTool.mock.calls.length;
    expect(callsAtBackoff).toBeGreaterThanOrEqual(3);
    await act(async () => { await vi.advanceTimersByTimeAsync(45_000); });
    expect(mocks.callTool.mock.calls.length).toBe(callsAtBackoff);
    vi.useRealTimers();
  });
});
