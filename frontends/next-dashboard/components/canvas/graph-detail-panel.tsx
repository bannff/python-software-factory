"use client";

/**
 * GraphDetailPanel — split view: graph (top) + data list (bottom).
 * Select a row → graph updates. Click a graph node → deep link to its tab.
 * Uses react-force-graph-2d, useGraphData hook, framer-motion.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Maximize2, RotateCcw, X } from "lucide-react";
import { useGraphData, colorForType } from "@/lib/hooks/use-graph-data";
import type { GraphNode } from "@/lib/types";
import type { CanvasViewId } from "@/lib/types";
import dynamic from "next/dynamic";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

/** Map Neo4j entity types to Companion-X tab IDs. */
const TYPE_TO_TAB: Record<string, CanvasViewId> = {
  GameSession: "games",
  GameMove: "games",
  Finding: "findings",
  SecurityFinding: "findings",
  EvalRun: "evals",
  ToolInvocation: "timeline-v2",
  Session: "timeline-v2",
  Transaction: "blockchain",
  Wallet: "blockchain",
  Bounty: "blockchain",
  Block: "blockchain",
  Memory: "graph",
  KBDocument: "graph",
  Agent: "graph",
};

interface GraphDetailPanelProps {
  /** Entity ID to center the graph on. Null = empty state. */
  entityId: string | null;
  /** Entity type hint for initial load. */
  entityType?: string;
  /** Callback when user clicks a graph node to navigate. */
  onNavigate?: (viewId: CanvasViewId) => void;
  /** Height of the graph section in pixels. */
  graphHeight?: number;
  /** Children = the data list below the graph. */
  children: React.ReactNode;
}

export function GraphDetailPanel({
  entityId,
  entityType,
  onNavigate,
  graphHeight = 280,
  children,
}: GraphDetailPanelProps) {
  const { data, loading, expandNode, reset } = useGraphData();
  const [selected, setSelected] = useState<GraphNode | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 800, h: graphHeight });

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      setDims({ w: entry.contentRect.width, h: graphHeight });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [graphHeight]);

  // Load entity neighborhood when entityId changes
  useEffect(() => {
    if (!entityId) return;
    reset();
    (async () => {
      await expandNode(entityId);
      setTimeout(() => graphRef.current?.zoomToFit(400, 40), 300);
    })();
  }, [entityId, expandNode, reset]);

  const handleNodeClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      const n = node as GraphNode;
      setSelected(n);
      if (data.nodes.length < 200) expandNode(n.id);
    },
    [expandNode, data.nodes.length],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Graph section */}
      <div
        ref={containerRef}
        className="relative border-b border-border/30 bg-card/10"
        style={{ height: graphHeight, minHeight: graphHeight }}
      >
        {/* Controls */}
        <div className="absolute top-2 right-2 z-10 flex gap-1">
          <button
            onClick={() => graphRef.current?.zoomToFit(400, 40)}
            className="rounded-md bg-card/60 backdrop-blur-sm p-1.5 text-muted-foreground/50 hover:text-foreground/70 transition-colors"
            title="Fit to view"
          >
            <Maximize2 className="h-3 w-3" />
          </button>
          <button
            onClick={() => { reset(); setSelected(null); }}
            className="rounded-md bg-card/60 backdrop-blur-sm p-1.5 text-muted-foreground/50 hover:text-foreground/70 transition-colors"
            title="Reset graph"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>

        {/* Node count badge */}
        <div className="absolute top-2 left-2 z-10 text-[10px] text-muted-foreground/40 tabular-nums">
          {data.nodes.length} nodes · {data.links.length} edges
          {loading && " · loading…"}
        </div>

        {/* Empty state */}
        {!entityId && data.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground/30">
            Select an item below to see its graph
          </div>
        )}

        {/* Force graph */}
        {data.nodes.length > 0 && (
          <ForceGraph2D
            ref={graphRef}
            graphData={data}
            width={dims.w}
            height={dims.h}
            nodeLabel="name"
            nodeColor="color"
            nodeVal="val"
            nodeRelSize={5}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            linkLabel="label"
            linkColor={() => "rgba(148,163,184,0.2)"}
            onNodeClick={handleNodeClick}
            backgroundColor="rgba(0,0,0,0)"
          />
        )}

        {/* Selected node sidebar */}
        <AnimatePresence>
          {selected && (
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="absolute top-0 right-0 h-full w-48 border-l border-border/30 bg-card/80 backdrop-blur-md p-2 overflow-y-auto z-20"
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                  style={{ backgroundColor: colorForType(selected.type) + "20", color: colorForType(selected.type) }}
                >
                  {selected.type}
                </span>
                <button onClick={() => setSelected(null)} className="text-muted-foreground/40 hover:text-foreground/60">
                  <X className="h-3 w-3" />
                </button>
              </div>
              <p className="text-[11px] font-medium text-foreground/80 truncate mb-1">{selected.name}</p>
              <p className="text-[9px] text-muted-foreground/40 font-mono truncate mb-2">{selected.id}</p>
              {TYPE_TO_TAB[selected.type] && onNavigate && (
                <button
                  onClick={() => onNavigate(TYPE_TO_TAB[selected.type])}
                  className="w-full text-[10px] text-center py-1 rounded border border-border/40 text-muted-foreground/60 hover:text-foreground/80 hover:bg-accent/30 transition-colors"
                >
                  Open in {TYPE_TO_TAB[selected.type]} →
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Data list section */}
      <div className="flex-1 overflow-auto" style={{ minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}
