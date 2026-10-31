"use client";

import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/hooks/use-health";

/**
 * Row 106 (feature-map) — `telemetry`, homed in Settings → Developer.
 * Scaffold over the existing `useHealth` timeline capabilities (no new
 * backend): the live tool-event transport and the history backend/
 * persistence. Deferred: startup timings + per-turn context traces (no
 * telemetry endpoint in this port yet — the substrate is the timeline).
 */
export function TelemetryPanel() {
  const { timeline } = useHealth();
  const live = timeline?.live;
  const history = timeline?.history;
  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <h3 className="text-sm font-medium">Telemetry</h3>
      <p className="mt-1 text-xs text-muted-foreground">Tool-event transport and history capabilities.</p>
      <dl className="mt-3 grid gap-1.5 text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Live stream</dt>
          <dd className="font-medium">
            <span className={cn("mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle",
              live?.available ? "bg-emerald-400" : "bg-muted-foreground/40")} />
            {live?.available ? (live.transport || "available") : "unavailable"}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">History</dt>
          <dd className="font-medium">
            {history?.available ? `${history.backend}${history.persistent ? " · persistent" : ""}` : (history?.reason || "unavailable")}
          </dd>
        </div>
      </dl>
    </div>
  );
}
