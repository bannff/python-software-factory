"use client";

import { useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Row 109 (feature-map) — `memory`, homed in Settings → Developer. Scaffold
 * over the existing `memory_stats` MCP read (no new backend): the memory
 * store's total count and a by-type breakdown. Deferred: the interactive
 * node/edge graph visualization (a heavy viz; the Memory operations surface
 * owns the browse/inspect UI — this is the Developer at-a-glance census).
 */
export function MemoryStatsPanel() {
  const [stats, setStats] = useState<{ total: number; byType: [string, number][] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const data = unwrapToolData(await callTool("memory_stats", {})) as
          { total_memories?: number; by_type?: Record<string, number> } | null;
        if (!live) return;
        setStats({
          total: data?.total_memories ?? 0,
          byType: Object.entries(data?.by_type ?? {}).sort(([, a], [, b]) => b - a),
        });
      } catch {
        if (live) setError("Memory stats unavailable.");
      }
    })();
    return () => { live = false; };
  }, []);

  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <h3 className="text-sm font-medium">Memory</h3>
      <p className="mt-1 text-xs text-muted-foreground">Stored memory census. Browse/edit lives in the Memory surface.</p>
      {error && <p role="alert" className="mt-2 text-xs text-destructive">{error}</p>}
      {stats && !error && (
        <>
          <p className="mt-3 text-2xl font-semibold">{stats.total}<span className="ml-1.5 text-xs font-normal text-muted-foreground">memories</span></p>
          {stats.byType.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-xs">
              {stats.byType.map(([type, count]) => (
                <li key={type} className="flex items-center justify-between gap-2">
                  <span className="truncate text-muted-foreground" title={type}>{type}</span>
                  <span className="font-medium">{count}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
