import { getMcpClient } from "./mcp-client";

/**
 * Client-side (brick, tool) resolution for real MCP `call_brick_tool`
 * (bd:python-factory-736).
 *
 * Companion-X always runs `MCP_DISCOVERY_MODE=progressive`
 * (`projects/companion_x/main.py`), so real `tools/call` only ever reaches
 * the ~10 top-level meta-tools (`call_brick_tool`, `get_brick_tools`, ...).
 * A brick-prefixed name like `graph_get_stats` is NOT itself a callable
 * top-level tool — it has to be dispatched as
 * `call_brick_tool(brick_name="graph", tool_name="graph_get_stats", ...)`.
 *
 * This mirrors the server's own resolution
 * (`bases/mcp_server/runtime/name_resolution.py::parse_tool_name`) using the
 * whole-registry catalog (`get_tool_catalog`) as the brick/name source of
 * truth instead of duplicating a hardcoded brick list — the same anti-drift
 * property `tool-catalog.ts`'s docstring calls out for the Cmd-K palette.
 */

export interface ResolvedTarget {
  brick: string;
  tool: string;
  publicName: string;
}

interface RawCatalogTool {
  brick: string;
  name: string;
  qualified_name: string;
}

interface RawCatalog {
  tools: RawCatalogTool[];
  aliases: Record<string, string>;
}

let fullCatalogPromise: Promise<RawCatalog> | null = null;

/** Recover a `get_tool_catalog` JSON payload from a native `tools/call` result. */
function extractCatalogPayload(callResult: unknown): RawCatalog {
  const empty: RawCatalog = { tools: [], aliases: {} };
  if (!callResult || typeof callResult !== "object") return empty;
  const result = callResult as {
    structuredContent?: unknown;
    content?: Array<{ type: string; text?: string }>;
  };
  const raw = result.structuredContent !== undefined
    ? result.structuredContent
    : parseTextContent(result.content);
  if (!raw || typeof raw !== "object") return empty;
  const envelope = raw as { ok?: boolean; data?: unknown };
  const payload = envelope.ok === true && envelope.data && typeof envelope.data === "object"
    ? envelope.data
    : raw;
  const body = payload as Partial<RawCatalog>;
  return { tools: body.tools ?? [], aliases: body.aliases ?? {} };
}

function parseTextContent(content?: Array<{ type: string; text?: string }>): unknown {
  if (!content || content.length !== 1 || content[0].type !== "text") return null;
  try {
    return JSON.parse(content[0].text ?? "{}");
  } catch {
    return null;
  }
}

/** Fetch (and cache) the UNFILTERED whole-registry catalog — every tool. */
async function getFullCatalog(): Promise<RawCatalog> {
  if (!fullCatalogPromise) {
    fullCatalogPromise = (async () => {
      const client = await getMcpClient();
      const callResult = await client.callTool({
        name: "get_tool_catalog",
        arguments: { categories: null },
      });
      return extractCatalogPayload(callResult);
    })().catch((err) => {
      fullCatalogPromise = null;
      throw err;
    });
  }
  return fullCatalogPromise;
}

/** Drop the cached catalog (test-only escape hatch; also handy after authoring). */
export function resetToolResolverCache(): void {
  fullCatalogPromise = null;
}

/**
 * Resolve a requested tool name (qualified, brick-local, or the legacy
 * alias-prefixed form like `ml_get_views`) to a `(brick, tool)` pair the
 * real `call_brick_tool` meta-tool can dispatch.
 *
 * Resolution order mirrors `parse_tool_name` exactly: exact qualified-name
 * match, then brick-prefix strip (longest brick name first, so `machine_learning`
 * doesn't lose to a shorter false-positive prefix), then the alias table,
 * then a last-resort exact local-name match. Returns `null` if nothing
 * resolves — the caller (`callTool`) then fails loudly rather than guessing.
 */
export async function resolveToolTarget(requested: string): Promise<ResolvedTarget | null> {
  const catalog = await getFullCatalog();

  const exact = catalog.tools.find((t) => t.qualified_name === requested);
  if (exact) return {
    brick: exact.brick, tool: exact.name, publicName: exact.qualified_name,
  };

  const bricks = [...new Set(catalog.tools.map((t) => t.brick))].sort(
    (a, b) => b.length - a.length,
  );
  for (const brick of bricks) {
    if (requested.startsWith(`${brick}_`) || requested.startsWith(`${brick}.`)) {
      const local = requested.slice(brick.length + 1);
      const match = catalog.tools.find((tool) =>
        tool.brick === brick && (
          tool.qualified_name === requested || tool.name === requested || tool.name === local
        ),
      );
      if (match) return {
        brick: match.brick, tool: match.name, publicName: match.qualified_name,
      };
    }
  }

  for (const [alias, brick] of Object.entries(catalog.aliases)) {
    if (requested.startsWith(`${alias}_`)) {
      const match = catalog.tools.find((tool) =>
        tool.brick === brick && tool.name === requested,
      );
      if (match) return {
        brick: match.brick, tool: match.name, publicName: match.qualified_name,
      };
    }
  }

  const localMatches = catalog.tools.filter((t) => t.name === requested);
  if (localMatches.length === 1) {
    const match = localMatches[0];
    return { brick: match.brick, tool: match.name, publicName: match.qualified_name };
  }

  return null;
}
