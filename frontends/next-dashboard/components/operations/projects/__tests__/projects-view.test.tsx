import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), listPersonas: vi.fn(), threadId: "thr_1" as string | undefined }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgent: () => ({ agent: { threadId: mocks.threadId } }) }));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
  listPersonas: () => mocks.listPersonas(),
}));

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
  mocks.threadId = "thr_1";
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
  mocks.listPersonas.mockReset().mockResolvedValue({
    count: 2,
    personas: [
      { id: "companion-x-default", name: "Default", description: "", model: null },
      { id: "researcher", name: "Researcher", description: "", model: null },
    ],
  });
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

  async function fillForm() {
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "New effort" } });
    fireEvent.change(screen.getByLabelText("Spec"), { target: { value: "Do the thing each cycle." } });
    await waitFor(() => expect((screen.getByLabelText("Agent") as HTMLSelectElement).options.length).toBe(2));
  }

  it("starts a project from the chosen persona and the active chat thread", async () => {
    render(<ProjectsView />);
    await fillForm();
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "researcher" } });
    fireEvent.click(screen.getByRole("button", { name: "Start project" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("workflow.start_loop", {
      kind: "goal", agent_id: "researcher", objective: "New effort",
      cycle_instructions: "Do the thing each cycle.", interval_seconds: 300, max_cycles: 24,
      envelope: { session_id: "thr_1" },
    }));
    await waitFor(() => expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe(""));
  });

  it("asks for a chat first and cannot start when there is no active thread", async () => {
    mocks.threadId = undefined;
    render(<ProjectsView />);
    await fillForm();
    expect(screen.getByText(/Open or start a chat first/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Start project" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps the form and shows the server reason when starting fails", async () => {
    mocks.callTool.mockImplementation((name: string) => name === "workflow.start_loop"
      ? Promise.resolve({ ok: false, error: { message: "loop_origin_not_found" } })
      : defaultImpl(name));
    render(<ProjectsView />);
    await fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Start project" }));
    const alert = await screen.findByText(/Could not start the project/);
    expect(alert.textContent).toContain("loop_origin_not_found");
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("New effort");
    expect((screen.getByLabelText("Spec") as HTMLTextAreaElement).value).toBe("Do the thing each cycle.");
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
