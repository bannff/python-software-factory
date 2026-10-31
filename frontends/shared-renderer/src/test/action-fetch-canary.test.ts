/**
 * Grep canary for the bd:372an regression.
 *
 * ANTI-DRIFT CONDITION 3. `ButtonRenderer` and `FormRenderer` used to call
 * `fetch("/api/tools/${tool}")` directly, bypassing the `BridgeAdapter` seam
 * that every other renderer hook honours — no envelope, no correlation, no
 * transcript entry, errors swallowed. That is the exact shape this test
 * forbids from ever reappearing anywhere in the package.
 *
 * A static assertion rather than a behavioural one on purpose: the failure
 * mode is a NEW renderer hardcoding a transport, which no behavioural test of
 * the existing renderers would catch.
 */
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

// vitest runs from the package root; jsdom rewrites `import.meta.url` to an
// http:// URL, so resolve from cwd instead.
const SRC = join(process.cwd(), "src");

/** The renderer package must not name an HTTP transport. */
const FORBIDDEN: { pattern: RegExp; why: string }[] = [
  {
    pattern: /fetch\s*\(\s*[`'"]\/api\/tools/,
    why: "raw fetch at the tool gateway — route through useBridge/useAction (bd:372an)",
  },
  {
    pattern: /fetch\s*\(\s*[`'"]\/api\//,
    why: "raw fetch at the API — the package must not know the transport (tenet 2/6)",
  },
];

/**
 * Strip comments before matching. The renderers document the pattern they
 * removed ("this used to fetch(...)"), and a canary that trips on its own
 * changelog is a canary nobody keeps.
 */
function stripComments(body: string): string {
  return body.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe("shared-renderer transport canary (bd:python-factory-372an)", () => {
  const files = walk(SRC).filter((f) => !f.endsWith("action-fetch-canary.test.ts"));

  it("finds source files to scan", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it("contains no raw fetch to the tool gateway", () => {
    const hits: string[] = [];
    for (const file of files) {
      const body = stripComments(readFileSync(file, "utf8"));
      for (const { pattern, why } of FORBIDDEN) {
        if (pattern.test(body)) hits.push(`${relative(SRC, file)}: ${why}`);
      }
    }
    expect(hits, `forbidden transport usage:\n${hits.join("\n")}`).toEqual([]);
  });

  it("the canary would catch the original bd:372an code", () => {
    const original = 'if (tool) await fetch(`/api/tools/${tool}`, { method: "POST" });';
    expect(FORBIDDEN.some(({ pattern }) => pattern.test(stripComments(original)))).toBe(true);
  });

  it("keeps the renderers that regressed wired to the action dispatcher", () => {
    for (const name of ["renderers/renderers-basic.tsx", "renderers/renderers-interactive.tsx"]) {
      const body = stripComments(readFileSync(join(SRC, name), "utf8"));
      expect(body, `${name} must dispatch via useAction`).toContain("useAction");
      expect(body, `${name} must not call fetch`).not.toMatch(/\bfetch\s*\(/);
    }
  });
});
