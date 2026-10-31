/**
 * ChartRenderer defensive guards (bd:python-factory-lbvkh).
 *
 * QA-tester verdict (memory `8744e0c1`): a single malformed Chart payload
 * from any A2UI producer would crash the entire chat panel
 * ("Application error: client-side exception") because
 * ``rawData.filter(...)`` had no ``Array.isArray`` guard. Repro evidence:
 * ``.agents/.issues/zg93f-r3-prompt-a-crash-2026-05-29T17-52-41-047Z.png``.
 *
 * These tests pin the contract that bad/missing/oddly-shaped data renders
 * the empty state instead of throwing. Combined with the <InlineView>
 * ErrorBoundary canary, a future Chart bug can no longer require a full
 * page reload.
 */

import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComponentTree } from "../renderers/component-renderer";
import type { ReactAdapterNode } from "../renderers/renderer-types";

vi.mock("../renderers/use-tool-data", () => ({
  useToolData: () => ({ data: null, loading: false, error: null }),
}));

function chartNode(props: Record<string, unknown>): ReactAdapterNode {
  return {
    id: "chart-1",
    component: "Chart",
    originalType: "Chart",
    props,
  };
}

describe("ChartRenderer — bd:lbvkh defensive guards", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  it("does not throw when data is a string instead of an array", () => {
    expect(() =>
      render(
        <ComponentTree
          nodes={[chartNode({ data: "not-an-array" as unknown })]}
        />,
      ),
    ).not.toThrow();
    // Renders the empty state copy.
    expect(screen.queryByText("No chart data")).not.toBeNull();
  });

  it("renders custom empty_state copy when provided", () => {
    render(
      <ComponentTree
        nodes={[
          chartNode({
            data: { unexpected: "shape" } as unknown,
            empty_state: "Nothing to chart yet",
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Nothing to chart yet")).not.toBeNull();
  });

  it("logs a warn when data is non-array, non-null", () => {
    render(<ComponentTree nodes={[chartNode({ data: 42 as unknown })]} />);
    expect(warnSpy).toHaveBeenCalled();
  });

  it("does not warn when data is omitted (defaults to [])", () => {
    render(<ComponentTree nodes={[chartNode({})]} />);
    expect(warnSpy).not.toHaveBeenCalled();
    expect(screen.queryByText("No chart data")).not.toBeNull();
  });

  it("still renders valid array data correctly (regression pin)", () => {
    render(
      <ComponentTree
        nodes={[
          chartNode({
            data: [
              { name: "a", value: 10 },
              { name: "b", value: 20 },
            ],
            xKey: "name",
            yKey: "value",
          }),
        ]}
      />,
    );
    expect(screen.queryByText("10")).not.toBeNull();
    expect(screen.queryByText("20")).not.toBeNull();
  });
});
