import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), listTools: vi.fn() }));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
  listTools: (...args: unknown[]) => mocks.listTools(...args),
}));

import WorkflowLibraryView from "../workflow-library-view";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
// Shape of the real `workflow.get_run` / `list_runs` row (RunOutput).
const record = (over: Record<string, unknown> = {}) => ({
  run_id: "run_1", workflow_id: "daily-digest", status: "completed", revision: 3,
  current_step_id: "summarize", waiting_for_event_type: null, last_event_id: 4,
  started_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:05:00Z",
  input: { topic: "ai" }, result: { summary: "done" }, error: null, ...over,
});

function serve(detail: unknown) {
  mocks.listTools.mockResolvedValue({ tools: [], count: 0 });
  mocks.callTool.mockImplementation(async (name: string) => {
    if (name === "workflow_get_workflow_registry") return wrap({ workflows: [] });
    if (name === "workflow_list_runs") return wrap({ runs: [record()] });
    if (name === "workflow_get_run") {
      if (detail instanceof Error) throw detail;
      return wrap(detail);
    }
    return wrap({ ok: true });
  });
}

beforeEach(() => { mocks.callTool.mockReset(); mocks.listTools.mockReset(); });

describe("run detail", () => {
  it("reads the run with workflow_get_run and shows its step, input and result", async () => {
    serve(record());
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    fireEvent.click(screen.getByRole("button", { name: "Show details for run run_1" }));
    const panel = await screen.findByRole("region", { name: "Run run_1 details" });
    expect(mocks.callTool).toHaveBeenCalledWith("workflow_get_run", { run_id: "run_1" });
    expect(panel.textContent).toMatch(/summarize/);
    expect(panel.textContent).toMatch(/"topic": "ai"/);
    expect(panel.textContent).toMatch(/"summary": "done"/);
  });

  it("shows what a waiting run is waiting for", async () => {
    serve(record({ status: "waiting", waiting_for_event_type: "approval.granted", result: null }));
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    fireEvent.click(screen.getByRole("button", { name: "Show details for run run_1" }));
    const panel = await screen.findByRole("region", { name: "Run run_1 details" });
    expect(panel.textContent).toMatch(/approval\.granted/);
    expect(panel.textContent).not.toMatch(/Result/);
  });

  it("states a failed read instead of an empty panel", async () => {
    serve(new Error("Run not found"));
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    fireEvent.click(screen.getByRole("button", { name: "Show details for run run_1" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Couldn.t load this run.*Run not found/);
  });

  it("hides the panel again on a second click", async () => {
    serve(record());
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    const toggle = screen.getByRole("button", { name: "Show details for run run_1" });
    fireEvent.click(toggle);
    await screen.findByRole("region", { name: "Run run_1 details" });
    fireEvent.click(screen.getByRole("button", { name: "Hide details for run run_1" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Run run_1 details" })).toBeNull());
  });
});
