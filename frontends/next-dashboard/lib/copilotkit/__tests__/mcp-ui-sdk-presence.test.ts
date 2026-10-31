/**
 * mcp-ui SDK presence canary (lo1g9.1).
 *
 * Fails fast if a future bump of `@mcp-ui/client` removes or renames
 * the `UIResourceRenderer` named export — the dispatcher entrypoint
 * cited by meta-architect verdict `26d6cd24-b165-4481-96ee-6a010277f22d`.
 *
 * Pinned version: `@mcp-ui/[email protected]` (see frontends/next-dashboard/package.json).
 * Dispatcher source: `node_modules/@mcp-ui/client/dist/index.mjs`
 * (re-exports `UIResourceRenderer` which fans out internally to
 *  HTMLResourceRenderer / RemoteDOMResourceRenderer by `mimeType`).
 */

import { describe, it, expect } from "vitest";
import * as mcpUi from "@mcp-ui/client";

describe("mcp-ui SDK presence canary", () => {
  it("exposes UIResourceRenderer", () => {
    expect(mcpUi.UIResourceRenderer).toBeDefined();
    expect(typeof mcpUi.UIResourceRenderer).toBe("function");
  });
});
