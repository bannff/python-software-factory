/**
 * Catalog ranking + active-brick resolution for the ⌘K palette (bd:3jcls.4).
 *
 * The active-brick ordering test is a regression pin from driving the palette
 * in a real browser: with a HARD brick bucket, typing `cacheset` on the ML tab
 * ranked `machine_learning_ml_sample_timeseries` (a scattered hit in its
 * description) above `cache_set` (a near-exact name hit). Brick membership must
 * bias the order, not override match quality.
 */

import { describe, expect, it } from "vitest";
import fixture from "./fixtures/real-tool-schemas.json";
import {
  activeBrickFor, fuzzyScore, rankTools, type CatalogTool, type ToolCatalog,
} from "@/lib/tool-catalog";

const REAL = fixture.tools as unknown as CatalogTool[];

function tool(brick: string, name: string, description = ""): CatalogTool {
  return {
    brick, name, qualified_name: name, description,
    input_schema: {}, category: "operational",
  };
}

describe("fuzzyScore", () => {
  it("matches subsequences and rejects non-matches", () => {
    expect(fuzzyScore("graph_get_findings", "gfind")).not.toBeNull();
    expect(fuzzyScore("cache_set", "cacheset")).not.toBeNull();
    expect(fuzzyScore("cache_set", "zzz")).toBeNull();
  });

  it("scores a contiguous prefix better than a scattered match", () => {
    const contiguous = fuzzyScore("cache_set", "cache")!;
    const scattered = fuzzyScore("configure_and_cache_settings", "cache")!;
    expect(contiguous).toBeLessThan(scattered);
  });

  it("treats an empty query as a tie", () => {
    expect(fuzzyScore("anything", "")).toBe(0);
  });
});

describe("rankTools", () => {
  const tools = [
    tool("cache", "cache_set", "Set a value in cache with optional TTL."),
    tool("machine_learning", "ml_sample_timeseries", "Generate synthetic windows."),
    tool("machine_learning", "ml_train", "Train a model."),
    tool("evals", "evals_run_suite", "Run an eval suite."),
  ];

  it("puts the active brick first when nothing is typed", () => {
    const ordered = rankTools(tools, "", "machine_learning");
    expect(ordered.slice(0, 2).map((t) => t.brick)).toEqual([
      "machine_learning", "machine_learning",
    ]);
    expect(ordered).toHaveLength(4); // the rest is not hidden
  });

  it("lets a strong match elsewhere beat a weak active-brick match", () => {
    // Regression pin — see file header.
    const ordered = rankTools(tools, "cacheset", "machine_learning");
    expect(ordered[0].qualified_name).toBe("cache_set");
  });

  it("breaks score ties toward the active brick", () => {
    const ordered = rankTools(tools, "ml_", "machine_learning");
    expect(ordered[0].brick).toBe("machine_learning");
  });

  it("filters out non-matches entirely", () => {
    expect(rankTools(tools, "zzzqqq", null)).toEqual([]);
  });

  it("ranks by the entry's own brick field, with no brick table", () => {
    // A brick nobody has ever heard of still gets promoted when it is active.
    const exotic = [...tools, tool("brand_new_brick", "bnb_do_thing", "New.")];
    expect(rankTools(exotic, "", "brand_new_brick")[0].brick).toBe("brand_new_brick");
  });

  it("orders real catalog entries deterministically", () => {
    const ordered = rankTools(REAL, "cache", "cache").map((t) => t.qualified_name);
    expect(ordered[0]).toBe("cache_keys"); // shortest contiguous hit
    expect(ordered).toContain("cache_set");
  });
});

describe("activeBrickFor", () => {
  const catalog = {
    bricks_loaded: ["cache", "machine_learning", "evals"],
    aliases: { ml: "machine_learning" },
  } as unknown as ToolCatalog;

  it("resolves a view id straight through when it is a brick", () => {
    expect(activeBrickFor("evals", catalog)).toBe("evals");
  });

  it("resolves via the SERVER-shipped alias table, not a local literal", () => {
    expect(activeBrickFor("ml", catalog)).toBe("machine_learning");
  });

  it("returns null for a view with no brick behind it", () => {
    expect(activeBrickFor("welcome", catalog)).toBeNull();
    expect(activeBrickFor(undefined, catalog)).toBeNull();
  });
});
