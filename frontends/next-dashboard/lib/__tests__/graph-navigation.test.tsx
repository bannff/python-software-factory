import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { GraphNodeDetail } from "@/components/canvas/graph-node-detail";
import { useGraphData } from "@/lib/hooks/use-graph-data";
import { useGraphRestore } from "@/lib/hooks/use-graph-restore";
import { graphMetricsFocusToken } from "@/lib/graph-navigation";
import type { GraphNode, NavigationRef } from "@/lib/types";
import type { GraphData } from "@/lib/graph-data-utils";

vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));

import { callTool } from "@/lib/api";

const callToolMock = vi.mocked(callTool);
const NODE: GraphNode = {
  id: "entity-1", name: "Entity 1", type: "Agent", color: "#3b82f6", val: 1,
  properties: { name: "Entity 1" },
};
const REF: NavigationRef = {
  version: "v1", surface: "graph", target_ref: NODE.id, label: NODE.name,
  graph_selected_ref: NODE.id,
  graph_context: { query_ref: NODE.id, neighborhood_limit: 2 },
  focus_origin: {
    token: graphMetricsFocusToken(NODE.id), surface: "graph", control: "open-metrics",
  },
};

beforeEach(() => callToolMock.mockReset());

describe("Graph context restoration", () => {
  it("loads the exact query reference and bounds the requested neighborhood", async () => {
    callToolMock.mockImplementation(async (name) => {
      if (name === "graph_get_entity") {
        return { tool: name, result: { found: true, entity: { id: NODE.id, type: NODE.type, properties: NODE.properties } } };
      }
      if (name === "graph_get_neighbors") {
        return { tool: name, result: { neighbors: [
          { id: "neighbor-1", type: "Event", properties: {} },
          { id: "neighbor-2", type: "Finding", properties: {} },
          { id: "neighbor-3", type: "Memory", properties: {} },
        ] } };
      }
      return { tool: name, result: { node_count: 4, edge_count: 3 } };
    });

    const { result } = renderHookForGraphData();
    await act(async () => {
      await result.current.loadGraphContext("entity-1", 2);
      await result.current.expandNode("entity-1", 2);
    });

    expect(callToolMock).toHaveBeenCalledWith("graph_get_entity", { entity_id: "entity-1" });
    expect(callToolMock).toHaveBeenCalledWith(
      "graph_get_neighbors", { entity_id: "entity-1", limit: 2 },
    );
    expect(result.current.loadedContext).toEqual({ query_ref: "entity-1", neighborhood_limit: 2 });
    expect(result.current.data.nodes.map((node) => node.id)).toEqual([
      "entity-1", "neighbor-1", "neighbor-2",
    ]);
    expect(result.current.data.links).toHaveLength(2);
  });

  it("does not acknowledge when the neighbor read returns a failure envelope", async () => {
    callToolMock.mockImplementation(async (name) => {
      if (name === "graph_get_entity") {
        return { tool: name, result: { found: true, entity: {
          id: NODE.id, type: NODE.type, properties: NODE.properties,
        } } };
      }
      if (name === "graph_get_neighbors") {
        return { tool: name, result: { ok: false, error: "backend unavailable" } };
      }
      return { tool: name, result: { node_count: 1, edge_count: 0 } };
    });
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<DataRestoreHarness acknowledge={acknowledge} report={report} />);

    await waitFor(() => expect(report).toHaveBeenCalledWith(
      expect.stringMatching(/requested context is unavailable/),
    ));
    expect(acknowledge).not.toHaveBeenCalled();
  });
});

function renderHookForGraphData() {
  let current: ReturnType<typeof useGraphData> | null = null;
  function Harness() {
    current = useGraphData();
    return null;
  }
  const rendered = render(<Harness />);
  return {
    ...rendered,
    result: { get current() { return current!; } },
  };
}

function DataRestoreHarness({
  acknowledge, report,
}: {
  acknowledge: (target?: string, status?: string) => void;
  report: (status: string) => void;
}) {
  const graph = useGraphData();
  const [selected, setSelected] = useState<GraphNode | null>(null);
  useGraphRestore({
    request: REF, data: graph.data, loadedContext: graph.loadedContext, selected,
    onSelect: setSelected, loadGraphContext: graph.loadGraphContext,
    expandNode: graph.expandNode, acknowledgeGraphRestore: acknowledge,
    reportNavigationStatus: report,
  });
  return <output data-testid="selected">{selected?.id ?? ""}</output>;
}

function RestoreHarness({
  withOrigin, loadGraphContext, expandNode, acknowledge, report,
}: {
  withOrigin: boolean;
  loadGraphContext: (query: string, limit: number, selected: string) => Promise<GraphNode>;
  expandNode: (nodeId: string, limit?: number) => Promise<boolean>;
  acknowledge: (target?: string, status?: string) => void;
  report: (status: string) => void;
}) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const empty: GraphData = { nodes: [], links: [] };
  useGraphRestore({
    request: REF, data: empty, loadedContext: null, selected, onSelect: setSelected,
    loadGraphContext, expandNode, acknowledgeGraphRestore: acknowledge,
    reportNavigationStatus: report,
  });
  return (
    <>
      {withOrigin && <button data-focus-origin={REF.focus_origin?.token}>Open metrics</button>}
      <output data-testid="selected">{selected?.id ?? ""}</output>
    </>
  );
}

describe("Graph restore completion and focus", () => {
  it("acknowledges only after expansion and restores the initiating control", async () => {
    const loadGraphContext = vi.fn(async () => NODE);
    const expandNode = vi.fn(async () => true);
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<RestoreHarness {...{ withOrigin: true, loadGraphContext, expandNode, acknowledge, report }} />);

    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(loadGraphContext).toHaveBeenCalledWith("entity-1", 2, "entity-1");
    expect(expandNode).toHaveBeenCalledWith("entity-1", 2);
    expect(acknowledge.mock.calls[0][0]).toBe("entity-1");
    expect(acknowledge.mock.calls[0][1]).toMatch(/focus restored/i);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open metrics" }));
    expect(report).not.toHaveBeenCalled();
  });

  it("keeps an accessible status when the focus origin is unavailable", async () => {
    const acknowledge = vi.fn();
    render(<RestoreHarness
      withOrigin={false}
      loadGraphContext={vi.fn(async () => NODE)}
      expandNode={vi.fn(async () => true)}
      acknowledge={acknowledge}
      report={vi.fn()}
    />);

    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(acknowledge.mock.calls[0][1]).toMatch(/focus origin unavailable/i);
  });
});

describe("Graph detail Metrics handoff", () => {
  it("publishes a stable focus-origin token with the exact navigation ref", () => {
    const onOpenMetrics = vi.fn();
    render(<GraphNodeDetail node={NODE} edges={[]} onClose={vi.fn()} onOpenMetrics={onOpenMetrics} />);

    const button = screen.getByRole("button", { name: "Open metrics" });
    expect(button.getAttribute("data-focus-origin")).toBe(graphMetricsFocusToken(NODE.id));
    fireEvent.click(button);

    expect(onOpenMetrics).toHaveBeenCalledWith(expect.objectContaining({
      version: "v1", surface: "graph", target_ref: NODE.id,
      graph_selected_ref: NODE.id,
      graph_context: { query_ref: NODE.id, neighborhood_limit: 20 },
      focus_origin: {
        token: graphMetricsFocusToken(NODE.id), surface: "graph", control: "open-metrics",
      },
    }));
  });
});
