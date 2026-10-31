import React from "react";
import { fireEvent, render } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ zoomToFit: vi.fn(), loadTopology: vi.fn(async () => {}), loadRunTopology: vi.fn(async () => {}) }));
let graphData = { nodes: [{ id: "a", name: "A", type: "Agent", color: "blue", val: 1 }], links: [] as Array<{ source: string; target: string }> };

vi.mock("next/dynamic", async () => {
  const ReactModule = await import("react");
  return { default: () => ReactModule.forwardRef((_props, ref) => { ReactModule.useImperativeHandle(ref, () => ({ zoomToFit: mocks.zoomToFit })); return <div data-testid="force-graph" />; }) };
});
vi.mock("@/lib/hooks/use-graph-data", () => ({
  colorForType: () => "#60a5fa",
  useGraphData: () => ({ data: graphData, loading: false, hasLoaded: true, error: null, stats: null, loadedContext: null, loadTopology: mocks.loadTopology, loadRunTopology: mocks.loadRunTopology, listRecentRuns: vi.fn(async () => []), loadGraphContext: vi.fn(), expandNode: vi.fn(async () => true) }),
}));
vi.mock("@/lib/hooks/use-graph-restore", () => ({ useGraphRestore: vi.fn() }));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({ useLiveToolStream: () => ({ entries: [] }) }));
vi.mock("@/lib/workbench-context", () => ({ useWorkbenchContext: () => ({ focusedRunId: null, focusRun: vi.fn(), clearRunFocus: vi.fn(), graphRestoreRequest: null, acknowledgeGraphRestore: vi.fn(), reportNavigationStatus: vi.fn(), openMetrics: vi.fn() }) }));

import GraphView from "../graph-view";

beforeAll(() => {
  global.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} } as typeof ResizeObserver;
});

describe("Graph camera", () => {
  it("never auto-fits on topology changes; Fit remains explicit", () => {
    mocks.zoomToFit.mockReset();
    const props = { steps: [], toolCalls: [], agentState: {} };
    const rendered = render(<GraphView {...props} />);
    graphData = { nodes: [...graphData.nodes, { id: "b", name: "B", type: "Agent", color: "blue", val: 1 }], links: [] };
    rendered.rerender(<GraphView {...props} />);
    expect(mocks.zoomToFit).not.toHaveBeenCalled();
    fireEvent.click(rendered.getByTitle("Fit to view"));
    expect(mocks.zoomToFit).toHaveBeenCalledTimes(1);
  });
});
