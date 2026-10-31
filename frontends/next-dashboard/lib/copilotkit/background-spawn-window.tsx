"use client";

/**
 * BackgroundSpawnWindow — live sub-window for async background agent runs.
 * bd:python-factory-r3eqj P2c
 *
 * Rendered inside spawn_subagent_async tool cards (see spawn-hooks.tsx
 * useSpawnSubagentAsyncRenderer). Subscribes to per-run SSE and renders
 * a live event stream so the user can see the background agent working
 * without the chat being blocked.
 *
 * Event shapes on the wire:
 *   spawn.event   → inner `event` field is a raw Strands event dict
 *   swarm.completed / status=completed → marks the run done
 *
 * Text delta extraction: event.data (string) for content deltas.
 * Tool call extraction:  event.current_tool_use?.name or event.type === "tool_use_stream"
 */

import { Loader2, CheckCircle2, Bot } from "lucide-react";
import { useRunStream, type RunStreamEvent } from "@/lib/hooks/use-run-stream";
import { cn } from "@/lib/utils";

const MAX_VISIBLE = 20;

interface BackgroundSpawnWindowProps {
  runId: string;
  agentId: string;
}

/** Extract a short display label from a raw Strands event dict. */
function extractEventLabel(ev: RunStreamEvent): string | null {
  const inner = ev.event as Record<string, unknown> | undefined;
  if (!inner) return null;

  // Tool call stream — show tool name
  const toolName =
    (inner.current_tool_use as Record<string, unknown> | undefined)?.name;
  if (typeof toolName === "string" && toolName) {
    return `🔧 ${toolName.replace(/_/g, " ")}`;
  }
  if (inner.type === "tool_use_stream") {
    const tName =
      (inner.tool_use as Record<string, unknown> | undefined)?.name;
    if (typeof tName === "string" && tName) return `🔧 ${tName.replace(/_/g, " ")}`;
  }

  // Text delta — show first 80 chars
  const data = inner.data;
  if (typeof data === "string" && data.trim()) {
    const snip = data.trim().slice(0, 80);
    return snip.length < data.trim().length ? `${snip}…` : snip;
  }

  // Fall back to event_type
  if (ev.event_type && ev.event_type !== "spawn.event") return ev.event_type;

  return null;
}

function EventRow({ ev }: { ev: RunStreamEvent }) {
  const label = extractEventLabel(ev);
  if (!label) return null;
  return (
    <div className="flex items-center gap-2 text-[11px] py-0.5">
      <span className="font-mono text-foreground/75 truncate">{label}</span>
    </div>
  );
}

export function BackgroundSpawnWindow({
  runId,
  agentId,
}: BackgroundSpawnWindowProps) {
  const { events, connected, completed } = useRunStream(runId);

  // Only show spawn.event rows with extractable content
  const visibleEvents = events
    .filter((ev) => ev.event_type === "spawn.event" || (ev.event && typeof ev.event === "object"))
    .slice(-MAX_VISIBLE);

  return (
    <div className="space-y-2">
      {/* Header row */}
      <div className="flex items-center gap-2">
        <Bot className="h-3.5 w-3.5 text-blue-400 shrink-0" />
        <span className="text-xs font-medium text-foreground/90 truncate">
          {agentId} — {completed ? "done" : "running"}
        </span>
        {/* Connection dot */}
        <span
          className={cn(
            "ml-auto h-2 w-2 rounded-full shrink-0",
            connected ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40",
          )}
        />
      </div>

      {/* Event list */}
      <div className="space-y-0.5 max-h-48 overflow-y-auto">
        {visibleEvents.length === 0 ? (
          <div className="text-xs text-muted-foreground italic">
            {completed ? "No events captured." : "Waiting for events…"}
          </div>
        ) : (
          visibleEvents.map((ev, i) => <EventRow key={`ev-${i}-${ev.event_type ?? "e"}`} ev={ev} />)
        )}
      </div>

      {/* Footer status */}
      {completed ? (
        <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="h-3 w-3" />
          <span>Completed · {events.length} event{events.length !== 1 ? "s" : ""}</span>
        </div>
      ) : connected ? (
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Streaming…</span>
        </div>
      ) : null}
    </div>
  );
}
