"use client";

import { useHealth } from "@/lib/hooks/use-health";
import { useModelCatalog } from "@/lib/hooks/use-model-catalog";

/**
 * Row 110 (feature-map) — `config`, homed in Settings → Developer. Upstream
 * exposes raw KiroCrew/agent config EDITORS; Companion-X deliberately does
 * not surface raw-config editing (owner ruling: settings, not raw config).
 * This scaffold is the honest read-only equivalent — the resolved runtime
 * config a user can actually observe (gateway, configured model providers),
 * with an explicit note that editing happens via env/config brick, not here.
 */
export function ConfigPanel() {
  const { gateway, status } = useHealth();
  // Read-only inventory: counts must reflect the whole catalog, not the picker's scope.
  const catalog = useModelCatalog({ scope: "all" });
  const providers = catalog.groups?.map((g) => g.provider) ?? [];
  const modelCount = catalog.groups?.reduce((n, g) => n + g.models.length, 0) ?? 0;
  const rows: [string, string][] = [
    ["Gateway", gateway ?? "—"],
    ["Gateway status", status],
    ["Model providers", providers.length ? providers.join(", ") : "—"],
    ["Configured models", String(modelCount)],
  ];
  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <h3 className="text-sm font-medium">Config</h3>
      <p className="mt-1 text-xs text-muted-foreground">Resolved runtime configuration (read-only).</p>
      <dl className="mt-3 grid gap-1.5 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="truncate font-medium" title={value}>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 rounded-md border border-border/40 bg-muted/20 p-2 text-[11px] text-muted-foreground">
        Configuration is set via environment / the config brick and is not editable from this page.
      </p>
    </div>
  );
}
