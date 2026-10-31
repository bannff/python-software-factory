"use client";

import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/hooks/use-health";

/**
 * Row 105 (feature-map) — `system`: host runtime & services, homed in
 * Settings → Developer. Reuses the existing `useHealth` poll (no new
 * backend): the live gateway address + status, and the service census
 * (registered bricks, total tools). Deferred: per-session/performance
 * metrics (no host-runtime endpoint in this port yet).
 */
export function SystemPanel() {
  const { connected, status, gateway, totalTools, brickCount, lastChecked } = useHealth();
  const rows: [string, string][] = [
    ["Gateway", gateway ?? "—"],
    ["Status", status],
    ["Registered bricks", brickCount != null ? String(brickCount) : "—"],
    ["Total tools", totalTools != null ? String(totalTools) : "—"],
    ["Last checked", lastChecked ? new Date(lastChecked).toLocaleTimeString() : "—"],
  ];
  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">System</h3>
          <p className="mt-1 text-xs text-muted-foreground">Host runtime and service health.</p>
        </div>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
          connected ? "bg-emerald-500/10 text-emerald-400" : "bg-destructive/10 text-destructive")}>
          {connected ? "online" : status}
        </span>
      </div>
      <dl className="mt-3 grid gap-1.5 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="truncate font-medium" title={value}>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
