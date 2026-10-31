import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const tool = vi.fn();
vi.mock("@companion-x/shared-renderer", () => ({
  useToolData: (...args: unknown[]) => tool(...args),
}));
vi.mock("framer-motion", () => ({ motion: new Proxy({}, { get: () => (p: React.PropsWithChildren<Record<string, unknown>>) => React.createElement("div", p, p.children) }) }));

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgentContext: vi.fn() }));

import ArtifactsView from "../artifacts-view";

const artifact = {
  slug: "release-notes", name: "Release notes", description: "Daily summary",
  tags: ["daily"], kind: "text", content: "<img src=x onerror=alert(1)>",
  version: 3, revision: 4, updated_at: "2026-09-11T00:00:00Z", folder_id: null,
};

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });

beforeEach(() => {
  window.history.replaceState({}, "", "/artifacts");
  tool.mockReset();
  callTool.mockReset();
  // The folder sidebar fetches its own list independently of the artifact
  // list/dialog flows under test here; default it to an empty, resolved
  // list so it never blocks or pollutes assertions about OTHER tool calls.
  callTool.mockImplementation((name: string) =>
    name === "artifacts_folder_list" ? Promise.resolve(wrap({ folders: [] })) : Promise.resolve({}),
  );
});

describe("ArtifactsView", () => {
  it("renders authoritative artifacts and opens a stable deep link", () => {
    tool.mockReturnValue({ data: { artifacts: [artifact] }, loading: false, error: null, refetch: vi.fn() });
    render(<ArtifactsView />);
    fireEvent.click(screen.getByRole("button", { name: /Release notes/ }));
    expect(window.location.pathname).toBe("/artifacts/release-notes");
    expect(screen.getByTestId("artifact-escaped-preview").textContent).toContain("<img");
    expect(document.querySelector("img")).toBeNull();
  });

  it("renders a truthful empty state", () => {
    tool.mockReturnValue({ data: { artifacts: [] }, loading: false, error: null, refetch: vi.fn() });
    render(<ArtifactsView />);
    expect(screen.getByText("No artifacts yet")).toBeTruthy();
  });

  it("renders a truthful MCP failure", () => {
    tool.mockReturnValue({ data: null, loading: false, error: "MCP unavailable", refetch: vi.fn() });
    render(<ArtifactsView />);
    expect(screen.getByRole("alert").textContent).toContain("MCP unavailable");
  });

  it("row 63 / P1 item 10: opens the New artifact dialog and creates via the real MCP tool", async () => {
    const refetch = vi.fn();
    tool.mockReturnValue({ data: { artifacts: [] }, loading: false, error: null, refetch });
    callTool.mockImplementation((name: string) => {
      if (name === "artifacts_folder_list") return Promise.resolve(wrap({ folders: [] }));
      if (name === "artifacts_save") return Promise.resolve({
        result: { artifact: { ...artifact, slug: "design-notes", name: "Design notes" } },
      });
      return Promise.resolve({});
    });
    render(<ArtifactsView />);
    fireEvent.click(screen.getByRole("button", { name: /New artifact/ }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Design notes"), { target: { value: "Design notes" } });
    fireEvent.change(screen.getByPlaceholderText("Paste or type the artifact content…"), { target: { value: "body text" } });
    fireEvent.click(screen.getByRole("button", { name: /Create artifact/ }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_save", {
      name: "Design notes", content: "body text", kind: "markdown", description: "", tags: [],
    }));
    expect(refetch).toHaveBeenCalled();
    expect(window.location.pathname).toBe("/artifacts/design-notes");
  });

  it("New artifact dialog cancels without calling the save tool", () => {
    tool.mockReturnValue({ data: { artifacts: [] }, loading: false, error: null, refetch: vi.fn() });
    render(<ArtifactsView />);
    fireEvent.click(screen.getByRole("button", { name: /New artifact/ }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(callTool).not.toHaveBeenCalledWith("artifacts_save", expect.anything());
  });

  it("row 63 remaining gap: lists real folders and filters artifacts by the selected one", async () => {
    const inFolder = { ...artifact, slug: "folder-doc", name: "Folder doc", folder_id: "f1" };
    tool.mockReturnValue({ data: { artifacts: [artifact, inFolder] }, loading: false, error: null, refetch: vi.fn() });
    callTool.mockImplementation((name: string) =>
      name === "artifacts_folder_list"
        ? Promise.resolve(wrap({ folders: [
            { id: "f1", parent_id: null, name: "Reports", revision: 1, path: "/Reports", depth: 1, item_count: 1 },
          ] }))
        : Promise.resolve({}),
    );
    render(<ArtifactsView />);
    await screen.findByText("Reports");
    expect(screen.getByText("Release notes")).toBeTruthy();
    expect(screen.queryByText("Folder doc")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reports 1" }));
    await waitFor(() => expect(screen.getByText("Folder doc")).toBeTruthy());
    expect(screen.queryByText("Release notes")).toBeNull();
  });

  it("row 63 remaining gap: creates a real folder through the sidebar", async () => {
    tool.mockReturnValue({ data: { artifacts: [] }, loading: false, error: null, refetch: vi.fn() });
    let created = false;
    callTool.mockImplementation((name: string, args: unknown) => {
      if (name === "artifacts_folder_list") return Promise.resolve(wrap({
        folders: created ? [{ id: "f2", parent_id: null, name: "Drafts", revision: 1, path: "/Drafts", depth: 1, item_count: 0 }] : [],
      }));
      if (name === "artifacts_folder_create") {
        created = true;
        expect((args as { name: string }).name).toBe("Drafts");
        return Promise.resolve(wrap({ folder: { id: "f2", parent_id: null, name: "Drafts", revision: 1, path: "/Drafts", depth: 1, item_count: 0 } }));
      }
      return Promise.resolve({});
    });
    render(<ArtifactsView />);
    await screen.findByText("All artifacts");
    fireEvent.click(screen.getByRole("button", { name: "New folder" }));
    fireEvent.change(screen.getByPlaceholderText("Folder name"), { target: { value: "Drafts" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByText("Drafts");
  });
});
