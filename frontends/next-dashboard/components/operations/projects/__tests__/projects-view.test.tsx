import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import ProjectsView from "../projects-view";

const loopRow = {
  loop_id: "loop_abc", agent_id: "companion-x-default", kind: "goal",
  objective: "Port the Task Runner", cycle_instructions: "Do one row per cycle.",
  interval_seconds: 300, max_cycles: 24, state: "active", terminal_reason: null,
  next_cycle: 3, last_settled_cycle: 2, revision: 5, created_at: "2026-09-15T00:00:00Z",
};

const listOk = (rows: unknown[]) => ({ ok: true, data: { loops: rows } });
const cycleOk = { ok: true, data: { cycle: { cycle: 2, state: "settled", disposition: "continue", summary: "Flipped row 92." } } };

function defaultImpl(name: string) {
  if (name === "workflow.list_loops") return Promise.resolve(listOk([loopRow]));
  if (name === "workflow.get_loop_cycle") return Promise.resolve(cycleOk);
  return Promise.resolve({ ok: true, data: { loop: loopRow } });
}

beforeEach(() => {
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
});

describe("ProjectsView", () => {
  it("shows loading then the project list", async () => {
    render(<ProjectsView />);
    expect(screen.getByText(/Loading projects/)).toBeTruthy();
    expect(await screen.findByText("Port the Task Runner")).toBeTruthy();
    expect(screen.getByText(/companion-x-default/)).toBeTruthy();
  });

  it("renders the truthful empty state", async () => {
    mocks.callTool.mockImplementation((name: string) => name === "workflow.list_loops" ? Promise.resolve(listOk([])) : defaultImpl(name));
    render(<ProjectsView />);
    expect(await screen.findByText(/No projects yet/)).toBeTruthy();
  });

  it("renders error + retry and re-lists on retry", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "workflow.list_loops" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<ProjectsView />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Projects unavailable");
    mocks.callTool.mockImplementation((name: string) => defaultImpl(name));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Port the Task Runner")).toBeTruthy();
  });

  it("starts a project by mapping the spec form onto start_loop's existing fields", async () => {
    render(<ProjectsView />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "New effort" } });
    fireEvent.change(screen.getByLabelText("Spec"), { target: { value: "Do the thing each cycle." } });
    fireEvent.click(screen.getByRole("button", { name: "Start project" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("workflow.start_loop", {
      kind: "goal", agent_id: "companion-x-default", objective: "New effort",
      cycle_instructions: "Do the thing each cycle.", interval_seconds: 300, max_cycles: 24,
    }));
  });

  it("opens a project, shows its latest cycle, and pauses it with revision fencing", async () => {
    render(<ProjectsView />);
    fireEvent.click(await screen.findByText("Port the Task Runner"));
    expect(await screen.findByText(/Latest cycle \(2\) — settled/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "workflow.pause_loop", { loop_id: "loop_abc", expected_revision: 5 },
    ));
  });

  it("stops a project", async () => {
    render(<ProjectsView />);
    fireEvent.click(await screen.findByText("Port the Task Runner"));
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "workflow.stop_loop", { loop_id: "loop_abc", expected_revision: 5 },
    ));
  });

  it("refreshes the truth and warns on a revision conflict rather than lying", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "workflow.pause_loop"
        ? Promise.resolve({ ok: false, error: { message: "loop_revision_conflict" } })
        : defaultImpl(name));
    render(<ProjectsView />);
    fireEvent.click(await screen.findByText("Port the Task Runner"));
    const listCalls = () => mocks.callTool.mock.calls.filter((c) => c[0] === "workflow.list_loops").length;
    const before = listCalls();
    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
    expect(await screen.findByText(/changed elsewhere/)).toBeTruthy();
    expect(listCalls()).toBeGreaterThan(before);
  });
});
