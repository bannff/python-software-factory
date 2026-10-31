import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "connections-view.tsx"), "utf-8");

/**
 * Item 5 (owner smoke #2, P1 BLOCK #2): "Connections list loses its
 * scrollbar and its entries when scrolled far down." Root cause: the list
 * had its own `max-h-[31rem] overflow-y-auto` cap while ALSO living inside
 * the Agent Capabilities tabpanel's own scroll container — two competing
 * scroll boundaries, and the outer one won, silently clipping rows below
 * the fold. Verified end-to-end in a real browser (44 registered bricks,
 * scrolled to the last entry, `workflow`, fully reachable) — this is a
 * fast regression guard against the exact height-cap class returning.
 */
describe("ConnectionsView list container (item 5 fix)", () => {
  it("does not re-introduce a competing max-h scroll cap on the brick list", () => {
    expect(source).not.toMatch(/max-h-\[31rem\]/);
  });

  it("the brick list is a plain flow container, not a self-scrolling region", () => {
    const listContainerLine = source.split("\n").find((line) => line.includes("rows.map((brick)"));
    expect(listContainerLine).toBeTruthy();
    expect(listContainerLine).not.toMatch(/overflow-y-auto/);
  });
});
