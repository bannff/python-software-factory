/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Minimal Vitest setup to host CopilotKit / AG-UI dispatcher canaries
 * (bd-f2h9, regression pin for bd-115z). Existing `*.test.ts` files in
 * `lib/` use the `node:test` runner and live outside this glob, so this
 * config does not disturb them.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: "@", replacement: path.resolve(__dirname, ".") },
      // bd-pws3: Force CJS resolution for `@ag-ui/client` so the
      // namespace import `import * as a from "fast-json-patch"` in
      // `dist/index.mjs` resolves `a.applyPatch` correctly. Under
      // ESM the namespace exposes only the named exports while
      // `applyPatch` lives on the default export object — Next.js's
      // CJS-shaped bundler hides this divergence in production but
      // vitest's strict ESM loader does not. The CJS build assigns
      // the default object's methods on the namespace, matching what
      // production sees. Without this alias the STATE_DELTA canary
      // sees `Failed to apply state patch: a.applyPatch is not a
      // function` and silently swallows the patch.
      {
        find: "@ag-ui/client",
        replacement: path.resolve(
          __dirname, "node_modules/@ag-ui/client/dist/index.js",
        ),
      },
      // bd:python-factory-eyahj: `@mcp-ui/[email protected]` declares
      // `react@^18.3.1` as a direct dep so npm installs a nested
      // copy under `node_modules/@mcp-ui/client/node_modules/react`.
      // Vitest's strict ESM loader resolves the SDK's
      // `react/jsx-runtime` import against that 18.x nested copy
      // while the host page uses top-level react@19 — React 19
      // detects the mismatch via its `throwOnInvalidObjectType`
      // path and crashes the renderer with "A React Element from
      // an older version of React was rendered." Force every
      // `react` / `react-dom` / `react/jsx-runtime` import to the
      // top-level workspace copy so the SDK and host share one
      // module graph. Next.js production bundling already dedupes
      // via webpack's resolve order; vitest needs explicit aliases
      // ordered before the bare-`react` rule to match the
      // sub-paths first.
      {
        find: /^react\/jsx-runtime$/,
        replacement: path.resolve(__dirname, "node_modules/react/jsx-runtime.js"),
      },
      {
        find: /^react\/jsx-dev-runtime$/,
        replacement: path.resolve(
          __dirname, "node_modules/react/jsx-dev-runtime.js",
        ),
      },
      { find: /^react-dom$/, replacement: path.resolve(__dirname, "node_modules/react-dom") },
      { find: /^react$/, replacement: path.resolve(__dirname, "node_modules/react") },
    ],
    dedupe: ["react", "react-dom", "react/jsx-runtime"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["**/__tests__/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "e2e/**"],
    css: false,
    server: {
      deps: {
        // Stub CSS imports inside CopilotKit / markdown deps which load
        // raw `.css` files (e.g. katex.min.css) that vitest can't parse.
        // Also inline `@mcp-ui/client` so the resolve.alias rules above
        // (forcing react→top-level workspace copy) actually fire on
        // its `import { jsx } from "react/jsx-runtime"` — without
        // inlining the SDK is loaded directly from node_modules and
        // vite skips alias resolution. bd:python-factory-eyahj.
        inline: [
          /@copilotkit/,
          /katex/,
          /react-markdown/,
          /@mcp-ui/,
        ],
      },
    },
  },
});
