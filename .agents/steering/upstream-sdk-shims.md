# Upstream SDK Shims & Dispatcher Pins

Canonical reference for local SDK shims, their upstream gaps, sunset triggers, and pinned third-party FE SDK dispatcher sources.

## Active upstream PRs we're watching

Local SDK shims follow the SDK-First "build it but document the gap" clause from `.agents/steering/dev-principles.md`: cite the upstream gap, ship the local fix, pin the SDK shape with a canary, and name the deletion trigger.

| Shim | Upstream issue / PR | Sunset trigger | Downstream consumers |
|---|---|---|---|
| `FactoryMCPClient` (`components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py`, bd:python-factory-nmzlk) — overrides Strands 1.50.2's public `MCPClient.map_mcp_content_to_tool_result_content` extension point to preserve `EmbeddedResource.uri+mimeType` through flattening | strands-agents/sdk-python issue [#2251](https://github.com/strands-agents/sdk-python/issues/2251) / PR [#2370](https://github.com/strands-agents/sdk-python/pull/2370) promoted the mapper to a public seam but did not address the data drop. Local upstream behavior fix: bd:python-factory-0g0gg | Upstream Strands lands real preservation → bump exact pin → delete `strands_mcp_client_factory.py` + canary + restore plain `MCPClient` in `strands_mcp_graph.create_mcp_client` | Carrier #5 (`@mcp-ui/[email protected]`) — forwarded `EmbeddedResource` blocks reach `<McpUiFrame>` via the flat `{text\|image, uri, mimeType}` shape. The `_handle_tool_result` regression test pins dispatch through the public mapper. |

## Pinned third-party FE SDK dispatcher sources

Per the SDK-First "dispatcher source rule" in `.agents/steering/dev-principles.md`: any code that wraps a third-party FE SDK with a dispatcher MUST cite the dispatcher source path + version pin. The five carriers in `.agents/steering/a2ui-protocol.md` are the live consumers of these sources.

`@mcp-ui/[email protected]` — `frontends/next-dashboard/node_modules/@mcp-ui/client/dist/index.mjs` (carrier #5):

| Line | Description |
|---|---|
| `:21-22` | Strict-equality MIME check on `text/html` + `text/uri-list` — rejects RFC 7231 params; consumer normalizes at `mcp-ui-validator.ts` (preserve `framework=react` for RemoteDOM only) |
| `:175` | `postMessage` source-window equality (SDK's only check). We layer Zod + tool/intent allowlist on top in `mcp-ui-validator.ts` |
| `:223` | `srcDoc` iframe `allow-scripts` for `inline_html` mode |
| `:234` | External_url SDK default `sandbox="allow-scripts allow-same-origin"` — `<McpUiFrame>` overrides to `allow-scripts` only (drops `allow-same-origin`); pinned by vitest snapshot |
| `:2754` | RemoteDOM `allow-scripts` + `display:none` host iframe |
| `:2762-2774` | `<UIResourceRenderer>` mode dispatch by `resource.mimeType` (`text/html` → rawHtml; `text/uri-list` → externalUrl; `application/vnd.mcp-ui.remote-dom*` → remoteDom) |

## CSP env-gate

The carrier #5 host CSP at `frontends/next-dashboard/lib/security/csp.ts` is env-gated, not a single static directive set. Cite the env-aware shape, not a fixed string, when wiring or reviewing it:

- **Production** (`NODE_ENV === "production"`, `csp.ts:88-89`): `script-src 'self' 'wasm-unsafe-eval'` — strict, unchanged from security-engineer verdict `d580bfdd` §3.
- **Development** (`csp.ts:88-90`): `script-src` adds `'unsafe-inline' 'unsafe-eval'` so Next.js App Router RSC streaming chunks (`__next_f.push([1, "..."])`) + React Refresh `new Function()` boot React. `connect-src` widens to `ws: http:` for HMR + absolute-URL `/health` polling.

Bridge fix only — qa verdict `e7f73978`, retro security verdict `dd49f85b`. Long-term replacement is a middleware-injected per-request nonce + `'strict-dynamic'` (TODO at `csp.ts:54-56`); when that lands, dev matches prod without the escape hatch and this section gets retired. Carrier #5 security layer 2 in `.agents/steering/a2ui-protocol.md` mirrors this note.
