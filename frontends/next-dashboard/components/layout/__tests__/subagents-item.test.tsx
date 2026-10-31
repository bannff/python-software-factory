import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import { SubagentsItem } from "../subagents-item";

const listOk = (runs: unknown[]) => ({ ok: true, data: { runs } });
const run = (id: string, status: string, persona = "worker") => ({
  run_id: id, persona_id: persona, status, kind: "background_subagent", origin_thread_id: "t1", started_at: "now",
});

function defaultImpl(name: string) {
  if (name === "agent.list_background_runs") return Promise.resolve(listOk([run("run-1", "running"), run("run-2", "succeeded", "reporter")]));
  return Promise.resolve({ ok: true, data: {} });
}

beforeEach(() => {
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
});

describe("SubagentsItem", () => {
  it("shows the active-count badge and lists runs with status in the popover", async () => {
    render(<SubagentsItem />);
    const trigger = await screen.findByLabelText("Subagents");
    expect(trigger.textContent).toContain("1"); // only run-1 is active
    fireEvent.click(trigger);
    expect(await screen.findByText("worker")).toBeTruthy();
    expect(screen.getByText("reporter")).toBeTruthy();
    expect(screen.getByText("succeeded")).toBeTruthy();
  });

  it("cancels one active run with a reason and refreshes", async () => {
    render(<SubagentsItem />);
    fireEvent.click(await screen.findByLabelText("Subagents"));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel run-1" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "workflow.cancel_run", { run_id: "run-1", reason: "user_cancelled" },
    ));
  });

  it("stop all cancels every active run only", async () => {
    render(<SubagentsItem />);
    fireEvent.click(await screen.findByLabelText("Subagents"));
    fireEvent.click(await screen.findByRole("button", { name: "Stop all" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "workflow.cancel_run", { run_id: "run-1", reason: "user_cancelled" },
    ));
    expect(mocks.callTool).not.toHaveBeenCalledWith("workflow.cancel_run", { run_id: "run-2", reason: "user_cancelled" });
  });

  it("shows a truthful empty state and no Stop all when nothing is active", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "agent.list_background_runs" ? Promise.resolve(listOk([])) : defaultImpl(name));
    render(<SubagentsItem />);
    fireEvent.click(await screen.findByLabelText("Subagents"));
    expect(await screen.findByText("No background runs.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Stop all" })).toBeNull();
  });

  it("degrades to an explicit error when the list call fails", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "agent.list_background_runs" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<SubagentsItem />);
    fireEvent.click(await screen.findByLabelText("Subagents"));
    expect(await screen.findByText("Subagents unavailable")).toBeTruthy();
  });

  it("backs off after 3 consecutive failures instead of polling forever (item 12d)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mocks.callTool.mockImplementation((name: string) =>
      name === "agent.list_background_runs" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<SubagentsItem />);
    fireEvent.click(await screen.findByLabelText("Subagents"));
    await vi.waitFor(() => expect(screen.queryByText("Subagents unavailable")).toBeTruthy());
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    await vi.waitFor(() => expect(screen.queryByText("Subagents unavailable right now.")).toBeTruthy());
    const callsAtBackoff = mocks.callTool.mock.calls.filter((c) => c[0] === "agent.list_background_runs").length;
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    const callsAfterBackoff = mocks.callTool.mock.calls.filter((c) => c[0] === "agent.list_background_runs").length;
    expect(callsAfterBackoff).toBe(callsAtBackoff);
    vi.useRealTimers();
  });
});
