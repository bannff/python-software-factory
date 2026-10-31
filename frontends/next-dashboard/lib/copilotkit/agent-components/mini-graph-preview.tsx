"use client";

/**
 * <MiniGraphPreview /> — agent-summonable hop-1 neighborhood preview
 * (bd-kzsl Phase 1, component 1/3).
 *
 * Registered via `useComponent` in agent-components.tsx; the agent
 * emits a typed `mini_graph_preview` reference and CopilotKit renders
 * this inline. Hop-1 only — depth >1 is currently a hint, not honored
 * (would require recursive expansion via use-graph-data; defer until
 * the prompt-awareness follow-up).
 */

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Loader2, Network } from "lucide-react";
import { z } from "zod";
import { callTool } from "@/lib/api";
import { unwrap } from "@/lib/graph-data-utils";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export const MiniGraphArgs = z.object({
  entity_id: z.string().describe("The entity id to render the neighborhood of."),
  depth: z
    .number()
    .optional()
    .describe("Hop depth for the neighborhood (default 1; v1 ships hop-1 only)."),
});

interface MiniGraphData {
  nodes: Array<{ id: string; name: string; color: string }>;
  links: Array<{ source: string; target: string }>;
}

export function MiniGraphPreview({
  entity_id,
  depth: _depth,
}: z.infer<typeof MiniGraphArgs>) {
  const [state, setState] = useState<{
    data: MiniGraphData | null;
    loading: boolean;
    error?: string;
  }>({ data: null, loading: true });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await callTool("graph_get_neighbors", { entity_id, limit: 30 });
        if (cancelled) return;
        const result = unwrap(raw) as Record<string, unknown> | undefined;
        const neighbors = (result?.neighbors ?? []) as Array<Record<string, unknown>>;
        const nodes: MiniGraphData["nodes"] = [
          { id: entity_id, name: entity_id.slice(0, 24), color: "#a78bfa" },
        ];
        const links: MiniGraphData["links"] = [];
        for (const n of neighbors.slice(0, 30)) {
          const id = String(n.id ?? n.entity_id ?? "");
          if (!id || id === entity_id) continue;
          nodes.push({
            id,
            name: String(n.name ?? id).slice(0, 24),
            color: "#64748b",
          });
          links.push({ source: entity_id, target: id });
        }
        setState({ data: { nodes, links }, loading: false });
      } catch (e) {
        if (cancelled) return;
        setState({
          data: null,
          loading: false,
          error: e instanceof Error ? e.message : "fetch failed",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entity_id]);

  return (
    <div className="ml-11 my-2 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <Network className="h-3.5 w-3.5 text-violet-500" />
        <span className="text-xs font-medium text-foreground/90">Graph preview</span>
        <code className="ml-1 truncate rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
          {entity_id}
        </code>
      </div>
      <div className="relative h-[180px] w-full bg-background/40">
        {state.loading && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> Loading…
          </div>
        )}
        {!state.loading && state.error && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
            Could not load neighborhood: {state.error}
          </div>
        )}
        {!state.loading && state.data && state.data.nodes.length > 1 && (
          <ForceGraph2D
            graphData={state.data}
            width={400}
            height={180}
            nodeRelSize={4}
            nodeLabel="name"
            linkColor={() => "rgba(148, 163, 184, 0.4)"}
            enableZoomInteraction={false}
            enablePanInteraction={false}
          />
        )}
        {!state.loading &&
          state.data &&
          state.data.nodes.length <= 1 &&
          !state.error && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              No neighbors found.
            </div>
          )}
      </div>
    </div>
  );
}
