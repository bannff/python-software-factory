"use client";

import { cn } from "@/lib/utils";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";

/**
 * Row 104 (feature-map) — `logs`, homed in Settings → Developer. Scaffold
 * over the existing live tool-event SSE stream (`useLiveToolStream`, no new
 * backend): a rolling, newest-first activity log of gateway tool events with
 * timestamp + status. Deferred: raw gateway log-line streaming and the
 * server-side log-level control (no `/api/logs` endpoint in this port yet).
 */
export function LogsPanel({ variant = "panel" }: { variant?: "panel" | "page" }) {
  const { entries, connected } = useLiveToolStream();
  const isPage = variant === "page";
  return (
    <div className={cn("rounded-md border border-border/40 p-4", isPage ? "flex h-full min-h-0 flex-col" : "mt-4")}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">Logs</h3>
          <p className="mt-1 text-xs text-muted-foreground">Live gateway tool-event activity (newest first).</p>
        </div>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
          connected ? "bg-emerald-500/10 text-emerald-400" : "bg-muted/30 text-muted-foreground")}>
          {connected ? "streaming" : "idle"}
        </span>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs italic text-muted-foreground/70">No recent activity.</p>
      ) : (
        <ul className={cn("mt-3 flex flex-col gap-0.5 overflow-auto font-mono text-[11px]",
          isPage ? "min-h-0 flex-1" : "max-h-64")}>
          {entries.map((entry) => (
            <li key={entry.id} className="flex items-center gap-2">
              <span className="shrink-0 text-muted-foreground/60">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
              <span className={cn("shrink-0",
                entry.status === "failed" ? "text-destructive"
                  : entry.status === "running" ? "text-amber-400" : "text-emerald-400")}>
                {entry.status === "failed" ? "✗" : entry.status === "running" ? "…" : "✓"}
              </span>
              <span className="min-w-0 flex-1 truncate" title={entry.title}>{entry.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
