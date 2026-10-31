"use client";

import { useCallback, useMemo, useState } from "react";
import { Sparkles, Check } from "lucide-react";
import { useCopilotKit } from "@copilotkit/react-core/v2";
import { Popover } from "@/components/ui/popover";
import { usePersonas } from "@/lib/hooks/use-personas";
import { cn } from "@/lib/utils";

/**
 * Persona '/' palette (bd:python-factory-d4roe.3, Phase 2).
 *
 * CopilotKit v2 ships NO native slash-command / command-palette
 * primitive (confirmed in strands-expert verdict 6e22d1bb Q4 — the v2
 * hook surface has no `/` selector), so this is a CUSTOM popover. It
 * lists chat personas from GET /api/personas and, on pick, calls
 * `core.setProperties({ ...current, companion_x_agent_id: id })` so the
 * NEXT run carries the selection in `RunAgentInput.forwardedProps`
 * (the v2 `runAgent` path spreads `{...core.properties, ...forwardedProps}`
 * — `@copilotkitnext/core` `index.mjs` `setProperties`/`runAgent`).
 *
 * This re-keys the WHOLE chat agent per-thread (the BE cache_key is
 * `f"{agent_id}-{thread_id}"`); it is NOT an LLM tool call. We do NOT
 * touch `<CopilotChat agentId="companion_x">` — that is the wire/runtime
 * identity, not the persona (verdict 6e22d1bb Q1).
 *
 * `setProperties` REPLACES the whole properties object, so we merge the
 * current `copilotkit.properties` to avoid clobbering other forwarded
 * props. Selection is sticky for the thread until changed.
 *
 * This is functional wiring, not a design pass — minimal shadcn/ui
 * styling consistent with the sidebar. ux-designer can polish later.
 */
export function PersonaPalette() {
  const { copilotkit } = useCopilotKit();
  const { personas, loading, error, refresh } = usePersonas();
  const [activeId, setActiveId] = useState<string | null>(null);

  const activeName = useMemo(
    () => personas.find((p) => p.id === activeId)?.name ?? "Persona",
    [personas, activeId],
  );

  const onPick = useCallback(
    (id: string) => {
      const current = (copilotkit?.properties ?? {}) as Record<string, unknown>;
      copilotkit?.setProperties({ ...current, companion_x_agent_id: id });
      setActiveId(id);
    },
    [copilotkit],
  );

  return (
    <Popover
      align="left"
      trigger={
        <span
          className="flex items-center gap-1 text-[10px] text-muted-foreground/70"
          title="Switch chat persona (applies to the next message)"
          onMouseEnter={refresh}
        >
          <Sparkles className="h-3 w-3" />
          <span className="truncate max-w-[90px]">{activeName}</span>
        </span>
      }
    >
      <div className="flex flex-col gap-1">
        <div className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/60">
          Personas
        </div>
        {loading && (
          <div className="px-2 py-1.5 text-muted-foreground/60">Loading…</div>
        )}
        {error && !loading && (
          <div className="px-2 py-1.5 text-destructive/80">{error}</div>
        )}
        {!loading && !error && personas.length === 0 && (
          <div className="px-2 py-1.5 text-muted-foreground/60">
            No personas registered
          </div>
        )}
        {personas.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onPick(p.id)}
            className={cn(
              "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left",
              "hover:bg-accent/50 transition-colors cursor-pointer",
              p.id === activeId && "bg-accent/40",
            )}
            title={p.description || p.id}
          >
            <Check
              className={cn(
                "mt-0.5 h-3 w-3 shrink-0",
                p.id === activeId ? "text-emerald-400" : "text-transparent",
              )}
            />
            <span className="min-w-0">
              <span className="block truncate font-medium text-foreground">
                {p.name || p.id}
              </span>
              {p.description && (
                <span className="block truncate text-[10px] text-muted-foreground/70">
                  {p.description}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>
    </Popover>
  );
}
