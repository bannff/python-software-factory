import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
import { callTool } from "@/lib/api";
import { useGraphData } from "@/lib/hooks/use-graph-data";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const tool = vi.mocked(callTool);
beforeEach(() => tool.mockReset());

describe("Graph focus loading", () => {
  it("guards exact topology from a stale broad response", async () => {
    const broad = deferred<never>();
    const exact = deferred<never>();
    tool.mockImplementation((name) => {
      if (name === "graph_get_stats") return Promise.resolve({ tool: name, result: { node_count: 2, edge_count: 1 } }) as never;
      if (name === "graph_find_entities") return broad.promise;
      if (name === "graph_get_run_topology") return exact.promise;
      return Promise.resolve({ tool: String(name), result: {} }) as never;
    });
    const { result } = renderHook(() => useGraphData());
    let broadLoad!: Promise<void>;
    let exactLoad!: Promise<void>;
    act(() => { broadLoad = result.current.loadTopology(); exactLoad = result.current.loadRunTopology("full-run-id"); });
    await act(async () => {
      exact.resolve({ tool: "graph_get_run_topology", result: { nodes: [{ id: "exact", type: "WorkflowRun", properties: {} }], edges: [] } } as never);
      await exactLoad;
    });
    expect(result.current.data.nodes.map((node) => node.id)).toEqual(["exact"]);
    expect(tool).toHaveBeenCalledWith("graph_get_run_topology", {
      run_id: "full-run-id", limit: 200,
    });
    await act(async () => {
      broad.resolve({ tool: "graph_find_entities", result: { entities: [{ id: "stale", type: "Agent", properties: {} }] } } as never);
      await broadLoad;
    });
    expect(result.current.data.nodes.map((node) => node.id)).toEqual(["exact"]);
  });
});


it("blocks every broad Graph loader while scoped to an exact run", async () => {
  const { result } = renderHook(() => useGraphData(true));
  let context: Awaited<ReturnType<typeof result.current.loadGraphContext>>;
  let expanded: boolean;
  await act(async () => {
    await result.current.loadTopology();
    context = await result.current.loadGraphContext("entity-1", 20, "entity-2");
    expanded = await result.current.expandNode("entity-1", 20);
  });
  expect(context!).toBeNull();
  expect(expanded!).toBe(false);
  expect(tool).not.toHaveBeenCalled();
});