"use client";

/**
 * Generic "Live View" canvas tab — the un-typed escape hatch for
 * carrier #2 (canvas-paint). Reads ``state.canvas.live`` from the
 * un-stubbed ``useCopilotCanvasState`` hook (bd-E) and renders the
 * agent's A2UI components tree directly via ``<ComponentTree>``.
 *
 * Distinct from ``graph`` / ``timeline`` / ``findings`` slots which
 * have bespoke chrome — this tab just paints whatever the agent emits
 * with no domain assumptions, so a single ``ui_paint_canvas("live",
 * payload)`` call surfaces here without any FE plumbing.
 *
 * Empty state: rendered when ``state.canvas.live`` is missing or
 * its ``components`` array is empty.
 *
 * Slot rename ``canvas`` → ``live`` under bd:python-factory-3hkqx so
 * the slot key matches the FE view id (the prior collision was the
 * "agent painted to canvas slot but I asked for live page" UX bug).
 */

import { useMemo } from "react";
import { LayoutGrid } from "lucide-react";
import { ComponentTree } from "@companion-x/shared-renderer";
import { useCopilotCanvasState } from "@/lib/hooks/use-copilot-state";
import { usePaintedComponents } from "@/lib/copilotkit/a2ui-canvas-slots";

export default function LiveView() {
  const { agentState } = useCopilotCanvasState();

  /* Per strands-expert verdict L6: useAgent forceUpdate's on every
   * state change with no per-key selector. Memo on the slot reference
   * short-circuits when the agent doesn't paint, so the heavy
   * <ComponentTree> sub-tree doesn't re-render on unrelated state
   * changes. */
  const slot = useMemo(
    () => agentState.canvas?.live,
    [agentState.canvas?.live],
  );
  const components = usePaintedComponents(slot);

  if (components.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex h-full flex-col" style={{ minHeight: 0 }}>
      <div className="flex items-center gap-2 border-b border-border/50 bg-card/10 px-4 py-2">
        <LayoutGrid className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-medium text-muted-foreground">
          {slot?.name ?? "Live"} · agent-rendered
        </span>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <ComponentTree nodes={components} />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/10">
        <LayoutGrid className="h-6 w-6 text-violet-400/60" />
      </div>
      <p className="text-sm">Awaiting agent paint…</p>
      <p className="text-[11px] text-muted-foreground/60 max-w-xs">
        This view renders any A2UI payload the agent writes to{" "}
        <code className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[10px]">
          state.canvas.live
        </code>{" "}
        via the <code className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[10px]">ui_paint_canvas</code> MCP tool.
      </p>
    </div>
  );
}
