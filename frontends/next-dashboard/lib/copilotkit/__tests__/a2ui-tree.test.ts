/**
 * Tests for ``a2uiToReactAdapterNodes`` (bd:python-factory-3hkqx round 3).
 *
 * Pure-function transform A2UI flat → ReactAdapterNode tree. No React
 * deps, no DOM. Verifies all three child-shape variants and the
 * orphan-parent / no-double-render guarantees.
 *
 * Meta-architect verdict ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q6 T5.
 */

import { describe, expect, it } from "vitest";
import { a2uiToReactAdapterNodes } from "../a2ui-tree";

describe("a2uiToReactAdapterNodes", () => {
  it("returns empty array for empty input", () => {
    expect(a2uiToReactAdapterNodes([])).toEqual([]);
  });

  it("returns empty array for non-array input", () => {
    expect(a2uiToReactAdapterNodes(undefined as unknown as unknown[])).toEqual([]);
    expect(a2uiToReactAdapterNodes(null as unknown as unknown[])).toEqual([]);
  });

  it("renders flat siblings unchanged (no nesting)", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "a", type: "Card", props: { title: "A" } },
      { id: "b", type: "Text", props: { value: "B" } },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0].id).toBe("a");
    expect(out[0].component).toBe("Card");
    expect(out[0].originalType).toBe("Card");
    expect(out[1].id).toBe("b");
    expect(out[0].children).toBeUndefined();
  });

  it("resolves parent: refs into parent.children and drops from top", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "card", type: "Card", props: { title: "Hi" } },
      { id: "txt", type: "Text", parent: "card", props: { value: "x" } },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("card");
    expect(out[0].children).toHaveLength(1);
    expect(out[0].children?.[0].id).toBe("txt");
  });

  it("lifts props.children into adapter children with props.children stripped", () => {
    const out = a2uiToReactAdapterNodes([
      {
        id: "card",
        type: "Card",
        props: {
          title: "Hi",
          children: [{ id: "txt", type: "Text", props: { value: "x" } }],
        },
      },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("card");
    expect(out[0].props).toEqual({ title: "Hi" });
    expect(out[0].props.children).toBeUndefined();
    expect(out[0].children).toHaveLength(1);
    expect(out[0].children?.[0].id).toBe("txt");
  });

  it("nested 3 levels via props.children produces a 3-deep tree", () => {
    const out = a2uiToReactAdapterNodes([
      {
        id: "outer",
        type: "Card",
        props: {
          children: [
            {
              id: "inner",
              type: "Card",
              props: {
                children: [{ id: "leaf", type: "Text", props: { value: "x" } }],
              },
            },
          ],
        },
      },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("outer");
    expect(out[0].children?.[0].id).toBe("inner");
    expect(out[0].children?.[0].children?.[0].id).toBe("leaf");
  });

  it("mixed parent: refs and props.children resolve in one pass", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "card", type: "Card", props: { title: "T" } },
      {
        id: "list",
        type: "List",
        props: { children: [{ id: "li1", type: "Text", props: { value: "i" } }] },
      },
      { id: "child-of-card", type: "Text", parent: "card", props: {} },
      { id: "alone", type: "Alert", props: { message: "hey" } },
    ]);
    const ids = out.map((n) => n.id);
    expect(ids).toEqual(["card", "list", "alone"]);
    expect(out[0].children?.map((c) => c.id)).toEqual(["child-of-card"]);
    expect(out[1].children?.map((c) => c.id)).toEqual(["li1"]);
  });

  it("orphan parent: ref keeps the orphan at top level", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "lonely", type: "Text", parent: "missing", props: {} },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("lonely");
  });

  it("never double-renders: a parent: child does not appear at top level", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "card", type: "Card", props: {} },
      { id: "txt", type: "Text", parent: "card", props: {} },
    ]);
    const topIds = out.map((n) => n.id);
    expect(topIds).toEqual(["card"]);
    const allIds: string[] = [];
    function walk(nodes: typeof out) {
      for (const n of nodes) {
        allIds.push(n.id);
        if (n.children) walk(n.children);
      }
    }
    walk(out);
    expect(allIds).toEqual(["card", "txt"]);
  });

  it("never double-renders: a props.children child does not also appear at top level", () => {
    const out = a2uiToReactAdapterNodes([
      {
        id: "card",
        type: "Card",
        props: { children: [{ id: "txt", type: "Text", props: {} }] },
      },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].children?.[0].id).toBe("txt");
  });

  it("component field defaults to type when absent", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "a", type: "Card", props: {} },
    ]);
    expect(out[0].component).toBe("Card");
  });

  it("originalType field defaults to type when absent", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "a", type: "Spacer", props: {} },
    ]);
    expect(out[0].originalType).toBe("Spacer");
  });

  it("preserves explicit component field over type field", () => {
    const out = a2uiToReactAdapterNodes([
      { id: "a", type: "card", component: "Card", props: {} },
    ]);
    expect(out[0].component).toBe("Card");
  });
});
