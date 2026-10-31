"use client";

import { useState, useEffect, type ReactNode } from "react";
import { useDefaultRenderTool, useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";
import type { Message } from "@ag-ui/core";
import { InlineView } from "@/components/chat/inline-view";
import { McpUiFrame } from "@/components/chat/mcp-ui-frame";
import { ToolCallCard, parseResult } from "./tool-call-card";
import {
  useKbSearchRenderer,
  useCacheGetRenderer,
  useNavigateCanvasRenderer,
} from "./tool-renderer-hooks";
import {
  useInvokeGraphRenderer,
  useLaunchSwarmRenderer,
} from "./subagent-hooks";
import {
  useSpawnSubagentRenderer,
  useSpawnSwarmRenderer,
  useSpawnGraphRenderer,
  useSpawnRegisteredGraphRenderer,
  useSpawnSubagentAsyncRenderer,
} from "./spawn-hooks";
import { COMPANION_X_AGENT_ID } from "./companion-agent";
import {
  Bot,
  GitBranch,
  Network,
  Search,
  Brain,
  ShieldAlert,
  BarChart2,
  Zap,
  FlaskConical,
  BrainCircuit,
  Gamepad2,
  Link,
  Container,
  Workflow,
  LayoutTemplate,
  Database,
  Timer,
  Settings2,
  Bell,
  Cpu,
} from "lucide-react";

/**
 * Registers CopilotKit v2 tool renderers.
 *
 * - Per-tool hooks (in `tool-renderer-hooks.tsx`) render rich cards
 *   inside the shared <ToolCallCard> so chrome stays consistent.
 * - The wildcard registers a fallback that gives every uninstrumented
 *   tool the same Kiro-style collapsible card, computes a one-line
 *   preview from the result (bd-rx48 / D3), threads any A2UI component
 *   payload through <InlineView>, multiplexes mcp-ui UIResource
 *   payloads into <McpUiFrame> (carrier #5 — bd:python-factory-eyahj
 *   under EPIC python-factory-lo1g9; sandbox-overridden
 *   <UIResourceRenderer> from `@mcp-ui/[email protected]`), and lights up
 *   frontend (`fe_*`) tools in violet (bd-f849 / D4).
 *
 * Deferred to client-only via useMounted() to avoid hydration issues
 * during Next.js static page generation.
 */
export function ToolRenderers() {
  const mounted = useMounted();
  if (!mounted) return null;
  return <ToolRenderersInner />;
}

function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}

function ToolRenderersInner() {
  useKbSearchRenderer();
  useCacheGetRenderer();
  useNavigateCanvasRenderer(); // keeps wildcard from doubling fe_navigate_canvas
  useInvokeGraphRenderer();           // bd-71a0: sub-graph watch-live
  useLaunchSwarmRenderer();           // bd-71a0: swarm watch-live
  useSpawnSubagentRenderer();         // bd:b6z01: named card
  useSpawnSwarmRenderer();            // bd:b6z01: named card
  useSpawnGraphRenderer();            // bd:b6z01: named card
  useSpawnRegisteredGraphRenderer();  // bd:b6z01: named card
  useSpawnSubagentAsyncRenderer();    // bd:r3eqj: async live sub-window
  useCatchAllRenderer();
  return null;
}

/* ------------------------------------------------------------------ */
/*  Wildcard fallback for every other tool                             */
/* ------------------------------------------------------------------ */

/**
 * Carrier-discriminating wildcard renderer (bd:python-factory-r6kki,
 * EPIC python-factory-lo1g9). Multiplexes THREE shapes inside ONE
 * wildcard render function because the CopilotKit v2 dispatcher only
 * honors the FIRST wildcard match per agent.
 *
 * Dispatcher source pins (dev-principles.md "dispatcher source rule"):
 *   - First-wildcard-find behavior:
 *     `node_modules/@copilotkitnext/[email protected]/dist/hooks/use-render-tool-call.mjs:58`
 *     `renderToolCalls.find((rc) => rc.name === "*")` — only the first
 *     hit wins, so a second `useDefaultRenderTool` would be dead code.
 *   - Wildcard registration overwrite-by-key:
 *     `node_modules/@copilotkitnext/[email protected]/dist/hooks/use-render-tool.mjs:71-72`
 *     `mergedMap.set(\`${agentId ?? ""}:${name}\`, renderer)` — repeat
 *     registrations clobber, no stacking. Multiplexing must happen
 *     inside the single registered render function.
 *   - mcp-ui consumer (lands in lo1g9.4):
 *     `node_modules/@mcp-ui/[email protected]/dist/components/UIResourceRenderer.{tsx,js}`
 *     consumes `{type:"resource", resource:{uri, mimeType, text|blob}}`.
 *
 * Predicate ordering (per meta-architect verdict
 * `26d6cd24-b165-4481-96ee-6a010277f22d`): mcp-ui FIRST, A2UI SECOND.
 * mcp-ui is more specific (requires `ui://` URI scheme), so probing it
 * before A2UI's `Array.isArray(components)` keeps a payload that
 * accidentally carries both fields routed to the iframe consumer
 * rather than the inline component tree.
 *
 * Two mcp-ui shapes are accepted because Strands MCPClient flattens
 * `EmbeddedResource` content blocks. `FactoryMCPClient`
 * (bd:python-factory-nmzlk,
 * `components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py:114-178`)
 * preserves `uri` + `mimeType` on the flat dict, so both producers
 * reach the consumer:
 *   - Flow A (nested):  {type:"resource", resource:{uri, mimeType, text|blob}}
 *   - Flow B (flat):    {text|image, uri, mimeType}            ← Strands-side flatten
 */
/**
 * Per-prefix icon selector for the wildcard catch-all renderer
 * (bd:python-factory-b6z01). Keyed by tool-name prefix so every
 * uninstrumented tool gets a contextual icon without a named renderer.
 */
function getToolIcon(name: string): ReactNode | null {
  if (name.startsWith("graph_"))        return <Network className="h-3.5 w-3.5" />;
  if (name.startsWith("kb_"))           return <Search className="h-3.5 w-3.5" />;
  if (name.startsWith("memory_"))       return <Brain className="h-3.5 w-3.5" />;
  if (name.startsWith("security_"))     return <ShieldAlert className="h-3.5 w-3.5" />;
  if (name.startsWith("metrics_"))      return <BarChart2 className="h-3.5 w-3.5" />;
  if (name.startsWith("events_"))       return <Zap className="h-3.5 w-3.5" />;
  if (name.startsWith("spawn_"))        return <Bot className="h-3.5 w-3.5" />;
  if (name.startsWith("agent_"))        return <GitBranch className="h-3.5 w-3.5" />;
  if (name.startsWith("evals_"))        return <FlaskConical className="h-3.5 w-3.5" />;
  if (name.startsWith("ml_"))           return <BrainCircuit className="h-3.5 w-3.5" />;
  if (name.startsWith("games_"))        return <Gamepad2 className="h-3.5 w-3.5" />;
  if (name.startsWith("blockchain_"))   return <Link className="h-3.5 w-3.5" />;
  if (name.startsWith("sandbox_"))      return <Container className="h-3.5 w-3.5" />;
  if (name.startsWith("workflow_"))     return <Workflow className="h-3.5 w-3.5" />;
  if (name.startsWith("ui_"))           return <LayoutTemplate className="h-3.5 w-3.5" />;
  if (name.startsWith("storage_"))      return <Database className="h-3.5 w-3.5" />;
  if (name.startsWith("cache_"))        return <Timer className="h-3.5 w-3.5" />;
  if (name.startsWith("config_"))       return <Settings2 className="h-3.5 w-3.5" />;
  if (name.startsWith("notification_")) return <Bell className="h-3.5 w-3.5" />;
  if (name.startsWith("hardware_"))     return <Cpu className="h-3.5 w-3.5" />;
  // fe_* already gets MonitorCog via ToolCallCard's isFrontendTool branch
  return null;
}

function useCatchAllRenderer() {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });
  useDefaultRenderTool({
    render: ({ name, status, parameters, result }) => {
      const parsed = parseResult(result);
      return (
        <WildcardRender
          name={name}
          status={status}
          parameters={parameters}
          parsed={parsed}
          icon={getToolIcon(name)}
          messages={agent.messages}
        />
      );
    },
  });
}

interface WildcardRenderProps {
  name: string;
  status: "inProgress" | "executing" | "complete";
  parameters: unknown;
  parsed: unknown;
  /** Per-prefix icon from getToolIcon; null = let ToolCallCard decide. */
  icon?: ReactNode | null;
  /**
   * Live agent.messages passed from useCatchAllRenderer so WildcardRender
   * can detect whether this tool call is already shown nested inside a
   * spawn card (bd:python-factory-0a2yv). When it is, the pill is rendered
   * dimmed + indented (ml-4 opacity-80) per ux-designer spec 5ed48a12.
   */
  messages?: Message[];
}

/**
 * Returns true when `name` is a non-spawn tool call that appears after
 * the most recent spawn_* toolCall in the assistant message stream. These
 * calls are already rendered nested inside the spawn card via SubAgentToolRows,
 * so the wildcard pill should be visually suppressed.
 *
 * The SPAWN_TOOL_NAMES set mirrors the four registered named renderers so the
 * detection stays in sync with spawn-hooks.tsx without an import dependency.
 */
const SPAWN_TOOL_NAMES = new Set([
  "spawn_subagent",
  "spawn_swarm",
  "spawn_graph",
  "spawn_registered_graph",
]);

export function isSubAgentToolCall(
  name: string,
  messages: Message[],
): boolean {
  // spawn_* tools have their own named renderer — they never hit the wildcard.
  // Guard anyway so the helper is safe to call for any name.
  if (SPAWN_TOOL_NAMES.has(name)) return false;

  // Walk backward through messages to find the most recent AssistantMessage
  // batch. If that batch contains a spawn_* toolCall, any non-spawn tool in
  // the SAME OR SUBSEQUENT messages is a sub-agent tool call.
  let foundSpawnAnchor = false;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role !== "assistant") continue;
    const toolCalls = (msg as Extract<Message, { role: "assistant" }>).toolCalls;
    if (!toolCalls?.length) continue;
    if (toolCalls.some((tc) => SPAWN_TOOL_NAMES.has(tc.function.name))) {
      foundSpawnAnchor = true;
      break;
    }
  }
  return foundSpawnAnchor;
}

/**
 * Pure render function for the wildcard catch-all. Extracted from the
 * `useCatchAllRenderer` callback so the canary tests can exercise the
 * predicate + render branches without spinning up the full CopilotKit
 * dispatcher harness on every case.
 */
export function WildcardRender({
  name,
  status,
  parameters,
  parsed,
  icon,
  messages = [],
}: WildcardRenderProps) {
  const carrier = detectCarrier(parsed);
  const preview = computeWildcardPreview(status, parsed);
  // Sub-agent tool calls now render INSIDE the sub-agent containment box
  // (via SubAgentToolRows in the spawn card). Suppress the duplicate
  // wildcard pill entirely — the box owns this pill (bd:python-factory-esb6n,
  // meta-architect 68207eb8 guardrail #3: suppress, do not un-dim).
  if (isSubAgentToolCall(name, messages)) return null;

  const card = (
    <div>
      <ToolCallCard
        name={name}
        status={status}
        previewLine={preview}
        icon={icon ?? undefined}
      >
        <GenericToolBody parameters={parameters} parsed={parsed} status={status} />
      </ToolCallCard>
    </div>
  );

  if (status !== "complete") return card;

  // Carrier #5 (mcp-ui UIResource) — bd:python-factory-eyahj
  // (lo1g9.4). Mounts the real SDK <UIResourceRenderer> via the
  // <McpUiFrame> wrapper which applies sandbox override (drop
  // allow-same-origin from SDK external_url default at
  // `@mcp-ui/[email protected]/dist/index.mjs:234`), Zod + allowlist
  // validator on `onUIAction`, "External UI from <server>" chrome
  // bar, 600px height clamp, ErrorBoundary, and origin-allowlist
  // UX for external_url. See
  // `components/chat/mcp-ui-frame.tsx` for the policy citations.
  if (carrier === "mcp-ui") {
    const meta = extractMcpUiMeta(parsed);
    return (
      <>
        {card}
        <McpUiFrame
          uri={meta.uri}
          mimeType={meta.mimeType}
          text={meta.text}
          blob={meta.blob}
          serverLabel={name}
        />
      </>
    );
  }

  // Carrier #1 (A2UI inline) — bd:python-factory-3hkqx contract.
  // The tool-call pill stays as trace metadata; the InlineView is
  // the consumer view per .agents/steering/a2ui-protocol.md.
  if (carrier === "a2ui") {
    return (
      <>
        {card}
        <InlineView payload={parsed as Parameters<typeof InlineView>[0]["payload"]} />
      </>
    );
  }

  return card;
}

/**
 * Discriminator for the four wildcard cases. Order matters:
 *   1. mcp-ui nested  → carrier #5
 *   2. mcp-ui flat    → carrier #5
 *   3. A2UI components → carrier #1
 *   4. anything else   → plain ToolCallCard
 *
 * Returning a tagged enum keeps the call site exhaustive without
 * scattering predicate logic through the JSX.
 */
type WildcardCarrier = "mcp-ui" | "a2ui" | "plain";

export function detectCarrier(parsed: unknown): WildcardCarrier {
  if (parsed == null || typeof parsed !== "object") return "plain";

  // Flow A: {type:"resource", resource:{uri:"ui://...", mimeType, text|blob}}
  const obj = parsed as {
    type?: unknown;
    resource?: { uri?: unknown; mimeType?: unknown };
  };
  const isMcpUiNested =
    obj.type === "resource" &&
    obj.resource != null &&
    typeof obj.resource.uri === "string" &&
    obj.resource.uri.startsWith("ui://");

  // Flow B: {text|image, uri:"ui://...", mimeType:"..."} — the shape
  // FactoryMCPClient preserves after Strands' content-block flatten.
  const flat = parsed as { uri?: unknown; mimeType?: unknown };
  const isMcpUiFlat =
    typeof flat.uri === "string" &&
    flat.uri.startsWith("ui://") &&
    typeof flat.mimeType === "string";

  if (isMcpUiNested || isMcpUiFlat) return "mcp-ui";

  // A2UI fallthrough — only after mcp-ui has been ruled out.
  if (Array.isArray((parsed as { components?: unknown }).components)) {
    return "a2ui";
  }

  return "plain";
}

function extractMcpUiMeta(parsed: unknown): {
  uri: string;
  mimeType: string;
  text?: string;
  blob?: string;
} {
  if (parsed == null || typeof parsed !== "object") {
    return { uri: "", mimeType: "" };
  }
  const nested = (parsed as {
    resource?: {
      uri?: unknown;
      mimeType?: unknown;
      text?: unknown;
      blob?: unknown;
    };
  }).resource;
  if (
    nested != null &&
    typeof nested.uri === "string" &&
    typeof nested.mimeType === "string"
  ) {
    return {
      uri: nested.uri,
      mimeType: nested.mimeType,
      text: typeof nested.text === "string" ? nested.text : undefined,
      blob: typeof nested.blob === "string" ? nested.blob : undefined,
    };
  }
  const flat = parsed as {
    uri?: unknown;
    mimeType?: unknown;
    text?: unknown;
    blob?: unknown;
  };
  return {
    uri: typeof flat.uri === "string" ? flat.uri : "",
    mimeType: typeof flat.mimeType === "string" ? flat.mimeType : "",
    text: typeof flat.text === "string" ? flat.text : undefined,
    blob: typeof flat.blob === "string" ? flat.blob : undefined,
  };
}

interface GenericBodyProps {
  parameters: unknown;
  parsed: unknown;
  status: "inProgress" | "executing" | "complete";
}

function GenericToolBody({ parameters, parsed, status }: GenericBodyProps) {
  return (
    <div className="space-y-3">
      <Section label="Arguments" body={parameters} />
      {status === "complete" && parsed !== undefined && (
        <Section label="Result" body={parsed} />
      )}
    </div>
  );
}

function Section({ label, body }: { label: string; body: unknown }) {
  const text =
    typeof body === "string" ? body : JSON.stringify(body ?? {}, null, 2);
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted/40 p-2 text-[11px] leading-relaxed text-foreground/80 whitespace-pre-wrap break-words">
        {text}
      </pre>
    </div>
  );
}

/**
 * Best-effort one-line preview for wildcard tool results (bd-rx48 / D3).
 *
 * Heuristics, in order:
 *   1. Array → "<n> items · <first>"
 *   2. Object → "<count> keys · <key>: <value>"
 *   3. Scalar → stringified, truncated
 */
function computeWildcardPreview(
  status: "inProgress" | "executing" | "complete",
  parsed: unknown,
): string | undefined {
  if (status !== "complete" || parsed == null) return undefined;

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) return "Empty";
    const first = parsed[0];
    const summary = typeof first === "string"
      ? truncate(first, 50)
      : typeof first === "object" && first !== null
        ? Object.keys(first as object)[0] ?? "object"
        : String(first);
    return `${parsed.length} item${parsed.length === 1 ? "" : "s"} · ${summary}`;
  }

  if (typeof parsed === "object") {
    const obj = parsed as Record<string, unknown>;
    const keys = Object.keys(obj);
    if (keys.length === 0) return "{}";
    const k = keys[0];
    const v = obj[k];
    const valStr = typeof v === "string"
      ? truncate(v, 40)
      : typeof v === "number" || typeof v === "boolean" || v === null
        ? String(v)
        : Array.isArray(v)
          ? `[${v.length}]`
          : "{…}";
    return `${k}: ${valStr}`;
  }

  return truncate(String(parsed), 80);
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
