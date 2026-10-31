import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { scanBundledReactVersions } from "./react-runtime-guard";

/**
 * Single-React-runtime guard (#47).
 *
 * `@mcp-ui/client@5.6.2` declares `react`/`react-dom` as direct dependencies
 * and `@remote-dom/react` peers on `^17 || ^18`, so the installed tree carries
 * a nested React 18 renderer next to the app's React 19. Today Turbopack
 * dedupes the app to one runtime and the nested copy never reaches a chunk —
 * but that is a bundler default, not a repo guarantee, and a React 18 renderer
 * under React 19 crashes with error #525 the moment it renders.
 *
 * This guard pins the user-visible half of the invariant: the built output
 * must declare exactly one React version and carry no React-18 renderer
 * marker. Scope note: it counts distinct `version` markers, so it catches a
 * React 18 renderer or a second 19.x minor, but a byte-identical second copy
 * of the same build is not distinguishable by this check.
 * `ci.yml` runs `npm run build` before `npm test`, so it is enforced there; a
 * local `npm test` without a build skips the built-output half.
 */

const NEXT_ROOT = path.resolve(__dirname, "..", "..", ".next");
const BUILT_CHUNK_DIRS = ["static/chunks", "server/chunks"].map((dir) =>
  path.join(NEXT_ROOT, dir),
);
const builtDirs = BUILT_CHUNK_DIRS.filter((dir) => existsSync(dir));

describe("single React runtime in the built app", () => {
  it("detects a React 18 renderer emitted into a chunk", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "react-runtime-guard-"));
    try {
      writeFileSync(
        path.join(dir, "chunk.js"),
        'var e={};e.createElement=function(){};e.version="18.3.1";',
      );
      expect(scanBundledReactVersions(dir)).toEqual(["18.3.1"]);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("ships one React version and no React-18 renderer marker", () => {
    expect(
      builtDirs.length > 0 || !process.env.CI,
      "no .next build output — run `npm run build` before this guard",
    ).toBe(true);
    if (builtDirs.length === 0) return;

    const versions = [...new Set(builtDirs.flatMap(scanBundledReactVersions))];
    expect(versions.filter((version) => version.startsWith("18."))).toEqual([]);
    expect(versions.filter((version) => version.startsWith("19."))).toHaveLength(1);
  });
});
