import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { useGraphData } from "../use-graph-data";

const wrap = (data: unknown) => ({ structuredContent: { ok: true, data } });

beforeEach(() => mocks.callTool.mockReset());

describe("useGraphData broad-view exclusion (Gate A.5 a12a8c66 N3)", () => {
  it("excludes lowercase memory nodes from the unscoped broad view", async () => {
    mocks.callTool.mockImplementation((name: string) => {
      if (name === "graph_get_stats") return Promise.resolve(wrap({ node_count: 2, edge_count: 0 }));
      if (name === "graph_find_entities") {
        return Promise.resolve(wrap({
          entities: [
            { id: "mem-1", type: "memory", properties: { content: "private note" } },
            { id: "agent-1", type: "Agent", properties: { agent_id: "agent-1" } },
          ],
        }));
      }
      return Promise.resolve(wrap({}));
    });
    const { result } = renderHook(() => useGraphData());
    await act(async () => { await result.current.loadTopology(); });
    const ids = result.current.data.nodes.map((n) => n.id);
    expect(ids).not.toContain("mem-1");
    expect(ids).toContain("agent-1");
  });

  it("still includes memory nodes when the Memories preset explicitly requests them", async () => {
    mocks.callTool.mockImplementation((name: string, args?: Record<string, unknown>) => {
      if (name === "graph_get_stats") return Promise.resolve(wrap({ node_count: 1, edge_count: 0 }));
      if (name === "graph_find_entities" && args?.entity_type === "memory") {
        return Promise.resolve(wrap({ entities: [{ id: "mem-1", type: "memory", properties: { content: "note" } }] }));
      }
      return Promise.resolve(wrap({ entities: [] }));
    });
    const { result } = renderHook(() => useGraphData());
    await act(async () => { await result.current.loadTopology("memory"); });
    expect(result.current.data.nodes.map((n) => n.id)).toContain("mem-1");
  });
});
