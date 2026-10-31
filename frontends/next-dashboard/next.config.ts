import type { NextConfig } from "next";
import path from "node:path";
import { buildSecurityHeaders } from "./lib/security/csp";

const SPA_VIEWS = ["graph", "timeline", "findings", "evals", "metrics", "ml"];

/**
 * Loopback spellings a browser, driver or bookmark may use for this dev server.
 *
 * Next blocks cross-origin `/ _next/*` and WebSocket (HMR) dev traffic unless
 * the requesting host is allowlisted (`next/dist/server/lib/router-utils/
 * block-cross-site-dev.js`); its built-in list covers `localhost` and
 * `**.localhost` only. A page served over `127.0.0.1` is therefore a
 * cross-origin request to the *same* server: the HMR socket is rejected, the
 * dev debug channel never settles, React skips `hydrateRoot` and the dashboard
 * stays on a dead "Connecting to tools…" composer with zero `/mcp` traffic and
 * no console error (GH #142). These literals are the loopback aliases a local
 * launch actually advertises — never a wildcard, never a LAN host.
 */
export const LOOPBACK_DEV_ORIGINS = ["127.0.0.1", "[::1]"];

/**
 * Next.js host config.
 *
 * - `allowedDevOrigins` is dev-only in Next itself (the guard lives on the dev
 *   request path), so listing loopback aliases cannot widen production CORS.
 * - `redirects()` collapses legacy SPA paths onto `/`.
 * - `headers()` ships companion security headers. CSP is generated once per
 *   document request by `middleware.ts`, which injects a nonce and forwards it
 *   to the App Router.
 */
const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: LOOPBACK_DEV_ORIGINS,
  // `next dev` otherwise writes AGENTS.md + CLAUDE.md into this directory on
  // every start (agentRules defaults to true and they are not gitignored,
  // which dirties the tree). This repo ships its own AGENTS.md convention.
  agentRules: false,
  transpilePackages: ["@companion-x/shared-renderer"],
  // Next copies this value into `outputFileTracingRoot`, so it decides the
  // standalone layout. Anchor it on the directory holding both this app and the
  // linked `../shared-renderer` package, via `__dirname` rather than
  // `process.cwd()`, so the emitted layout (`.next/standalone/next-dashboard/`)
  // is identical locally and under the Docker builder's `/app/next-dashboard`.
  turbopack: { root: path.resolve(__dirname, "..") },
  async redirects() {
    return SPA_VIEWS.map((v) => ({
      source: `/${v}`,
      destination: "/",
      permanent: false,
    }));
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: buildSecurityHeaders(),
      },
    ];
  },
};

export default nextConfig;
