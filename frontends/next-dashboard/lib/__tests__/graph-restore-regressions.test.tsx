import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { useGraphRestore } from "@/lib/hooks/use-graph-restore";
import type { GraphData } from "@/lib/graph-data-utils";
import { unwrap } from "@/lib/graph-data-utils";
import type { BoundedGraphContext, GraphNode, NavigationRef } from "@/lib/types";

const NODE: GraphNode = {
  id: "entity-1", name: "Entity 1", type: "Agent", color: "#3b82f6", val: 1,
};
const REF: NavigationRef = {
  version: "v1", surface: "graph", target_ref: NODE.id, label: NODE.name,
  graph_selected_ref: NODE.id,
  graph_context: { query_ref: NODE.id, neighborhood_limit: 2 },
  focus_origin: null,
};

type Loader = (query: string, limit: number, selected: string) => Promise<GraphNode | null>;
type Expander = (nodeId: string, limit?: number) => Promise<boolean>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function RestoreHarness({
  request, loadGraphContext, expandNode, acknowledge, report,
}: {
  request: NavigationRef;
  loadGraphContext: Loader;
  expandNode: Expander;
  acknowledge: (target?: string, status?: string) => void;
  report: (status: string) => void;
}) {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loadedContext, setLoadedContext] = useState<BoundedGraphContext | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const load = async (query: string, limit: number, selectedRef: string) => {
    const node = await loadGraphContext(query, limit, selectedRef);
    if (node) {
      setData({ nodes: [node], links: [] });
      setLoadedContext({ query_ref: query, neighborhood_limit: limit });
    }
    return node;
  };
  useGraphRestore({
    request, data, loadedContext, selected, onSelect: setSelected,
    loadGraphContext: load, expandNode,
    acknowledgeGraphRestore: acknowledge, reportNavigationStatus: report,
  });
  return <output data-testid="selected">{selected?.id ?? ""}</output>;
}

function RetryHarness(props: Omit<React.ComponentProps<typeof RestoreHarness>, "request">) {
  const [request, setRequest] = useState(REF);
  return (
    <>
      <button onClick={() => setRequest({
        ...REF,
        graph_context: REF.graph_context ? { ...REF.graph_context } : null,
        focus_origin: REF.focus_origin ? { ...REF.focus_origin } : null,
      })}>Retry navigation</button>
      <RestoreHarness {...props} request={request} />
    </>
  );
}

describe("Graph restore transaction regressions", () => {
  it("does not cancel an in-flight restore when graph data is updated", async () => {
    const pending = deferred<GraphNode>();
    const load = vi.fn(() => pending.promise);
    const expand = vi.fn(async () => true);
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<RestoreHarness
      request={REF} loadGraphContext={load} expandNode={expand}
      acknowledge={acknowledge} report={report}
    />);

    await waitFor(() => expect(load).toHaveBeenCalledWith("entity-1", 2, "entity-1"));
    expect(acknowledge).not.toHaveBeenCalled();
    await act(async () => { pending.resolve(NODE); });
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(expand).toHaveBeenCalledWith("entity-1", 2);
    expect(report).not.toHaveBeenCalled();
  });

  it("retries after load failure when navigation gets a fresh equivalent request", async () => {
    const load = vi.fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(NODE);
    const expand = vi.fn(async () => true);
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<RetryHarness
      loadGraphContext={load} expandNode={expand}
      acknowledge={acknowledge} report={report}
    />);

    await waitFor(() => expect(report).toHaveBeenCalledWith(
      expect.stringMatching(/requested context is unavailable/),
    ));
    expect(acknowledge).not.toHaveBeenCalled();
    fireEvent.click(document.querySelector("button")!);
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(load).toHaveBeenCalledTimes(2);
    expect(expand).toHaveBeenCalledTimes(1);
  });

  it("does not acknowledge until selection expansion succeeds", async () => {
    const expansion = deferred<boolean>();
    const acknowledge = vi.fn();
    render(<RestoreHarness
      request={REF} loadGraphContext={vi.fn(async () => NODE)}
      expandNode={vi.fn(() => expansion.promise)}
      acknowledge={acknowledge} report={vi.fn()}
    />);

    await waitFor(() => expect(acknowledge).not.toHaveBeenCalled());
    await act(async () => { expansion.resolve(true); });
    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
  });

  it("does not acknowledge after expansion fails", async () => {
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<RestoreHarness
      request={REF} loadGraphContext={vi.fn(async () => NODE)}
      expandNode={vi.fn(async () => false)}
      acknowledge={acknowledge} report={report}
    />);

    await waitFor(() => expect(report).toHaveBeenCalledWith(
      expect.stringMatching(/neighborhood is unavailable/),
    ));
    expect(acknowledge).not.toHaveBeenCalled();
  });

  it("does not acknowledge a restore when a gateway returns a bare error", async () => {
    const acknowledge = vi.fn();
    const report = vi.fn();
    render(<RestoreHarness
      request={REF}
      loadGraphContext={vi.fn(async () => unwrap({ result: { error: "Graph unavailable" } }) as GraphNode)}
      expandNode={vi.fn(async () => true)}
      acknowledge={acknowledge}
      report={report}
    />);

    await waitFor(() => expect(report).toHaveBeenCalledWith(
      expect.stringMatching(/requested context is unavailable/),
    ));
    expect(acknowledge).not.toHaveBeenCalled();
  });

  it("keeps the unavailable-focus status after a successful restore", async () => {
    const acknowledge = vi.fn();
    render(<RestoreHarness
      request={REF} loadGraphContext={vi.fn(async () => NODE)}
      expandNode={vi.fn(async () => true)}
      acknowledge={acknowledge} report={vi.fn()}
    />);

    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(acknowledge.mock.calls[0][1]).toMatch(/focus origin unavailable/i);
  });
});
