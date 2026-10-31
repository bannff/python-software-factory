/**
 * Single source of truth for the Companion-X agent identity (bd:python-factory-sopw).
 *
 * The agent ID crosses the Next.js boundary: the server-side runtime route
 * (`app/api/copilotkit/[[...path]]/route.ts`) registers the agent with
 * `CopilotRuntime`, and the client-side provider (`lib/copilotkit/provider.tsx`)
 * registers it via `selfManagedAgents` so the same identifier wires up both
 * sides. Importing the constant from here drift-proofs the pair.
 *
 * SDK-First citation:
 * - `@copilotkitnext/[email protected]` `CopilotKitProvider.mjs:30` accepts
 *   `selfManagedAgents` (alias of `agents__unsafe_dev_only`); both merge into
 *   `mergedAgents` and feed `agentRegistry.initialize` synchronously
 *   (`@copilotkitnext/core` `index.mjs:170-182`). `processAgentsChanged` runs
 *   on the inspector's `attachToCore` initial pass with the agent already
 *   present (`@copilotkitnext/[email protected]` `index.mjs:404-405`).
 *
 * Why local registration (not just `runtimeUrl`):
 * The `runtimeUrl`-only path relies on an async `/info` handshake to populate
 * `core.agents.companion_x`. Empirically (Playwright-verified) the inspector's
 * `attachToCore` does not reliably wire its agent subscription on initial
 * `core` assignment from the React wrapper, leaving the AG-UI Events / Agent /
 * State tabs empty. Registering here populates `core.agents` synchronously at
 * construction, so the inspector subscribes via the same code path the chat
 * agent uses (`useAgent` resolves `core.getAgent("companion_x")` first).
 *
 * The `HttpAgent` URL points at the Hono runtime route (NOT directly at the
 * Python `/ag-ui/run`) so middleware logging in
 * `lib/copilotkit/middleware/logging.ts` continues to fire.
 */

import { HttpAgent } from "@ag-ui/client";

/** Agent ID shared by FE provider registration and BE runtime registration. */
export const COMPANION_X_AGENT_ID = "companion_x";

/**
 * Hono runtime route the FE talks to. Hono proxies to the Python `/ag-ui/run`
 * endpoint via the registered server-side `HttpAgent` in
 * `app/api/copilotkit/[[...path]]/route.ts`.
 */
const COMPANION_X_RUNTIME_PATH = `/api/copilotkit/agent/${COMPANION_X_AGENT_ID}/run`;

/**
 * Build a fresh `HttpAgent` bound to the Companion-X runtime route.
 *
 * Returned as a factory (not a module-level singleton) so the provider can
 * call it inside its render lifecycle without server-side import-time side
 * effects (Next.js 15 + React 19 SSR). The provider memoises the result.
 */
export function createCompanionXAgent(): HttpAgent {
  return new HttpAgent({ url: COMPANION_X_RUNTIME_PATH });
}
