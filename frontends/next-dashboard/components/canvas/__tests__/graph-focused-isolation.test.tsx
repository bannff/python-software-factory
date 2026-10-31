import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  focusedRunId: null as string | null,
  detailTarget: "entity-2",
}));
type GraphCanvasMockProps = {
  graphData: { nodes: { id: string }[] };
  onNodeClick: (node: { id: string }) => void;
};
vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
vi.mock("next/dynamic", () => ({
  default: () => ({ graphData, onNodeClick }: GraphCanvasMockProps) => (
    <button onClick={() => onNodeClick(graphData.nodes[0])}>Canvas node</button>
  ),
}));
vi.mock("../graph-node-detail", () => ({
  GraphNodeDetail: ({ node, onNodeSelect }: { node: { name: string }; onNodeSelect: (id: string) => void }) => (
    <div><span>{node.name}</span><button onClick={() => onNodeSelect(state.detailTarget)}>Detail node</button></div>
  ),
}));
vi.mock("../graph-toolbar", () => ({ GraphToolbar: () => null }));
vi.mock("../graph-type-filters", () => ({ GraphTypeFilters: () => null }));
vi.mock("../runs-selector", () => ({ RunsSelector: () => null }));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({ useLiveToolStream: () => ({ entries: [] }) }));
vi.mock("@/lib/workbench-context", () => ({
  useWorkbenchContext: () => ({
    focusedRunId: state.focusedRunId, focusRun: vi.fn(), clearRunFocus: vi.fn(),
    graphRestoreRequest: null, acknowledgeGraphRestore: vi.fn(),
    reportNavigationStatus: vi.fn(), openMetrics: vi.fn(),
  }),
}));

import { callTool } from "@/lib/api";
import GraphView from "../graph-view";

const tool = vi.mocked(callTool);
const nodes = [
  { id: "entity-1", type: "Agent", properties: { name: "Entity 1" } },
  { id: "entity-2", type: "Agent", properties: { name: "Entity 2" } },
];

beforeAll(() => {
  global.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} } as typeof ResizeObserver;
});
beforeEach(() => {
  state.focusedRunId = null;
  state.detailTarget = "entity-2";
  tool.mockReset();
  tool.mockImplementation(async (name) => {
    if (name === "graph_get_run_topology") return { tool: name, result: { nodes, edges: [] } } as never;
    if (name === "graph_find_entities") return { tool: name, result: { entities: nodes } } as never;
    if (name === "graph_get_neighbors") return { tool: name, result: { neighbors: [] } } as never;
    return { tool: name, result: { node_count: 2, edge_count: 0 } } as never;
  });
});

function renderGraph() {
  return render(<GraphView steps={[]} toolCalls={[]} agentState={{}} />);
}
function broadCalls() {
  return tool.mock.calls.filter(([name]) => name === "graph_get_neighbors" || name === "graph_get_entity");
}

describe("focused Graph interaction isolation", () => {
  it("selects from canvas and detail without broad reads while focused", async () => {
    state.focusedRunId = "run-exact";
    renderGraph();
    fireEvent.click(await screen.findByRole("button", { name: "Canvas node" }));
    expect(await screen.findByText("Entity 1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Detail node" }));
    expect(await screen.findByText("Entity 2")).toBeTruthy();
    expect(broadCalls()).toHaveLength(0);
  });

  it("does not select a detail target outside the exact-run dataset", async () => {
    state.focusedRunId = "run-exact";
    state.detailTarget = "outside-run";
    renderGraph();
    fireEvent.click(await screen.findByRole("button", { name: "Canvas node" }));
    fireEvent.click(await screen.findByRole("button", { name: "Detail node" }));
    expect(screen.getByText("Entity 1")).toBeTruthy();
    expect(screen.queryByText("Entity 2")).toBeNull();
    expect(broadCalls()).toHaveLength(0);
  });

  it("preserves broad-mode expansion for canvas and detail navigation", async () => {
    renderGraph();
    fireEvent.click(await screen.findByRole("button", { name: "Canvas node" }));
    fireEvent.click(await screen.findByRole("button", { name: "Detail node" }));
    await waitFor(() => expect(broadCalls()).toHaveLength(2));
    expect(broadCalls().map(([, args]) => args)).toEqual([
      { entity_id: "entity-1", limit: 20 },
      { entity_id: "entity-2", limit: 20 },
    ]);
  });
});
