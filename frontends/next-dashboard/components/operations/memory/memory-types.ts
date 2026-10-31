import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Client view of a Memory record (feature-map row 43/49 — Memory browser +
 * Episodic search). Mirrors the read-safe subset of the Memory brick's
 * ``MemoryData`` DTO returned by ``memory_list`` / ``memory_retrieve``.
 * Identity is ambient — the UI never sends a ``user_id`` unless it wants to
 * scope to a different owner than the caller's own principal. Every row is
 * parsed defensively so a degraded record is dropped, never crashes the view.
 */
export type MemoryType = "short_term" | "long_term" | "episodic";

export interface MemoryRecord {
  id: string;
  userId: string;
  content: string;
  memoryType: MemoryType;
  category: string;
  metadata: Record<string, unknown>;
  relevanceScore: number;
  createdAt: string;
  updatedAt: string | null;
  expiresAt: string | null;
}

export interface MemoryStatsSummary {
  totalMemories: number;
  byType: Record<string, number>;
  byCategory: Record<string, number>;
  oldestMemory: string | null;
  newestMemory: string | null;
}

/** A scope filter value for the Memory tab (owner ruling 2026-09-16 06:32:
 * one label-scoped store, never a store per persona). "own" clears the
 * filter (default recall = own scope + shared, i.e. no explicit
 * ``agent`` constraint); "shared" restricts to ``scope:shared`` only. */
export type MemoryScopeFilter = "own" | "shared";

/** Build the ``memory_list``/``memory_retrieve`` ``metadata`` filter for a
 * scope selection. "own" sends no filter (server-side default recall
 * already means "this caller's own memories" via ambient identity — the
 * ruling's "own scope + shared" default requires no extra constraint
 * since everything returned already belongs to the caller). "shared"
 * narrows to ``scope=shared`` explicitly. */
export function scopeFilterToMetadata(scope: MemoryScopeFilter): Record<string, string> | undefined {
  return scope === "shared" ? { scope: "shared" } : undefined;
}

const MEMORY_TYPES = ["short_term", "long_term", "episodic"] as const;

function oneOfType(value: unknown): MemoryType {
  return typeof value === "string" && (MEMORY_TYPES as readonly string[]).includes(value)
    ? (value as MemoryType)
    : "short_term";
}

/** Parse one raw row into a MemoryRecord, or null if it is not valid. */
export function parseMemoryRow(row: unknown): MemoryRecord | null {
  if (!row || typeof row !== "object") return null;
  const r = row as Record<string, unknown>;
  if (typeof r.id !== "string" || !r.id) return null;
  if (typeof r.content !== "string") return null;
  return {
    id: r.id,
    userId: typeof r.user_id === "string" ? r.user_id : "",
    content: r.content,
    memoryType: oneOfType(r.memory_type),
    category: typeof r.category === "string" ? r.category : "custom",
    metadata: (r.metadata && typeof r.metadata === "object" ? r.metadata : {}) as Record<string, unknown>,
    relevanceScore: typeof r.relevance_score === "number" ? r.relevance_score : 1,
    createdAt: typeof r.created_at === "string" ? r.created_at : "",
    updatedAt: typeof r.updated_at === "string" ? r.updated_at : null,
    expiresAt: typeof r.expires_at === "string" ? r.expires_at : null,
  };
}

/** Unwrap + validate a ``memory_list`` ToolResult into an ordered list. */
export function parseMemoryList(raw: unknown): MemoryRecord[] {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.memories) ? obj.memories : [];
  return rows.map(parseMemoryRow).filter((row): row is MemoryRecord => row !== null);
}

/** Unwrap + validate a ``memory_stats`` ToolResult. */
export function parseMemoryStats(raw: unknown): MemoryStatsSummary {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  return {
    totalMemories: typeof obj.total_memories === "number" ? obj.total_memories : 0,
    byType: (obj.by_type && typeof obj.by_type === "object" ? obj.by_type : {}) as Record<string, number>,
    byCategory: (obj.by_category && typeof obj.by_category === "object" ? obj.by_category : {}) as Record<string, number>,
    oldestMemory: typeof obj.oldest_memory === "string" ? obj.oldest_memory : null,
    newestMemory: typeof obj.newest_memory === "string" ? obj.newest_memory : null,
  };
}
