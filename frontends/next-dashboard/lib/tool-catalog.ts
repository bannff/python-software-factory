/**
 * Tool-catalog client + ranking for the Cmd-K palette (bd:3jcls.4).
 *
 * The registry is GENERATED server-side. This module fetches it and orders it;
 * it contains no tool names and no brick names. Adding a tool to any brick has
 * to make it appear here with zero edits, which is the whole point — the evals
 * evaluator registry is three hand-synced literals that already drifted
 * (bd:python-factory-wvkvg.22).
 *
 * One round-trip: real MCP `tools/call get_tool_catalog` loads every brick
 * in-process on the server (bd:python-factory-736 — migrated off the retired
 * `GET /api/tools/catalog` REST route onto the same meta-tool real MCP
 * clients already have via `call_brick_tool`'s sibling meta-tools; FastMCP's
 * `tools/list` only advertises the ~10 progressive-discovery meta-tools, not
 * a per-brick dump, so `get_tool_catalog` is the one that actually returns
 * the full registry in a single call). A frontend-driven `get_brick_tools`
 * walk would be ~40 sequential calls and would render a partial registry
 * until the last one landed.
 *
 * This also closes the fuzzy-tool-name-resolution gap the SME review
 * flagged: the retired `/api/tools/resolve/{partial_name}` route has no real
 * MCP equivalent (`tools/call` requires an exact name), and had zero
 * frontend callers to begin with. `fuzzyScore`/`rankTools` below already
 * implement fuzzy matching CLIENT-SIDE against this catalog — the Cmd-K
 * palette's actual fuzzy-match need was already served locally, never by
 * the server route.
 */

export interface CatalogTool {
  brick: string;
  name: string;
  /** Aggregator-visible, brick-prefixed name (what actually gets invoked). */
  qualified_name: string;
  description: string;
  input_schema: JsonSchema;
  category: string | null;
}

export interface JsonSchema {
  type?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  enum?: unknown[];
  default?: unknown;
  anyOf?: JsonSchema[];
  items?: JsonSchema;
  description?: string;
  additionalProperties?: boolean | JsonSchema;
}

export interface ToolCatalog {
  tools: CatalogTool[];
  count: number;
  bricks_loaded: string[];
  bricks_failed: { brick: string; error: string }[];
  categories: string[] | null;
  /** Server-owned view-id → brick-name aliases (e.g. `ml` → `machine_learning`). */
  aliases: Record<string, string>;
}

const EMPTY: ToolCatalog = {
  tools: [], count: 0, bricks_loaded: [], bricks_failed: [],
  categories: null, aliases: {},
};

/** Fetch the whole-registry catalog, scoped to human-fireable verbs. */
export async function fetchToolCatalog(signal?: AbortSignal): Promise<ToolCatalog> {
  const { getMcpClient } = await import("./mcp-client");
  const client = await getMcpClient();
  const callResult = await client.callTool(
    { name: "get_tool_catalog", arguments: { categories: ["operational", "authoring"] } },
    { signal },
  );
  const body = extractCatalogPayload(callResult) as Partial<ToolCatalog>;
  return { ...EMPTY, ...body, tools: body.tools ?? [] };
}

/** Recover the catalog JSON from a native `tools/call` result. */
function extractCatalogPayload(callResult: unknown): unknown {
  if (!callResult || typeof callResult !== "object") return {};
  const result = callResult as {
    structuredContent?: unknown;
    content?: Array<{ type: string; text?: string }>;
  };
  const raw = result.structuredContent !== undefined
    ? result.structuredContent
    : parseTextContent(result.content);
  if (!raw || typeof raw !== "object") return {};
  const envelope = raw as { ok?: boolean; data?: unknown };
  return envelope.ok === true && envelope.data && typeof envelope.data === "object"
    ? envelope.data
    : raw;
}

function parseTextContent(
  content: Array<{ type: string; text?: string }> | undefined,
): unknown {
  if (!content || content.length !== 1 || content[0].type !== "text") return content ?? {};
  try {
    return JSON.parse(content[0].text ?? "null");
  } catch {
    return content[0].text ?? "";
  }
}

/**
 * Resolve the active canvas view id onto a brick name that exists in the
 * catalog. Uses the server-shipped alias table, so there is no brick list
 * here to fall out of sync with the backend.
 */
export function activeBrickFor(
  view: string | undefined, catalog: ToolCatalog,
): string | null {
  if (!view) return null;
  const candidate = catalog.aliases[view] ?? view;
  return catalog.bricks_loaded.includes(candidate) ? candidate : null;
}

/**
 * Subsequence match — the affordance every command palette has: `gnf` finds
 * `graph_get_new_findings`. Returns a score (lower is better) or `null`.
 * A contiguous hit scores better than a scattered one, and an earlier hit
 * better than a later one.
 */
export function fuzzyScore(haystack: string, needle: string): number | null {
  if (!needle) return 0;
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let score = 0;
  let at = 0;
  let previous = -1;
  for (const char of n) {
    const found = h.indexOf(char, at);
    if (found === -1) return null;
    score += found - at; // characters skipped
    if (previous !== -1 && found !== previous + 1) score += 1; // non-contiguous
    previous = found;
    at = found + 1;
  }
  return score;
}

/** Best score across the fields a human would search by. */
function scoreTool(tool: CatalogTool, query: string): number | null {
  const name = fuzzyScore(tool.qualified_name, query);
  if (name !== null) return name;
  const desc = fuzzyScore(tool.description, query);
  // Description hits rank below name hits, always.
  return desc === null ? null : desc + 1000;
}

/**
 * How much the active tab's brick is favoured. Applied as a score DISCOUNT,
 * not a hard bucket.
 *
 * A hard bucket looked right until it was driven in a browser: on the ML tab,
 * typing `cacheset` put `machine_learning_ml_sample_timeseries` (a scattered
 * hit in its DESCRIPTION) above `cache_set` (a near-exact name hit), because
 * brick membership outranked match quality. That makes typing pointless.
 *
 * As a discount the behaviour is right at both ends with no special-casing:
 * with an empty query every score is 0, so the active brick's verbs come
 * first; once the human narrows, match quality leads and the active brick is
 * a strong tiebreaker. Small enough that a name hit (single digits) always
 * beats a description-only hit (1000+).
 */
const ACTIVE_BRICK_BONUS = 6;

/**
 * Filter by fuzzy query and order with the active tab's brick first.
 *
 * The active-brick bias comes from the entry's own `brick` field compared
 * against a resolved brick name — no hardcoded ordering table.
 */
export function rankTools(
  tools: CatalogTool[], query: string, activeBrick: string | null,
): CatalogTool[] {
  const scored: { tool: CatalogTool; score: number }[] = [];
  for (const tool of tools) {
    const score = scoreTool(tool, query);
    if (score === null) continue;
    const active = activeBrick !== null && tool.brick === activeBrick;
    scored.push({ tool, score: score - (active ? ACTIVE_BRICK_BONUS : 0) });
  }
  scored.sort((a, b) => {
    if (a.score !== b.score) return a.score - b.score;
    return a.tool.qualified_name.localeCompare(b.tool.qualified_name);
  });
  return scored.map((s) => s.tool);
}
