import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BridgeAdapterProvider, type BridgeAdapter } from "../index";
import { MetricCardRenderer } from "../renderers/renderers-metric";
import { LineageRenderer, normalizeLineageData } from "../renderers/renderers-lineage";
import type { ReactAdapterNode } from "../renderers/renderer-types";

const renderChildren = () => null;
const node = (component: string, props: Record<string, unknown>): ReactAdapterNode => ({
  id: "test", component, originalType: component, props,
});

class Adapter implements BridgeAdapter {
  constructor(private readonly value: unknown) {}
  async callTool(): Promise<unknown> { return { result: this.value }; }
}

function withAdapter(element: React.ReactElement, value: unknown) {
  return render(<BridgeAdapterProvider adapter={new Adapter(value)}>{element}</BridgeAdapterProvider>);
}

describe("Metric data_path", () => {
  it("resolves a nested value before metric extraction", async () => {
    withAdapter(
      <MetricCardRenderer node={node("Metric", {
        label: "Runs", value: "Unknown", data_tool: "summary", data_path: "$.overview.runs",
      })} renderChildren={renderChildren} />,
      { overview: { runs: 7 } },
    );
    await waitFor(() => expect(screen.getByText("7")).toBeTruthy());
  });
});

describe("Lineage", () => {
  it("caps nodes and removes dangling edges deterministically", () => {
    const nodes = Array.from({ length: 105 }, (_, index) => ({
      node_id: `node-${String(index).padStart(3, "0")}`,
    }));
    const result = normalizeLineageData({
      nodes,
      edges: [
        { source: "node-000", target: "node-099", relation: "KEPT" },
        { source: "node-000", target: "node-104", relation: "DROPPED" },
      ],
    });
    expect(result.nodes).toHaveLength(100);
    expect(result.edges).toHaveLength(1);
    expect(result.truncated).toBe(true);
    expect(result.dropped_edges).toBe(1);
  });

  it("renders disconnected static nodes and explicit missing links", () => {
    withAdapter(
      <LineageRenderer node={node("Lineage", { data: {
        nodes: [
          { node_id: "a", entity_type: "TrainingRun", source_ref: "run-a" },
          { node_id: "b", entity_type: "WorkflowRun", source_ref: "run-b" },
        ],
        edges: [], missing_links: [{ node_id: "a", kinds: ["dataset"] }],
      } })} renderChildren={renderChildren} />,
      {},
    );
    expect(screen.getByText("run-a")).toBeTruthy();
    expect(screen.getByText("run-b")).toBeTruthy();
    expect(screen.getByText(/Missing links: dataset/)).toBeTruthy();
  });

  it("loads generic tool data through data_path", async () => {
    withAdapter(
      <LineageRenderer node={node("Lineage", {
        data_tool: "lineage", data_path: "$.payload",
      })} renderChildren={renderChildren} />,
      { payload: { nodes: [{ node_id: "x", source_ref: "tool-node" }], edges: [] } },
    );
    await waitFor(() => expect(screen.getByText("tool-node")).toBeTruthy());
  });
});
