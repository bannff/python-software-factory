import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkbenchProvider } from "@/lib/workbench-context";

const mocks = vi.hoisted(() => ({
  data: [] as unknown,
  loading: false,
  error: null as string | null,
}));

vi.mock("@companion-x/shared-renderer", () => ({
  useToolData: () => mocks,
  ComponentTree: ({ nodes }: { nodes: Array<{ id: string }> }) => (
    <div data-testid="component-tree">{nodes[0]?.id}</div>
  ),
}));

import BrickViewRenderer from "../brick-view-renderer";

function view(id: string, nodeId: string) {
  return {
    id, name: id.toUpperCase(), brick: "demo",
    metadata: { description: `${id} description` },
    components: [{ id: nodeId, type: "text", props: { text: id } }],
  };
}

function renderView() {
  return render(
    <WorkbenchProvider>
      <BrickViewRenderer viewTool="demo_get_views" />
    </WorkbenchProvider>,
  );
}

describe("BrickViewRenderer", () => {
  beforeEach(() => {
    mocks.data = [];
    mocks.loading = false;
    mocks.error = null;
  });

  it("keeps one-view DOM content without a selector wrapper", () => {
    mocks.data = [view("only", "only-node")];
    renderView();
    expect(screen.getByTestId("component-tree").textContent).toBe("only-node");
    expect(screen.queryByRole("navigation", { name: "Brick views" })).toBeNull();
  });

  it("registers fetched IDs and switches by retained view ID", async () => {
    mocks.data = [view("overview", "overview-node"), view("models", "models-node")];
    renderView();
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Brick views" })).toBeTruthy());
    expect(screen.getByTestId("component-tree").textContent).toBe("overview-node");
    fireEvent.click(screen.getByRole("button", { name: "MODELS" }));
    await waitFor(() => expect(screen.getByTestId("component-tree").textContent).toBe("models-node"));
  });
});

describe("BrickViewRenderer states", () => {
  beforeEach(() => {
    mocks.data = [];
    mocks.loading = false;
    mocks.error = null;
  });

  it("shows stable skeletons while the first view payload loads", () => {
    mocks.data = null;
    mocks.loading = true;
    renderView();
    expect(screen.getByLabelText("Loading brick views").children).toHaveLength(3);
  });

  it("shows an error when no usable view payload exists", () => {
    mocks.error = "view gateway unavailable";
    renderView();
    expect(screen.getByText("view gateway unavailable")).toBeTruthy();
  });

  it("retains stale view data when refresh reports an error", () => {
    mocks.data = [view("overview", "stale-overview-node")];
    mocks.error = "refresh failed";
    renderView();
    expect(screen.getByTestId("component-tree").textContent).toBe("stale-overview-node");
    expect(screen.queryByText("refresh failed")).toBeNull();
  });
});
