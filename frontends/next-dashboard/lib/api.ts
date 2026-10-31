import type {
  ToolListResponse,
  ToolExecuteResponse,
  HealthResponse,
  PersonaListResponse,
} from "./types";
import { getMcpClient } from "./mcp-client";
import { fetchToolCatalog } from "./tool-catalog";
import { resolveToolTarget } from "./tool-resolver";

/**
 * API client for the Python Software Factory gateway.
 *
 * bd:python-factory-736 — `callTool`/`listTools` speak real MCP
 * (`tools/call` / `tools/list` over the `/mcp` streamable-HTTP JSON-RPC
 * transport) via `getMcpClient()`, instead of the retired REST bridge
 * (`POST /api/tools/{tool_name}`). Both functions keep their EXTERNAL
 * signature and return shape unchanged so the ~10 call sites across the
 * dashboard (views/[id]/page.tsx, welcome-view, the graph/timeline/evals
 * hooks, chat-feedback, agent-component cards) need zero edits — only the
 * internals changed. `getHealth`/`listPersonas` keep hitting their small
 * dedicated REST routes, which survive this migration (see
 * `bases/api/.../bridge.py` docstring).
 */

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

/**
 * List all MCP tools available through the gateway.
 *
 * Real MCP `tools/list` only returns tools mounted on the progressive
 * meta-tool surface (`call_brick_tool`, `get_brick_tools`, ...), not the
 * ~40 per-brick tool names the REST bridge's flat `/api/tools` returned.
 * The one caller that needs the flat, brick-prefixed name list
 * (`app/views/[id]/page.tsx`'s `*_get_views` scan) is served by the
 * whole-registry catalog (`fetchToolCatalog`, `get_tool_catalog` meta-tool)
 * instead — same data source the Cmd-K palette already uses.
 */
export async function listTools(): Promise<ToolListResponse> {
  const catalog = await fetchToolCatalog();
  const tools = catalog.tools.map((t) => t.qualified_name);
  return { tools, count: tools.length };
}

/**
 * Execute an MCP tool by name via real `tools/call`.
 *
 * Companion-X always runs `MCP_DISCOVERY_MODE=progressive`
 * (`projects/companion_x/main.py`), so a brick-prefixed name like
 * `graph_get_stats` is not itself a top-level callable tool — real
 * `tools/call` only exposes the ~10 progressive meta-tools. This resolves
 * `name` to its owning `(brick, tool)` pair (`resolveToolTarget`, backed by
 * the same whole-registry catalog the palette uses) and dispatches through
 * the `call_brick_tool` meta-tool, exactly like the aggregator's own
 * `invoke_tool` used to do server-side for the retired REST bridge.
 *
 * Translates the resulting envelope back into the `{tool, result}` shape
 * callers already unwrap today (via `unwrapToolResult`/`unwrapToolData`,
 * which look for a `result` key) — `call_brick_tool`'s own transport
 * envelope (`{ok, result: {kind, content, structured_content, ...}}`, see
 * `tool_dispatch.py`) is unwrapped one level further to recover the actual
 * tool payload, matching what `agg.invoke_tool` returned to the REST bridge.
 */
export async function callTool(
  name: string,
  args: Record<string, unknown> = {},
): Promise<ToolExecuteResponse> {
  const target = await resolveToolTarget(name);
  if (!target) {
    throw new ApiError(404, `Tool '${name}' not found`);
  }
  const client = await getMcpClient();
  const callResult = await client.callTool({
    name: "call_brick_tool",
    arguments: {
      brick_name: target.brick,
      tool_name: target.tool,
      arguments: JSON.stringify(args),
    },
  });
  const value = extractCallBrickToolValue(callResult, name);
  return { tool: name, result: value };
}

/**
 * Recover the historical raw value from a `call_brick_tool` result.
 *
 * `call_brick_tool` itself never fails at the MCP-transport level for a
 * normal tool error — it returns `{ok: false, error: {...}}` as its own
 * structured content (a native transport envelope, see
 * `mcp_contracts.py::native_transport_egress`). That is unwrapped to the
 * inner tool payload here so callers see the same shape the REST bridge
 * used to hand them (the plain tool result, or `{error: "..."}` on failure)
 * instead of the two extra wrapper layers.
 */
function extractCallBrickToolValue(callResult: unknown, name: string): unknown {
  const raw = extractStructuredOrText(callResult);
  if (!raw || typeof raw !== "object") {
    throw new ApiError(502, `Tool '${name}' returned an invalid response`);
  }
  const outer = raw as { schema_version?: string; ok?: boolean; data?: unknown };
  if (outer.ok === false) throw new ApiError(502, `Tool '${name}' failed`);
  const transport = (outer.schema_version && "data" in outer ? outer.data : raw) as
    | { ok?: boolean; result?: unknown }
    | undefined;
  if (!transport || typeof transport !== "object" || transport.ok !== true) {
    throw new ApiError(502, `Tool '${name}' failed`);
  }
  const result = transport.result as
    | { content?: Array<{ type: string; text?: string }>; structured_content?: unknown }
    | undefined;
  if (!result || typeof result !== "object") {
    throw new ApiError(502, `Tool '${name}' returned an invalid response`);
  }
  if (result.structured_content !== undefined) return result.structured_content;
  const content = result.content ?? [];
  if (content.length === 1 && content[0].type === "text") {
    try {
      return JSON.parse(content[0].text ?? "null");
    } catch {
      return content[0].text ?? null;
    }
  }
  throw new ApiError(502, `Tool '${name}' returned an invalid response`);
}

/** Recover a JSON payload from a native `tools/call` result. */
function extractStructuredOrText(callResult: unknown): unknown {
  if (!callResult || typeof callResult !== "object") return callResult;
  const result = callResult as {
    structuredContent?: unknown;
    content?: Array<{ type: string; text?: string }>;
  };
  if (result.structuredContent !== undefined) {
    return result.structuredContent;
  }
  const content = result.content ?? [];
  if (content.length === 1 && content[0].type === "text") {
    const text = content[0].text ?? "";
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return content;
}

/** Aggregated gateway health check. */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

/**
 * List chat personas for the '/' palette (bd:python-factory-d4roe.3).
 * Thin read passthrough to the agent brick's ``agent_get_agent_registry``
 * MCP tool via the api base's small dedicated REST route. Read-only GET.
 */
export async function listPersonas(): Promise<PersonaListResponse> {
  return request<PersonaListResponse>("/api/personas");
}

export { ApiError };
