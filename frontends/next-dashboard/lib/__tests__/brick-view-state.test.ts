import { describe, expect, it } from "vitest";
import { normalizeBrickViews, resolveBrickViewId } from "@/lib/brick-view-state";

const views = [
  { id: "overview", name: "Overview" },
  { id: "models", name: "Models" },
  { id: "lineage", name: "Lineage" },
];

describe("brick view state", () => {
  it("retains a valid selected id instead of reapplying viewIndex", () => {
    expect(resolveBrickViewId(views, "lineage", 0)).toBe("lineage");
  });

  it("falls back deterministically when a selected id is stale", () => {
    expect(resolveBrickViewId(views, "removed", 1)).toBe("models");
    expect(resolveBrickViewId(views, "removed", 99)).toBe("lineage");
  });

  it("keeps first occurrence metadata order and removes duplicate ids", () => {
    expect(normalizeBrickViews([...views, { id: "models", name: "Duplicate" }]))
      .toEqual(views);
  });

  it("preserves the only view", () => {
    expect(resolveBrickViewId([views[0]], undefined, 7)).toBe("overview");
  });
});
