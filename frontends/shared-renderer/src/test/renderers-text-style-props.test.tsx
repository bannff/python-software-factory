/**
 * GH #78 — Text semantic style props (color/size/align) reach the DOM.
 *
 * Catalog (`components.py` Text.optionalProps) declares `color`, `size`,
 * `align`. The renderer maps them to inline CSS: color→color,
 * size→font-size (number/numeric-string → px), align→text-align.
 * Complements the free-form `props.style` wrapper canary
 * (renderers-style-passthrough.test.tsx) with the semantic-prop contract.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
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
    id: `${type}-gh78`,
    component: type,
    originalType: type,
    props,
    children,
  };
}

const COLOR_NEEDLE = "rgb(255, 0, 153)"; // #ff0099

describe("Text({color}) — inline color", () => {
  it("hex color paints to the text element", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "Daniel", color: "#ff0099" })]} />,
    );
    const el = Array.from(container.querySelectorAll<HTMLElement>("p, h1, h2, h3, h4"))
      .find((e) => e.style.color === COLOR_NEEDLE);
    expect(el, "Text dropped props.color — styled text renders gray").not.toBeUndefined();
  });
});

describe("Text({size}) — font-size mapping", () => {
  it("number → px", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "x", size: 24 })]} />,
    );
    const el = container.querySelector<HTMLElement>("[style*='font-size']");
    expect(el?.style.fontSize).toBe("24px");
  });

  it("numeric string → px", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "x", size: "18" })]} />,
    );
    const el = container.querySelector<HTMLElement>("[style*='font-size']");
    expect(el?.style.fontSize).toBe("18px");
  });

  it("CSS length string passes through", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "x", size: "1.5rem" })]} />,
    );
    const el = container.querySelector<HTMLElement>("[style*='font-size']");
    expect(el?.style.fontSize).toBe("1.5rem");
  });
});

describe("Text({align}) — text-align mapping", () => {
  it("center paints to the text element", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "x", align: "center" })]} />,
    );
    const el = container.querySelector<HTMLElement>("[style*='text-align']");
    expect(el?.style.textAlign).toBe("center");
  });
});

describe("Text without style props — no style attr", () => {
  it("plain text stays clean", () => {
    const { container } = render(
      <ComponentTree nodes={[node("Text", { text: "plain" })]} />,
    );
    expect(container.querySelector("p[style]")).toBeNull();
  });
});
