import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), listTools: vi.fn() }));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
  listTools: (...args: unknown[]) => mocks.listTools(...args),
}));

import WorkflowLibraryView from "../workflow-library-view";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const def1 = { id: "daily-digest", name: "Daily digest", version: 1, tags: ["scheduled"] };
const run1 = { run_id: "run_1", workflow_id: "daily-digest", status: "running", started_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z" };

type Handlers = Record<string, (args: unknown) => Promise<unknown>>;
function route(handlers: Handlers) {
  mocks.callTool.mockImplementation((name: string, args: unknown) =>
    (handlers[name] ?? (() => Promise.resolve(wrap({}))))(args),
  );
}

beforeEach(() => {
  mocks.callTool.mockReset();
  mocks.listTools.mockReset().mockResolvedValue({ tools: [], count: 0 });
});

describe("WorkflowLibraryView states", () => {
  it("shows a truthful loading state then the empty state", async () => {
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: [] }),
      "workflow.list_runs": async () => wrap({ runs: [] }),
    });
    render(<WorkflowLibraryView />);
    expect(screen.getByText(/Loading workflow library/i)).toBeTruthy();
    await screen.findByText(/No workflows yet/i);
    expect(screen.getByText(/No runs yet/i)).toBeTruthy();
  });

  it("renders retry copy without a raw error and re-fetches", async () => {
    route({ "workflow.get_workflow_registry": async () => { throw new Error("boom"); } });
    render(<WorkflowLibraryView />);
    const alert = await screen.findByText(/Workflow library unavailable right now/i);
    expect(alert.parentElement?.textContent).not.toContain("boom");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(mocks.callTool.mock.calls.filter((c) => c[0] === "workflow.get_workflow_registry").length).toBeGreaterThan(1),
    );
  });

  it("renders definitions and runs", async () => {
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: [def1] }),
      "workflow.list_runs": async () => wrap({ runs: [run1] }),
    });
    render(<WorkflowLibraryView />);
    expect(await screen.findByText("Daily digest")).toBeTruthy();
    expect(screen.getAllByText("daily-digest").length).toBeGreaterThan(0);
    expect(screen.getByText("scheduled")).toBeTruthy();
    expect(screen.getByText("run_1")).toBeTruthy();
    expect(screen.getByText("running")).toBeTruthy();
  });

  it("hides authoring controls when the authoring tool is not in the catalog", async () => {
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: [def1] }),
      "workflow.list_runs": async () => wrap({ runs: [] }),
    });
    render(<WorkflowLibraryView />);
    await screen.findByText("Daily digest");
    expect(screen.queryByRole("button", { name: "Add a new workflow definition" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete workflow definition daily-digest" })).toBeNull();
  });

  it("shows authoring controls and creates a definition when the tool is available", async () => {
    mocks.listTools.mockResolvedValue({ tools: ["workflow.authoring.upsert_workflow_definition"], count: 1 });
    let created = false;
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: created ? [def1] : [] }),
      "workflow.list_runs": async () => wrap({ runs: [] }),
      "workflow.authoring.upsert_workflow_definition": async (args) => {
        created = true;
        expect((args as { id: string }).id).toBe("daily-digest");
        return wrap({ ok: true, path: "/x/daily-digest.yaml" });
      },
    });
    render(<WorkflowLibraryView />);
    await screen.findByText(/No workflows yet/i);
    fireEvent.click(screen.getByRole("button", { name: "Add a new workflow definition" }));
    fireEvent.change(screen.getByLabelText("ID"), { target: { value: "daily-digest" } });
    fireEvent.change(screen.getByLabelText("Definition (YAML)"), { target: { value: "name: Daily digest\nsteps: []" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(mocks.callTool.mock.calls.some((c) => c[0] === "workflow.authoring.upsert_workflow_definition")).toBe(true));
    await screen.findByText("Daily digest");
  });

  it("starts a run from a saved definition", async () => {
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: [def1] }),
      "workflow.list_runs": async () => wrap({ runs: [] }),
      "workflow.start_run": async (args) => {
        expect((args as { workflow_name_or_id: string }).workflow_name_or_id).toBe("daily-digest");
        return wrap({ run_id: "run_new", status: "pending" });
      },
    });
    render(<WorkflowLibraryView />);
    await screen.findByText("Daily digest");
    fireEvent.click(screen.getByRole("button", { name: "Run workflow daily-digest" }));
    await waitFor(() => expect(mocks.callTool.mock.calls.some((c) => c[0] === "workflow.start_run")).toBe(true));
  });

  it("cancels a running run", async () => {
    let cancelled = false;
    route({
      "workflow.get_workflow_registry": async () => wrap({ workflows: [] }),
      "workflow.list_runs": async () => wrap({ runs: cancelled ? [] : [run1] }),
      "workflow.cancel_run": async () => { cancelled = true; return wrap({ ok: true, status: "cancelled" }); },
    });
    render(<WorkflowLibraryView />);
    await screen.findByText("run_1");
    fireEvent.click(screen.getByRole("button", { name: "Cancel run run_1" }));
    await waitFor(() => expect(screen.queryByText("run_1")).toBeNull());
  });
});
