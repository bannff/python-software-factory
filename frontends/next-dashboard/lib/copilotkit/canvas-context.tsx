"use client";

/**
 * <CanvasContextBridge /> — publishes Companion-X canvas state into the
 * CopilotKit v2 agent context via `useAgentContext`. The chat agent then
 * sees the user's active view, open tabs, and the most recent
 * tool-stream entries on every turn (bd-vw04).
 *
 * v2 renamed `useCopilotReadable` to `useAgentContext`. Re-exported via
 * `@copilotkitnext/react`. Signature:
 *     useAgentContext({ description: string, value: JsonSerializable })
 *
 * Hard cap on `recentTools` to 10 entries so the agent's prompt budget
 * does not balloon when the live tool stream is busy. We never publish
 * the raw SSE buffer, only a JSON-serializable summary.
 *
 * Must be mounted inside <CopilotKitProvider> AND inside
 * <WorkbenchProvider> — placed in `provider.tsx` next to <ToolRenderers />
 * which already lives there.
 */

import { useMemo } from "react";
import type { JsonSerializable } from "@copilotkit/react-core/v2";
import { useAgentContext } from "@copilotkit/react-core/v2";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";

const RECENT_TOOL_CAP = 10;

interface SerializedCanvasState {
  activeView: string;
  activeTabId: string;
  openTabs: string[];
  selectedSubviews: Record<string, string>;
  recentTools: Array<{
    title: string;
    type: string;
    status: string;
    timestamp: number;
  }>;
}

export function CanvasContextBridge() {
  const { activeView, activeTabId, tabs, selectedBrickViews } = useWorkbenchContext();
  const { entries } = useLiveToolStream();

  const value = useMemo<SerializedCanvasState>(() => {
    return {
      activeView,
      activeTabId,
      openTabs: tabs.map((t) => t.viewId),
      selectedSubviews: selectedBrickViews,
      recentTools: entries.slice(0, RECENT_TOOL_CAP).map((e) => ({
        title: e.title,
        type: e.type,
        status: e.status,
        timestamp: e.timestamp,
      })),
    };
  }, [activeView, activeTabId, tabs, selectedBrickViews, entries]);

  useAgentContext({
    description:
      "Companion-X canvas state: active workbench view, open tabs, and " +
      "the most recent tool-stream entries (capped). Use this to answer " +
      "user questions about what they're looking at.",
    // bd-8qdq: cast at SDK boundary keeps SerializedCanvasState a closed
    // shape so TS catches typos at construction inside `useMemo` above.
    // The SDK's JsonSerializable is open-by-design (recursive index
    // signature) for forward-compat; we only cross that contract here.
    // See memory: [CONSULT bd:python-factory-8qdq phase:design specialist:meta-architect].
    value: value as unknown as JsonSerializable,
  });

  return null;
}
