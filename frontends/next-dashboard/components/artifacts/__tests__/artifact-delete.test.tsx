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
  tags: ["daily"], kind: "text", content: "body",
  version: 3, revision: 4, updated_at: "2026-09-11T00:00:00Z", folder_id: null,
};

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const tombstoned = { slug: artifact.slug, tombstoned: true, event_published: true, warning: null };

/** Model the real library: a successful tombstone leaves `artifacts_list`. */
function renderLibrary() {
  let listed: (typeof artifact)[] = [artifact];
  tool.mockImplementation(() => ({
    data: { artifacts: listed }, loading: false, error: null,
    refetch: () => { listed = []; },
  }));
  render(<ArtifactsView />);
  fireEvent.click(screen.getByRole("button", { name: /Release notes/ }));
}

async function confirmDelete() {
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
}

const tombstoneResult = (name: string) => {
  if (name === "artifacts_folder_list") return Promise.resolve(wrap({ folders: [] }));
  if (name === "artifacts_tombstone") return Promise.resolve(wrap(tombstoned));
  return Promise.resolve({});
};

beforeEach(() => {
  window.history.replaceState({}, "", "/artifacts");
  tool.mockReset();
  callTool.mockReset();
  callTool.mockImplementation(tombstoneResult);
});

describe("artifact delete (issue #141)", () => {
  it("deletes through artifacts_tombstone with the CURRENT revision and removes it from the library", async () => {
    renderLibrary();
    await confirmDelete();
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_tombstone", {
      slug: "release-notes", expected_revision: 4,
    }));
    expect(screen.getByLabelText("Deleted artifact")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Release notes/ })).toBeNull();
  });

  it("shows the stale-revision conflict message and keeps the artifact in place when the tombstone fails", async () => {
    callTool.mockImplementation((name: string) => {
      if (name === "artifacts_folder_list") return Promise.resolve(wrap({ folders: [] }));
      if (name === "artifacts_tombstone") return Promise.reject(new Error("tool_execution_failed"));
      return Promise.resolve({});
    });
    renderLibrary();
    await confirmDelete();
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not be deleted/i);
    expect(screen.queryByLabelText("Deleted artifact")).toBeNull();
  });

  it("surfaces the artifact_event_unavailable warning instead of swallowing it", async () => {
    callTool.mockImplementation((name: string) => {
      if (name === "artifacts_folder_list") return Promise.resolve(wrap({ folders: [] }));
      if (name === "artifacts_tombstone") return Promise.resolve(wrap({
        slug: artifact.slug, tombstoned: true, event_published: false, warning: "artifact_event_unavailable",
      }));
      return Promise.resolve({});
    });
    renderLibrary();
    await confirmDelete();
    expect((await screen.findByRole("status")).textContent).toContain("artifact_event_unavailable");
  });

  it("offers purge as a separate, unmistakably permanent action and names the setting when it is disabled", async () => {
    callTool.mockImplementation((name: string) => {
      if (name === "artifacts_folder_list") return Promise.resolve(wrap({ folders: [] }));
      if (name === "artifacts_tombstone") return Promise.resolve(wrap(tombstoned));
      if (name === "artifacts_purge") return Promise.reject(new Error("authoring_disabled"));
      return Promise.resolve({});
    });
    renderLibrary();
    await confirmDelete();
    await screen.findByLabelText("Deleted artifact");
    fireEvent.click(screen.getByRole("button", { name: "Purge permanently" }));
    expect(screen.getByText(/cannot be undone/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm permanent purge" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_purge", {
      slug: "release-notes", expected_revision: 5,
    }));
    expect((await screen.findByRole("alert")).textContent).toContain("ARTIFACTS_ENABLE_AUTHORING_TOOLS");
  });
});
