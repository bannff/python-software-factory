import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), listTools: vi.fn() }));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
  listTools: (...args: unknown[]) => mocks.listTools(...args),
}));

import WorkflowLibraryView from "../workflow-library-view";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const def1 = { id: "daily-digest", name: "Daily digest", version: 1, tags: [] };
const run = (status: string, error?: string) => ({
  run_id: "run_1", workflow_id: "daily-digest", status,
  started_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z", ...(error ? { error } : {}),
});
// Real catalog shape: listTools() returns qualified names, never dotted ones.
const CATALOG = ["workflow_get_workflow_registry", "workflow_authoring_upsert_workflow_definition"];

function serve(workflows: unknown[], runs: unknown[], tools = CATALOG) {
  mocks.listTools.mockResolvedValue({ tools, count: tools.length });
  mocks.callTool.mockImplementation(async (name: string) => {
    if (name === "workflow_get_workflow_registry") return wrap({ workflows });
    if (name === "workflow_list_runs") return wrap({ runs });
    return wrap({ ok: true });
  });
}

beforeEach(() => { mocks.callTool.mockReset(); mocks.listTools.mockReset(); });

describe("authoring gate", () => {
  it("offers authoring when the catalog lists the qualified upsert tool", async () => {
    serve([def1], []);
    render(<WorkflowLibraryView />);
    await screen.findByText("Daily digest");
    expect(screen.getByRole("button", { name: "Add a new workflow definition" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Delete workflow definition daily-digest" })).toBeTruthy();
  });

  it("stays off when the catalog lacks the tool", async () => {
    serve([def1], [], ["workflow_get_workflow_registry"]);
    render(<WorkflowLibraryView />);
    await screen.findByText("Daily digest");
    expect(screen.queryByRole("button", { name: "Add a new workflow definition" })).toBeNull();
  });
});

describe("delete confirmation", () => {
  it("does not delete on the first click and deletes on confirm", async () => {
    serve([def1], []);
    render(<WorkflowLibraryView />);
    await screen.findByText("Daily digest");
    fireEvent.click(screen.getByRole("button", { name: "Delete workflow definition daily-digest" }));
    expect(mocks.callTool.mock.calls.some((c) => c[0] === "workflow_authoring_delete_workflow_definition")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete workflow definition daily-digest" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "workflow_authoring_delete_workflow_definition", { id: "daily-digest" }));
  });
});

describe("run actions", () => {
  it.each(["pending", "running", "waiting"])("offers Cancel for a %s run", async (status) => {
    serve([], [run(status)]);
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    expect(screen.getByRole("button", { name: "Cancel run run_1" })).toBeTruthy();
  });

  it.each(["completed", "failed", "cancelled"])("offers no Cancel for a %s run", async (status) => {
    serve([], [run(status)]);
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    expect(screen.queryByRole("button", { name: "Cancel run run_1" })).toBeNull();
  });

  it("shows a cancelled run's reason as neutral text, not an error", async () => {
    serve([], [run("cancelled", "cancelled")]);
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    expect(document.querySelector(".text-destructive")).toBeNull();
  });

  it("still shows a failed run's error in the error colour", async () => {
    serve([], [run("failed", "step exploded")]);
    render(<WorkflowLibraryView />);
    const message = await screen.findByText("step exploded");
    expect(message.className).toContain("text-destructive");
  });
});
