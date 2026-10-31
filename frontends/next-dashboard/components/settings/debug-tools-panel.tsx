"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";

/**
 * Row 112 (feature-map) — debug tools, homed in Settings → Developer.
 * Client-only (upstream's own `DebugToolsTab` has no handler): a read-only
 * runtime overlay — the live tool-event SSE connection state + recent event
 * count, plus this client's runtime context (user agent, viewport, origin).
 * The companion diagnostic to the MCP pool panel for tracing tool-transport
 * issues from the browser side.
 */
export function DebugToolsPanel() {
  const { entries, connected } = useLiveToolStream();
  const [ctx, setCtx] = useState<{ ua: string; viewport: string; origin: string } | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setCtx({
      ua: navigator.userAgent,
      viewport: `${window.innerWidth}×${window.innerHeight}`,
      origin: window.location.origin,
    });
  }, []);

  const rows: [string, string][] = [
    ["Tool event stream", connected ? "connected" : "disconnected"],
    ["Recent tool events", String(entries.length)],
    ["Viewport", ctx?.viewport ?? "—"],
    ["Dashboard origin", ctx?.origin ?? "—"],
  ];

  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <h3 className="text-sm font-medium">Debug tools</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Read-only client diagnostics for tracing tool-transport and rendering issues.
      </p>
      <dl className="mt-3 grid gap-1.5 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className={cn("truncate font-medium",
              label === "Tool event stream" && (connected ? "text-emerald-400" : "text-destructive"))}
              title={value}>{value}</dd>
          </div>
        ))}
      </dl>
      {ctx && <p className="mt-2 truncate text-[10px] text-muted-foreground/70" title={ctx.ua}>{ctx.ua}</p>}
    </div>
  );
}
