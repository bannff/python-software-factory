import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "canvas.tsx"), "utf-8");

/**
 * Real live bug (item 5 recurrence, owner smoke #2, P1 BLOCK #2): the
 * Connections tab's scrollbar was reported fixed by an earlier `min-h-0`
 * added to `app/layout.tsx`'s `<main>` — but that fix alone was
 * insufficient at real viewport heights. Root cause traced by direct DOM
 * inspection through the full ancestor chain: `Canvas`'s own top-level flex
 * column (`<div className="flex flex-1 flex-col min-w-0">`, the shared
 * wrapper rendered for EVERY tab, not just Connections) had NO `min-h-0`.
 * A flex item's default `min-height: auto` refuses to shrink below its
 * own content size, so this one div silently grew to fit its tallest
 * child's full content height (2906px at repro conditions) instead of
 * respecting the `flex-1` sizing the rest of the shell chain correctly
 * set up — breaking the height-clamp chain for every tab, and making
 * `main`'s intentional `overflow-hidden` clip content with no scrollbar
 * anywhere upstream of it. Verified live: before the fix the outer scroll
 * boundary's `scrollHeight === clientHeight` (not actually overflowing,
 * so no scrollbar ever appears); after adding `min-h-0` here, the SAME
 * outer boundary correctly overflows and scrolling reaches the last of 44
 * registered bricks. `connections-view.tsx` itself needed NO change — this
 * is the one place the fix belongs, and it fixes every tab at once.
 */
describe("Canvas top-level wrapper (min-h-0 clamp chain)", () => {
  it("keeps min-h-0 on its own top-level flex column so height clamps propagate to every tab", () => {
    const wrapperLine = source.split("\n").find((line) => line.includes("flex-1 flex-col min-w-0"));
    expect(wrapperLine).toBeTruthy();
    expect(wrapperLine).toMatch(/min-h-0/);
  });
});
