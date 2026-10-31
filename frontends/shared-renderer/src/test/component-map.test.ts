/**
 * Tests for ``getRenderer`` (bd:python-factory-3hkqx round 3).
 *
 * Pin the case + underscore-insensitive lookup. Mirrors the BE
 * ``paint_canvas.py:_norm`` rule. Meta-architect verdict
 * ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q6 T6.
 */

import { describe, expect, it } from "vitest";
import { getRenderer, COMPONENT_MAP } from "../renderers/component-map";

describe("getRenderer (bd:python-factory-3hkqx)", () => {
  it("PascalCase canonical resolves", () => {
    expect(getRenderer("Card")).toBe(COMPONENT_MAP.Card);
    expect(getRenderer("ItemList")).toBe(COMPONENT_MAP.ItemList);
    expect(getRenderer("Sparkline")).toBe(COMPONENT_MAP.Sparkline);
  });

  it("lowercase resolves to same renderer as PascalCase", () => {
    expect(getRenderer("card")).toBe(COMPONENT_MAP.Card);
    expect(getRenderer("text")).toBe(COMPONENT_MAP.Text);
  });

  it("underscore aliases resolve (item_list, status_dot, etc)", () => {
    expect(getRenderer("item_list")).toBe(COMPONENT_MAP.ItemList);
    expect(getRenderer("status_dot")).toBe(COMPONENT_MAP.StatusDot);
    expect(getRenderer("trend_badge")).toBe(COMPONENT_MAP.TrendBadge);
  });

  it("mixed casing + underscores all resolve to the canonical entry", () => {
    expect(getRenderer("Item_List")).toBe(COMPONENT_MAP.ItemList);
    expect(getRenderer("ITEMLIST")).toBe(COMPONENT_MAP.ItemList);
    expect(getRenderer("itemlist")).toBe(COMPONENT_MAP.ItemList);
  });

  it("Spacer and Divider have proper renderers (not Fallback)", () => {
    expect(getRenderer("Spacer")).toBeDefined();
    expect(getRenderer("Spacer")).toBe(COMPONENT_MAP.Spacer);
    expect(getRenderer("Divider")).toBeDefined();
    expect(getRenderer("Divider")).toBe(COMPONENT_MAP.Divider);
  });

  it("returns null for unknown names", () => {
    expect(getRenderer("UnknownThing")).toBeNull();
    expect(getRenderer("hello-heading")).toBeNull();
  });

  it("returns null for empty / undefined", () => {
    expect(getRenderer(undefined)).toBeNull();
    expect(getRenderer("")).toBeNull();
  });

  it("all 24 BE catalog types resolve (parity)", () => {
    // Mirror of the BE COMPONENT_CATALOG keys.
    const catalog = [
      "Card", "Text", "Button", "Form", "TextField", "Select",
      "DatePicker", "TimePicker", "Image", "List", "Table", "Chart",
      "Alert", "Progress", "Metric", "Lineage", "Divider", "Spacer", "ItemList",
      "StatusDot", "TrendBadge", "Sparkline", "DetailPanel", "FilterBar",
    ];
    const missing: string[] = [];
    for (const t of catalog) {
      if (getRenderer(t) === null) missing.push(t);
    }
    expect(missing).toEqual([]);
  });
});
