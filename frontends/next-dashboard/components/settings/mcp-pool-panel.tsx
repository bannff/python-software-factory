"use client";

import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/hooks/use-health";

/**
 * Row 108 (feature-map) — MCP connection pool state, homed in Settings →
 * Developer. Reuses the existing `useHealth` poll (no new backend): shows
 * the live connection status, healthy/total brick counts, total tool count,
 * and a per-brick health list (with the error when a brick is unhealthy) —
 * the diagnostic that would have surfaced the earlier MCP-401 outage at a
 * glance.
 */
export function McpPoolPanel() {
  const { connected, status, totalTools, brickCount, healthyBricks, bricks, lastChecked } = useHealth();
  const entries = Object.entries(bricks).sort(([a], [b]) => a.localeCompare(b));
  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">MCP connection pool</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Live tool-transport health. {lastChecked ? "Polled every 30s." : "Checking…"}
          </p>
        </div>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
          connected ? "bg-emerald-500/10 text-emerald-400" : "bg-destructive/10 text-destructive")}>
          {connected ? "connected" : status}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <div><dt className="text-muted-foreground">Bricks</dt>
          <dd className="font-medium">{healthyBricks ?? "—"} / {brickCount ?? "—"} healthy</dd></div>
        <div><dt className="text-muted-foreground">Tools</dt>
          <dd className="font-medium">{totalTools ?? "—"}</dd></div>
      </dl>
      {entries.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {entries.map(([name, health]) => (
            <li key={name} className="flex items-center gap-2 rounded-md border border-border/40 bg-muted/10 px-2 py-1 text-xs">
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", health.healthy ? "bg-emerald-400" : "bg-destructive")} />
              <span className="min-w-0 flex-1 truncate" title={name}>{name}</span>
              {!health.healthy && health.error && (
                <span className="shrink-0 truncate text-[10px] text-destructive" title={health.error}>{health.error}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
