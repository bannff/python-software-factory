import type { BridgeAdapter } from "@companion-x/shared-renderer";
import { callTool } from "@/lib/api";

/**
 * NextBridgeAdapter — the Next dashboard's {@link BridgeAdapter}
 * implementation (Track 6, bd:python-factory-ons71).
 *
 * Thin wrapper over the existing `@/lib/api` `callTool`, which POSTs to
 * the gateway via the Next.js rewrites. The shared renderer hooks own
 * the `res.result ?? res` envelope unwrap, so this stays a pass-through.
 *
 * `callTool` is an arrow property (bound) so it survives being read off
 * the adapter without losing `this` — defensive even though the impl
 * doesn't reference instance state today.
 */
export class NextBridgeAdapter implements BridgeAdapter {
  callTool = (name: string, args: Record<string, unknown> = {}): Promise<unknown> =>
    callTool(name, args);
}
