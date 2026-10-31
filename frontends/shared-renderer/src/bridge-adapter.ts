/**
 * BridgeAdapter — the framework-agnostic data seam for the shared
 * renderer (Track 6, bd:python-factory-ons71).
 *
 * The renderer package never imports a concrete transport. Every MCP
 * tool call routes through this single interface, supplied by the host
 * via {@link BridgeAdapterProvider}. The Next dashboard wraps its
 * `@/lib/api` `callTool` (NextBridgeAdapter).
 *
 * `callTool` returns `Promise<unknown>` — the renderer hooks own the
 * envelope unwrap (`res.result ?? res`), so the adapter stays a thin
 * pass-through with zero knowledge of the gateway response shape.
 */
export interface BridgeAdapter {
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
}
