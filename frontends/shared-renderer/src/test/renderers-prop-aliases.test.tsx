/**
 * Catalog ↔ renderer prop-name parity canary
 * (bd:python-factory-3hkqx round 4 — prop-alias regression).
 *
 * The BE A2UI catalog
 * (``components/ui/src/factory/ui/runtime/a2ui/components.py``)
 * declares ``required_props`` per type. That spec surfaces to the
 * agent through tool docstrings, so the LLM emits exactly those names.
 * If the renderer reads a different name, the slot paints to nothing
 * — the user-visible "Live tab is empty after Round 3" bug.
 *
 * This canary instantiates each catalog type via ``<ComponentTree>``
 * with the **catalog-spec'd** prop name and asserts the value reaches
 * the DOM. Any FAIL = doc-vs-impl drift; file a bd per type. RED tests
 * here pin the exact mismatch:
 *   • Text({content}) — catalog says ``content``; renderer reads ``text``.
 *   • Text({value})   — agent emits ``value`` (round-3 evidence).
 *   • Alert({message}) — catalog says ``message``; renderer reads
 *     ``title``/``description``.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComponentTree } from "../renderers/component-renderer";
import type { ReactAdapterNode } from "../renderers/renderer-types";

vi.mock("../renderers/use-tool-data", () => ({
  useToolData: () => ({ data: null, loading: false, error: null }),
}));

function node(
  type: string,
  props: Record<string, unknown>,
  children?: ReactAdapterNode[],
): ReactAdapterNode {
  return {
    id: `${type}-1`,
    component: type,
    originalType: type,
    props,
    children,
  };
}

function renderTree(nodes: ReactAdapterNode[]) {
  return render(<ComponentTree nodes={nodes} />);
}

/** Minimal text-rendered cases — pass type + props + expected DOM text. */
const TEXT_CASES: Array<[string, string, Record<string, unknown>, string]> = [
  // The three lines below are the bug surface — RED until the renderer
  // accepts the catalog-spec'd alias OR the catalog/agent are realigned.
  ["Text", "content", { content: "hello-content-prop" }, "hello-content-prop"],
  ["Text", "value (agent emits)", { value: "hello-value-prop" }, "hello-value-prop"],
  ["Alert", "message", { message: "alert-message-prop" }, "alert-message-prop"],
  // Already-green baselines — pin the contract that DOES work today.
  ["Text", "text", { text: "hello-text-prop" }, "hello-text-prop"],
  ["Button", "label", { label: "click-me" }, "click-me"],
  ["Alert", "title+description", { title: "alert-title", description: "alert-desc" }, "alert-title"],
  ["Card", "title+description", { title: "card-t", description: "card-d" }, "card-t"],
  ["Progress", "label", { value: 42, label: "loading-label" }, "loading-label"],
  ["Metric", "label+value", { label: "metric-label", value: "99" }, "metric-label"],
  ["Form", "submit_label", { fields: [{ name: "x", type: "text" }], submit_label: "GO-BUTTON", tool: "noop" }, "GO-BUTTON"],
  ["Table", "rows[].cell", { columns: [{ key: "name", label: "Name" }], rows: [{ name: "row-cell-value" }] }, "row-cell-value"],
  ["Chart", "data values", { data: [{ name: "a", value: 10 }], xKey: "name", yKey: "value" }, "10"],
];

describe("A2UI catalog ↔ renderer prop-name parity", () => {
  for (const [type, label, props, expected] of TEXT_CASES) {
    it(`${type}({${label}}) → DOM contains "${expected}"`, () => {
      renderTree([node(type, props)]);
      expect(screen.queryByText(expected)).not.toBeNull();
    });
  }

  it("List({items}) — renders each item", () => {
    renderTree([node("List", { items: ["alpha", "beta", "gamma"] })]);
    for (const w of ["alpha", "beta", "gamma"]) {
      expect(screen.queryByText(w)).not.toBeNull();
    }
  });

  it("Image({src}) — img element with src attr", () => {
    const { container } = renderTree([
      node("Image", { src: "https://example.com/x.png", alt: "x" }),
    ]);
    expect(container.querySelector("img")?.getAttribute("src")).toContain(
      "example.com/x.png",
    );
  });

  it("Image accepts arbitrary external hosts (uses plain <img>, not next/image)", () => {
    // bd:python-factory-3hkqx — agent emits picsum/dicebear/data: URIs;
    // next/image would reject any host not in next.config.js, so we
    // ship plain <img>. Pin: the rendered tag is a native <img>, not
    // the next/image's <span><img/></span> wrapper structure.
    const { container } = renderTree([
      node("Image", { src: "https://picsum.photos/seed/cyber1/600/300", alt: "stub" }),
    ]);
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe(
      "https://picsum.photos/seed/cyber1/600/300",
    );
    expect(img?.getAttribute("loading")).toBe("lazy");
  });

  it("Spacer({height}) — emits aria-hidden div", () => {
    const { container } = renderTree([node("Spacer", { height: 24 })]);
    expect(container.querySelector("div[aria-hidden='true']")).not.toBeNull();
  });

  it("Divider({}) — emits role=separator", () => {
    const { container } = renderTree([node("Divider", {})]);
    expect(container.querySelector("[role='separator']")).not.toBeNull();
  });

  it("Sparkline({data}) — emits SVG (line variant)", () => {
    const { container } = renderTree([
      node("Sparkline", { data: [1, 2, 3, 5, 8], variant: "line" }),
    ]);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("StatusDot({value, thresholds}) — emits the dot span", () => {
    const { container } = renderTree([
      node("StatusDot", {
        value: 80,
        thresholds: { warning: 50, critical: 25 },
      }),
    ]);
    expect(container.querySelector("span.rounded-full")).not.toBeNull();
  });

  it("TrendBadge({direction}) — emits an arrow char", () => {
    renderTree([node("TrendBadge", { direction: "up", change_pct: 5 })]);
    expect(/[↑↓→]/.test(document.body.textContent ?? "")).toBe(true);
  });
});
