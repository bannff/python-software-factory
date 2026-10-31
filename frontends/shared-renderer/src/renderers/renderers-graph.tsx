"use client";

import React, { useState, useCallback, useRef, useEffect, Suspense } from "react";
import { useGraphData } from "../lib/use-graph-data";
import type { GraphNode } from "../lib/graph-types";
import type { RendererProps } from "./renderer-types";

// React.lazy replaces next/dynamic(..., { ssr: false }). GraphViewer only
// renders under "use client" (no SSR pass), so a client-only lazy import is
// behaviour-equivalent to the old dynamic({ ssr: false }) (Track 6,
// bd:python-factory-ons71). react-force-graph-2d's default export is the
// component; cast keeps the permissive prop surface next/dynamic gave us.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ForceGraph2D = React.lazy(() => import("react-force-graph-2d")) as unknown as React.ComponentType<any>;

interface RecentRun { run_id: string; status: string; started_at: string }

/**
 * GraphViewerRenderer — renders a graph_viewer component from brick view JSON.
 * Reads data_tool / neighbors_tool from props, loads via MCP, renders ForceGraph2D.
 * Click a node to expand its neighbors. When a Run filter is selected, switches
 * to left-to-right DAG layout to render the workflow execution path.
 */
export function GraphViewerRenderer({ node }: RendererProps) {
  const { max_nodes = 100 } = node.props as {
    data_tool?: string; neighbors_tool?: string;
    max_nodes?: number; show_labels?: boolean;
  };
  const {
    data, loading, error, loadTopology, expandNode, reset,
    loadRunTopology, listRecentRuns,
  } = useGraphData();
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string>("");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);

  /* Auto-load on mount */
  useEffect(() => { loadTopology(); }, [loadTopology]);
  useEffect(() => {
    if (data.nodes.length > 0) setTimeout(() => graphRef.current?.zoomToFit(400, 40), 300);
  }, [data.nodes.length]);

  /* Refresh the run dropdown whenever the topology view is re-loaded */
  useEffect(() => {
    listRecentRuns(20).then(setRecentRuns).catch(() => {});
  }, [listRecentRuns]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleClick = useCallback((n: any) => {
    setSelected(n as GraphNode);
    if (!activeRunId && data.nodes.length < max_nodes) expandNode(n.id);
  }, [expandNode, data.nodes.length, max_nodes, activeRunId]);

  const handleRunChange = useCallback((runId: string) => {
    setActiveRunId(runId);
    if (runId) {
      loadRunTopology(runId);
    } else {
      reset();
      loadTopology();
    }
  }, [loadRunTopology, loadTopology, reset]);

  return (
    <div className="rounded-lg border bg-card/30 overflow-hidden" style={{ height: 480 }}>
      <div className="flex items-center justify-between border-b border-border/50 px-3 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          {data.nodes.length} nodes · {data.links.length} edges
          {loading && " · loading…"}
          {activeRunId && ` · run ${activeRunId.slice(0, 8)}`}
        </span>
        <div className="flex gap-1 items-center">
          <select
            value={activeRunId}
            onChange={(e) => handleRunChange(e.target.value)}
            className="rounded border border-border/50 bg-background px-2 py-0.5 text-xs text-muted-foreground"
            title="Filter by workflow run"
          >
            <option value="">All</option>
            {recentRuns.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)} · {r.status}
              </option>
            ))}
          </select>
          <button onClick={() => graphRef.current?.zoomToFit(400, 40)}
            className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent/50">Fit</button>
          <button onClick={() => { setActiveRunId(""); reset(); loadTopology(); }}
            className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent/50">Reset</button>
        </div>
      </div>
      {error && <div className="px-3 py-1 text-xs text-destructive">{error}</div>}
      <div className="flex" style={{ height: 440 }}>
        <div className="flex-1">
          <Suspense fallback={null}>
            <ForceGraph2D
              ref={graphRef}
              graphData={data}
              nodeLabel="name"
              nodeColor="color"
              nodeVal="val"
              nodeRelSize={5}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              linkLabel="label"
              linkColor={() => "rgba(148,163,184,0.3)"}
              onNodeClick={handleClick}
              backgroundColor="rgba(0,0,0,0)"
              dagMode={activeRunId ? "lr" : undefined}
              dagLevelDistance={activeRunId ? 120 : undefined}
              d3VelocityDecay={activeRunId ? 0.4 : 0.4}
            />
          </Suspense>
        </div>
        {selected && (
          <div className="w-52 border-l border-border/50 p-2 overflow-y-auto text-xs">
            <div className="flex justify-between mb-1">
              <span className="font-semibold truncate">{selected.name}</span>
              <button onClick={() => setSelected(null)} className="text-muted-foreground">✕</button>
            </div>
            <div className="text-muted-foreground space-y-0.5">
              <div>Type: {selected.type}</div>
              <div>ID: {selected.id}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
