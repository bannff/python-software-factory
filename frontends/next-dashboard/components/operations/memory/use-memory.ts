"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import {
  parseMemoryList,
  parseMemoryStats,
  scopeFilterToMetadata,
  type MemoryRecord,
  type MemoryScopeFilter,
  type MemoryStatsSummary,
  type MemoryType,
} from "./memory-types";

/**
 * Owner-scoped Memory browser state (feature-map row 43 read path + row 49
 * Episodic search), backed by the real ``memory_list`` / ``memory_retrieve``
 * / ``memory_stats`` / ``memory_delete`` / ``memory_update`` /
 * ``memory_bulk_preview`` / ``memory_bulk_delete`` MCP tools.
 *
 * Identity is ambient — no ``user_id`` is ever sent, so this always reflects
 * the caller's own principal regardless of which backend adapter is active
 * (in-memory / neo4j / amem today; a graph adapter later — this view does
 * not change when that lands, per the M7.7 scoping consult).
 *
 * A text query switches the read path from ``memory_list`` (plain paged
 * browse) to ``memory_retrieve`` (relevance-scored search) — both return the
 * same record shape so the list renders identically either way.
 */
export function useMemory() {
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [stats, setStats] = useState<MemoryStatsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<MemoryType | "all">("all");
  const [scopeFilter, setScopeFilter] = useState<MemoryScopeFilter>("own");
  const mounted = useRef(true);

  const refresh = useCallback(async (
    nextQuery = query, nextType = typeFilter, nextScope = scopeFilter,
  ) => {
    setLoading(true);
    try {
      const memoryType = nextType === "all" ? undefined : nextType;
      const metadata = scopeFilterToMetadata(nextScope);
      const raw = nextQuery.trim()
        ? await callTool("memory_retrieve", {
            query: nextQuery.trim(), memory_type: memoryType, limit: 50, min_relevance: 0, metadata,
          })
        : await callTool("memory_list", { limit: 100, metadata });
      const parsed = parseMemoryList(raw);
      const filtered = nextQuery.trim() || !memoryType
        ? parsed
        : parsed.filter((m) => m.memoryType === memoryType);
      if (!mounted.current) return;
      setMemories(filtered);
      setError(null);
    } catch {
      if (mounted.current) setError("Memory unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [query, typeFilter, scopeFilter]);

  const refreshStats = useCallback(async () => {
    try {
      const raw = await callTool("memory_stats", {});
      if (mounted.current) setStats(parseMemoryStats(raw));
    } catch {
      // Stats are a supplementary panel — a failure there does not block
      // the list, so it silently stays at its last-known value.
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    void refreshStats();
    return () => {
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const search = useCallback((nextQuery: string) => {
    setQuery(nextQuery);
    void refresh(nextQuery, typeFilter, scopeFilter);
  }, [refresh, typeFilter, scopeFilter]);

  const filterByType = useCallback((nextType: MemoryType | "all") => {
    setTypeFilter(nextType);
    void refresh(query, nextType, scopeFilter);
  }, [refresh, query, scopeFilter]);

  const filterByScope = useCallback((nextScope: MemoryScopeFilter) => {
    setScopeFilter(nextScope);
    void refresh(query, typeFilter, nextScope);
  }, [refresh, query, typeFilter]);

  const remove = useCallback(async (memoryId: string): Promise<boolean> => {
    try {
      await callTool("memory_delete", { memory_id: memoryId });
      await refresh();
      await refreshStats();
      return true;
    } catch {
      return false;
    }
  }, [refresh, refreshStats]);

  const correct = useCallback(async (memoryId: string, content: string): Promise<string | null> => {
    try {
      const raw = await callTool("memory_update", { memory_id: memoryId, content });
      const data = unwrapToolData(raw) as { updated?: boolean; error?: string | null } | null;
      if (!data?.updated) return data?.error ?? "Could not save the correction";
      await refresh();
      return null;
    } catch {
      return "Could not save the correction";
    }
  }, [refresh]);

  const previewBulkDelete = useCallback(async (): Promise<{ count: number; error: string | null }> => {
    try {
      const memoryType = typeFilter === "all" ? undefined : typeFilter;
      const metadata = scopeFilterToMetadata(scopeFilter);
      const raw = await callTool("memory_bulk_preview", {
        query: query.trim() || undefined, memory_type: memoryType, metadata,
      });
      const data = unwrapToolData(raw) as { matched_count?: number; error?: string | null } | null;
      if (data?.error) return { count: 0, error: data.error };
      return { count: data?.matched_count ?? 0, error: null };
    } catch {
      return { count: 0, error: "Could not preview the matching memories" };
    }
  }, [query, typeFilter, scopeFilter]);

  const bulkDelete = useCallback(async (): Promise<string | null> => {
    try {
      const memoryType = typeFilter === "all" ? undefined : typeFilter;
      const metadata = scopeFilterToMetadata(scopeFilter);
      const raw = await callTool("memory_bulk_delete", {
        query: query.trim() || undefined, memory_type: memoryType, metadata,
      });
      const data = unwrapToolData(raw) as { deleted_count?: number; error?: string | null } | null;
      if (data?.error) return data.error;
      await refresh();
      await refreshStats();
      return null;
    } catch {
      return "Bulk delete failed";
    }
  }, [query, typeFilter, scopeFilter, refresh, refreshStats]);

  return {
    memories, stats, loading, error, query, typeFilter, scopeFilter,
    search, filterByType, filterByScope, remove, correct,
    previewBulkDelete, bulkDelete,
    refresh: () => { void refresh(); void refreshStats(); },
  };
}
