import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), agent: { threadId: "t1" } }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgent: () => ({ agent: mocks.agent }) }));

import { MonitorItem } from "../monitor-item";

const listOk = (loops: unknown[]) => ({ ok: true, data: { loops } });
const loop = (id: string, threadId: string, state: string, objective = "Watch PR #1") => ({
  loop_id: id, objective, kind: "monitor", origin_thread_id: threadId, state, revision: 3,
});

function defaultImpl(name: string) {
  if (name === "workflow.list_loops") return Promise.resolve(listOk([loop("m1", "t1", "active")]));
  return Promise.resolve({ ok: true, data: {} });
}

beforeEach(() => {
  mocks.agent.threadId = "t1";
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
});

describe("MonitorItem", () => {
  it("shows only monitors for the current thread, not other threads", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "workflow.list_loops" ? Promise.resolve(listOk([loop("m1", "t1", "active"), loop("m2", "t2", "active")])) : defaultImpl(name));
    render(<MonitorItem />);
    const trigger = await screen.findByLabelText("Monitors");
    expect(trigger.textContent).toContain("1");
    fireEvent.click(trigger);
    expect(await screen.findByText("Watch PR #1")).toBeTruthy();
  });

  it("excludes goal-kind and terminal-state loops even on the same thread", async () => {
    mocks.callTool.mockImplementation((name: string) => name === "workflow.list_loops"
      ? Promise.resolve(listOk([
          loop("m1", "t1", "active"),
          { ...loop("g1", "t1", "active"), kind: "goal" },
          loop("m2", "t1", "stopped"),
        ]))
      : defaultImpl(name));
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    const rows = await screen.findAllByText("Watch PR #1");
    expect(rows).toHaveLength(1);
  });

  it("arms a monitor via workflow.start_loop with kind=monitor", async () => {
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    fireEvent.click(await screen.findByRole("button", { name: "Arm" }));
    fireEvent.change(screen.getByPlaceholderText("What to watch"), { target: { value: "PR #42" } });
    fireEvent.change(screen.getByPlaceholderText("What to check each cycle"), { target: { value: "Check CI status" } });
    fireEvent.click(screen.getByRole("button", { name: /Start/ }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("workflow.start_loop", {
      kind: "monitor", agent_id: "companion_x", objective: "PR #42", cycle_instructions: "Check CI status",
      interval_seconds: 300, max_cycles: 24,
    }));
  });

  it("stops an active monitor with its revision", async () => {
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    fireEvent.click(await screen.findByRole("button", { name: "Stop m1" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("workflow.stop_loop", {
      loop_id: "m1", expected_revision: 3,
    }));
  });

  it("shows a truthful empty state when nothing is armed", async () => {
    mocks.callTool.mockImplementation((name: string) => name === "workflow.list_loops" ? Promise.resolve(listOk([])) : defaultImpl(name));
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    expect(await screen.findByText("No monitors running.")).toBeTruthy();
  });

  it("degrades to an explicit error when the list call fails", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "workflow.list_loops" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    expect(await screen.findByText("Monitor status unavailable")).toBeTruthy();
  });

  it("backs off after 3 consecutive failures instead of polling forever (item 12d)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mocks.callTool.mockImplementation((name: string) =>
      name === "workflow.list_loops" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<MonitorItem />);
    fireEvent.click(await screen.findByLabelText("Monitors"));
    await vi.waitFor(() => expect(screen.queryByText("Monitor status unavailable")).toBeTruthy());
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    await vi.waitFor(() => expect(screen.queryByText("Monitors unavailable right now.")).toBeTruthy());
    const callsAtBackoff = mocks.callTool.mock.calls.filter((c) => c[0] === "workflow.list_loops").length;
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    const callsAfterBackoff = mocks.callTool.mock.calls.filter((c) => c[0] === "workflow.list_loops").length;
    expect(callsAfterBackoff).toBe(callsAtBackoff);
    vi.useRealTimers();
  });
});
