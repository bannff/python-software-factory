import React from "react";
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ComponentTree } from "../index";

const mount = (node: { id: string; component: string; originalType: string; props: Record<string, unknown> }) =>
  render(<ComponentTree nodes={[node]} />).container.textContent ?? "";

describe("FallbackComponent", () => {
  it("names the unsupported type and the node id", () => {
    const text = mount({ id: "n1", component: "Gizmo", originalType: "Gizmo", props: {} });
    expect(text).toMatch(/Unknown component: Gizmo/);
    expect(text).toMatch(/ID: n1/);
  });

  it("says when a node carries no type at all and lists the props it did get", () => {
    const text = mount({ id: "", component: "", originalType: "", props: { label: "x", count: 2 } });
    expect(text).toMatch(/no type/i);
    expect(text).toMatch(/label, count/);
    expect(text).not.toMatch(/type:\s*\|/);
  });
});
