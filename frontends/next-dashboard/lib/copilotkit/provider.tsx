"use client";

import { useMemo } from "react";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { BridgeAdapterProvider } from "@companion-x/shared-renderer";
import "@copilotkit/react-core/v2/styles.css";
import "./inspector.css";
import { ToolRenderers } from "./tool-renderers";
import { CanvasContextBridge } from "./canvas-context";
import { FrontendTools } from "./frontend-tools";
import { CanvasSuggestions } from "./canvas-suggestions";
import { NextBridgeAdapter } from "@/lib/next-bridge-adapter";
import { ActionTranscriptProvider } from "./action-transcript";
import { CommandPaletteMount } from "@/components/command/command-palette-mount";
import { McpConfirmationHost } from "@/components/mcp-confirmation-host";
import { McpQuestionHost } from "@/components/mcp-question-host";
// DISABLED bd-xpxa: registers FE tools with dotted MCP names (e.g. "sandbox.execute")
import { terminalActivityRenderer } from "./terminal-activity-renderer";
// which CopilotKit prefixes to "fe_sandbox.execute" in the AG-UI request.
// Bedrock Converse rejects the entire turn — toolSpec.name must match
// [a-zA-Z0-9_-]+. File a redesign before re-enabling. File kept on disk.
// import { DestructiveGuards } from "./destructive-guards";
import { AgentComponents } from "./agent-components";
import { COMPANION_X_AGENT_ID, createCompanionXAgent } from "./companion-agent";
import { InspectorAttachWorkaround } from "./inspector-attach-workaround";

interface CopilotProviderProps {
  children: React.ReactNode;
}

// Stable reference (per CopilotKit warning about non-stable arrays).
// bd:python-factory-esb6n: ALL sub-agent activity renderers remain removed.
// `terminal.command` is registered separately because command output has no
// duplicate containment surface.
// The sub-agent containment box (`sub-agent-group.tsx`) is now the single
// surface for every SYNC spawn (subagent / swarm / graph / registered),
// naming the run in its header ("Sub-agent · id" / "Swarm · N agents" /
// "Pipeline · …") and containing each node's reasoning + tool pills + prose.
//   - `singleSubagentActivityRenderer` (subagent.single) duplicated the box header.
//   - `swarmActivityRenderer` / `graphActivityRenderer` (subagent.swarm/.graph)
//     rendered a SECOND bare top-level card OUTSIDE the box (and with a buggy
//     agent_count=0), co-mingling with the coordinator — exactly what the
//     containment goal forbids. The activity message id `subagent:<tcid>`
//     arrives BEFORE the spawn anchor in the stream, so it cannot be pulled
//     into the box positionally. meta-architect verdict 298d1bb2 (supersedes
//     60d5af60). Per-node status (pending/running/failed/handoff) will be
//     re-introduced INSIDE the box under bd:python-factory-8q8da; NodeSchema /
//     NodeRowList are kept on disk in subagent-activity-renderer.tsx for reuse.
// Sub-agent activity renderers remain parked to avoid duplicate containment cards.
// Terminal activity is distinct and renders one command/output card.
const ACTIVITY_RENDERERS = [terminalActivityRenderer];

/**
 * CopilotKit v2 provider — wraps the app and connects to our AG-UI
 * backend via the /api/copilotkit runtime route.
 *
 * v2 dropped the provider-level `agent` / `enableInspector` props.
 * Agent binding moves down onto `<CopilotChat agentId="…">`. The dev
 * inspector is gated on `showDevConsole` (true / "auto" / false).
 * "auto" enables it on localhost only — which is exactly what the
 * status-bar diamond reparenter wants.
 *
 * `selfManagedAgents` (bd:python-factory-sopw): registers the
 * `companion_x` agent locally so `core.agents` is populated
 * synchronously at construction. Without this, the web-inspector's
 * AG-UI Events / Agent / State tabs stay empty because its
 * `attachToCore` does not reliably wire agent subscriptions on initial
 * `core` assignment via the React wrapper. Cite:
 * `@copilotkitnext/[email protected]` `CopilotKitProvider.mjs:30` (prop
 * accepted), `core/index.mjs:170-182` (synchronous `initialize`),
 * `web-inspector/index.mjs:404-405` (`processAgentsChanged` runs on
 * the initial `attachToCore` pass). Verdicts: meta-architect +
 * strands-expert APPROVE.
 *
 * NO `runtimeUrl` PROP — IMPORTANT (bd:python-factory-sopw shadow fix):
 * Setting `runtimeUrl` triggers the async `/info` handshake which
 * builds a `ProxiedCopilotRuntimeAgent` for `companion_x` and SHADOWS
 * our locally-registered `HttpAgent` via the merge order in
 * `core/index.mjs::updateRuntimeConnection` (`{...localAgents,
 * ...remoteAgents}` — remote spreads last and overrides). Empirically
 * verified: with both props set, `core.agents.companion_x.constructor.name`
 * resolves to `ProxiedCopilotRuntimeAgent`, not `HttpAgent`, and the
 * inspector's subscription stays at the wrong instance.
 *
 * The `HttpAgent` we register already carries its own URL pointing at
 * `/api/copilotkit/agent/companion_x/run`, which the Hono route in
 * `app/api/copilotkit/[[...path]]/route.ts` handles end-to-end. Dropping
 * `runtimeUrl` keeps the runtime-status badge at "Disconnected"
 * (cosmetic — there's no remote runtime to be connected to) but
 * eliminates the shadow.
 *
 * `renderActivityMessages` registers the Terminal activity renderer; parked
 * sub-agent renderers remain excluded to avoid duplicate containment cards.
 * ``@copilotkitnext/react/dist/hooks/use-render-activity-message.mjs``
 * matches each message by exact ``activityType`` (four-step chain:
 * agentId-bound exact → unbound exact → wildcard ``"*"`` → null).
 *
 * Companion children (registered as effects, render null):
 *   - <ToolRenderers />        per-tool + wildcard render hooks
 *   - <CanvasContextBridge />  pushes canvas state into agent context
 *   - <FrontendTools />        FE round-trip for fe_navigate_canvas
 *   - <CanvasSuggestions />    canvas-aware starter chips (bd-4y5d)
 *   - <DestructiveGuards />    HITL approval gates on destructive tools (bd-xpxa)
 *   - <AgentComponents />      typed components the agent can summon (bd-kzsl)
 */
export function CopilotProvider({ children }: CopilotProviderProps) {
  // Memoise the agent instance so the provider's stable-array check
  // does not see a fresh object on every render (CopilotKit logs a
  // warning otherwise).
  const selfManagedAgents = useMemo(
    () => ({ [COMPANION_X_AGENT_ID]: createCompanionXAgent() }),
    [],
  );

  // Stable BridgeAdapter for the shared renderer (Track 6). Memoised so
  // the provider value reference is stable across renders.
  const bridgeAdapter = useMemo(() => new NextBridgeAdapter(), []);

  return (
    <CopilotKitProvider
      selfManagedAgents={selfManagedAgents}
      showDevConsole="auto"
      renderActivityMessages={ACTIVITY_RENDERERS}
    >
      <BridgeAdapterProvider adapter={bridgeAdapter}>
        <ActionTranscriptProvider>
          <ToolRenderers />
          <CanvasContextBridge />
          <FrontendTools />
          <CanvasSuggestions />
          {/* <DestructiveGuards /> — DISABLED bd-xpxa: dotted tool names break Bedrock */}
          <AgentComponents />
          {/* bd:python-factory-sopw upstream workaround — see file header. */}
          <InspectorAttachWorkaround />
          {/* ⌘K palette (bd:3jcls.4). Renders null until summoned — zero
              persistent chrome. Inside the bridge + transcript providers so
              human-fired verbs share the agent's dispatch path. */}
          <CommandPaletteMount />
          {/* Direct MCP transport confirmation; deliberately outside AG-UI. */}
          <McpConfirmationHost />
          {/* Direct MCP multiple-choice question elicitation; same pattern. */}
          <McpQuestionHost />
          {children}
        </ActionTranscriptProvider>
      </BridgeAdapterProvider>
    </CopilotKitProvider>
  );
}
