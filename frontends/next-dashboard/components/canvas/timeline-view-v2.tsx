"use client";

/**
 * ``TimelineViewV2`` entry — dispatches between agent-painted carrier
 * #2 rendering (``state.canvas.timeline``) and the default MCP/SSE-driven
 * live timeline. The live mode lives in ``timeline-view-v2-live.tsx``.
 */

import { useMemo } from "react";
import { GitBranch } from "lucide-react";
import { ComponentTree } from "@companion-x/shared-renderer";
import { TimelineViewV2Live } from "./timeline-view-v2-live";
import {
  usePaintedComponents,
  type CanvasState,
} from "@/lib/copilotkit/a2ui-canvas-slots";
import type { Step, ActiveToolCall } from "@/lib/types";

interface TimelineViewV2Props {
  steps?: Step[];
  toolCalls?: ActiveToolCall[];
  agentState?: { canvas?: CanvasState } & Record<string, unknown>;
}

export default function TimelineViewV2({ agentState }: TimelineViewV2Props = {}) {
  /* Carrier #2: when the agent paints `state.canvas.timeline` with an
   * A2UI components tree, render that tree directly. Empty slot falls
   * back to today's MCP/SSE-driven timeline — keeps existing UX intact. */
  const timelineSlot = useMemo(
    () => agentState?.canvas?.timeline,
    [agentState?.canvas?.timeline],
  );
  const paintedComponents = usePaintedComponents(timelineSlot);

  if (paintedComponents.length > 0) {
    return (
      <div className="flex h-full flex-col" style={{ minHeight: 0 }}>
        <div className="flex items-center gap-2 border-b border-border/50 bg-card/10 px-4 py-2">
          <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground">
            {timelineSlot?.name ?? "Timeline"} · agent-painted
          </span>
        </div>
        <div className="flex-1 overflow-auto p-4">
          <ComponentTree nodes={paintedComponents} />
        </div>
      </div>
    );
  }

  return <TimelineViewV2Live />;
}
