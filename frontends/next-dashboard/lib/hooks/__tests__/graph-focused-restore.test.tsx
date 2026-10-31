import { render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { GraphData } from "@/lib/graph-data-utils";
import { useGraphRestore } from "@/lib/hooks/use-graph-restore";
import type { GraphNode, NavigationRef } from "@/lib/types";

const NODE: GraphNode = {
  id: "entity-1", name: "Entity 1", type: "Agent", color: "#3b82f6", val: 1,
};
const REF: NavigationRef = {
  version: "v1", surface: "graph", target_ref: NODE.id, label: NODE.name,
  graph_selected_ref: NODE.id,
  graph_context: { query_ref: NODE.id, neighborhood_limit: 20 },
  focus_origin: null,
};

type Props = {
  data: GraphData;
  load: (query: string, limit: number, selected: string) => Promise<GraphNode | null>;
  expand: (nodeId: string, limit?: number) => Promise<boolean>;
  acknowledge: (target?: string, status?: string) => void;
  report: (status: string) => void;
};

function Harness({ data, load, expand, acknowledge, report }: Props) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  useGraphRestore({
    request: REF, data, scoped: true, loadedContext: null, selected,
    onSelect: setSelected, loadGraphContext: load, expandNode: expand,
    acknowledgeGraphRestore: acknowledge, reportNavigationStatus: report,
  });
  return <output>{selected?.id ?? "none"}</output>;
}

describe("focused Graph restore isolation", () => {
  it("selects an already loaded exact-run node without broad reads", async () => {
    const load = vi.fn();
    const expand = vi.fn();
    const acknowledge = vi.fn();
    render(<Harness data={{ nodes: [NODE], links: [] }} load={load} expand={expand}
      acknowledge={acknowledge} report={vi.fn()} />);

    await waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1));
    expect(screen.getByText(NODE.id)).toBeTruthy();
    expect(load).not.toHaveBeenCalled();
    expect(expand).not.toHaveBeenCalled();
  });

  it("reports a scoped failure when the node is absent without broad reads", async () => {
    const load = vi.fn();
    const expand = vi.fn();
    const report = vi.fn();
    const acknowledge = vi.fn();
    render(<Harness data={{ nodes: [], links: [] }} load={load} expand={expand}
      acknowledge={acknowledge} report={report} />);

    await waitFor(() => expect(report).toHaveBeenCalledWith(
      expect.stringMatching(/not present in the focused run/i),
    ));
    expect(load).not.toHaveBeenCalled();
    expect(expand).not.toHaveBeenCalled();
    expect(acknowledge).not.toHaveBeenCalled();
  });
});
