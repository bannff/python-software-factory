"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import { useGraphData } from "@/lib/hooks/use-graph-data";
import { useGraphRestore } from "@/lib/hooks/use-graph-restore";
import { useGraphRunFocus } from "@/lib/hooks/use-graph-run-focus";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { filterGraphData, graphTypeCounts } from "@/lib/graph-view-data";
import { reduceRunActivity } from "@/lib/run-activity";
import { a2uiSlotToGraphData, type CanvasState } from "@/lib/copilotkit/a2ui-canvas-slots";
import type { ActiveToolCall, GraphNode, Step } from "@/lib/types";
import { GraphNodeDetail } from "./graph-node-detail";
import { EmptyGraph } from "./graph-empty-state";
import { GraphTypeFilters } from "./graph-type-filters";
import { GraphToolbar } from "./graph-toolbar";
import { RunsSelector } from "./runs-selector";
import { makeNodePainter, nodePointerAreaPaint } from "./graph-canvas-painters";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

interface GraphViewProps {
  steps: Step[];
  toolCalls: ActiveToolCall[];
  agentState: { canvas?: CanvasState } & Record<string, unknown>;
}

export default function GraphView({ agentState }: GraphViewProps) {
  const workbench = useWorkbenchContext();
  const scoped = workbench.focusedRunId !== null;
  const graph = useGraphData(scoped);
  const { entries: liveEntries } = useLiveToolStream();
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"type" | "name">("type");
  const [displaySource, setDisplaySource] = useState<"painted" | "queried">("painted");
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [dims, setDims] = useState({ w: 800, h: 600 });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const previousFocusedRunId = useRef(workbench.focusedRunId);

  const clearSelected = useCallback(() => setSelected(null), []);
  const replaceWithQueriedData = useCallback(() => {
    setDisplaySource("queried");
    setSelected(null);
    setHiddenTypes(new Set());
    setActivePreset(null);
  }, []);
  useGraphRunFocus(workbench.focusedRunId, graph.loadTopology, graph.loadRunTopology, clearSelected);

  useEffect(() => {
    if (previousFocusedRunId.current === workbench.focusedRunId) return;
    previousFocusedRunId.current = workbench.focusedRunId;
    replaceWithQueriedData();
  }, [workbench.focusedRunId, replaceWithQueriedData]);

  const paintedGraph = useMemo(
    () => a2uiSlotToGraphData(agentState.canvas?.graph),
    [agentState.canvas?.graph],
  );
  const rawData = workbench.focusedRunId || displaySource === "queried"
    ? graph.data
    : paintedGraph ?? graph.data;
  const typeCounts = useMemo(() => graphTypeCounts(rawData.nodes), [rawData.nodes]);
  const graphData = useMemo(() => filterGraphData(rawData, hiddenTypes), [rawData, hiddenTypes]);
  const activity = useMemo(() => reduceRunActivity(liveEntries), [liveEntries]);

  useGraphRestore({
    request: workbench.graphRestoreRequest,
    data: scoped ? graph.data : graphData,
    scoped,
    loadedContext: graph.loadedContext,
    selected,
    onSelect: setSelected,
    loadGraphContext: graph.loadGraphContext,
    expandNode: graph.expandNode,
    acknowledgeGraphRestore: workbench.acknowledgeGraphRestore,
    reportNavigationStatus: workbench.reportNavigationStatus,
  });

  const toggleType = useCallback((type: string) => {
    setHiddenTypes((previous) => {
      const next = new Set(previous);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }, []);
  const loadPreset = useCallback((entityType: string) => {
    replaceWithQueriedData();
    setSearchMode("type");
    setQuery(entityType);
    setActivePreset(entityType);
    void graph.loadTopology(entityType);
  }, [replaceWithQueriedData, graph.loadTopology]);
  const handleSearch = useCallback(() => {
    const value = query.trim();
    replaceWithQueriedData();
    if (searchMode === "name") void graph.loadTopology(undefined, value || undefined);
    else void graph.loadTopology(value || undefined);
  }, [query, searchMode, replaceWithQueriedData, graph.loadTopology]);
  const selectNode = useCallback((node: GraphNode) => {
    setSelected(node);
    if (!scoped) void graph.expandNode(node.id);
  }, [scoped, graph.expandNode]);
  const selectNodeById = useCallback((id: string) => {
    const node = rawData.nodes.find((item) => item.id === id);
    if (node) selectNode(node);
  }, [rawData.nodes, selectNode]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleNodeClick = useCallback((node: any) => {
    selectNode(node as GraphNode);
  }, [selectNode]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const measure = () => {
      const { width, height } = element.getBoundingClientRect();
      if (width > 0 && height > 0) setDims({ w: Math.floor(width), h: Math.floor(height) });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const reload = useCallback(() => {
    replaceWithQueriedData();
    if (workbench.focusedRunId) void graph.loadRunTopology(workbench.focusedRunId);
    else void graph.loadTopology();
  }, [workbench.focusedRunId, replaceWithQueriedData, graph.loadRunTopology, graph.loadTopology]);
  const reset = useCallback(() => {
    replaceWithQueriedData();
    if (workbench.focusedRunId) workbench.clearRunFocus();
    else void graph.loadTopology();
  }, [workbench, replaceWithQueriedData, graph.loadTopology]);
  const focusRun = useCallback((runId: string) => {
    replaceWithQueriedData();
    workbench.focusRun(runId);
  }, [workbench, replaceWithQueriedData]);
  const clearRunFocus = useCallback(() => {
    replaceWithQueriedData();
    workbench.clearRunFocus();
  }, [workbench, replaceWithQueriedData]);
  const paintNode = useMemo(() => makeNodePainter(selected?.id ?? null), [selected?.id]);

  return (
    <div className="flex h-full flex-col" style={{ minHeight: 0 }}>
      <GraphToolbar
        query={query} searchMode={searchMode} activePreset={activePreset} loading={graph.loading}
        broadControlsDisabled={scoped}
        runsSelector={<RunsSelector listRecentRuns={graph.listRecentRuns} focusedRunId={workbench.focusedRunId} onFocusRun={focusRun} onClear={clearRunFocus} />}
        activity={activity} onQueryChange={setQuery}
        onToggleSearchMode={() => setSearchMode((mode) => mode === "type" ? "name" : "type")}
        onSearch={handleSearch} onLoadPreset={loadPreset}
        onFit={() => graphRef.current?.zoomToFit(400, 40)} onReset={reset}
        stats={workbench.focusedRunId ? null : graph.stats}
        visibleNodes={graphData.nodes.length} visibleLinks={graphData.links.length}
      />
      <GraphTypeFilters typeCounts={typeCounts} hiddenTypes={hiddenTypes} visibleCount={graphData.nodes.length} onToggleType={toggleType} />
      <div className="relative flex flex-1 bg-background" style={{ minHeight: 0 }}>
        {graph.error && <div className="absolute inset-x-0 top-2 z-10 mx-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">{graph.error}</div>}
        <div ref={containerRef} data-testid="graph-viewport" className="relative flex-1" style={{ minHeight: 0 }}>
          {graphData.nodes.length > 0 ? (
            <ForceGraph2D ref={graphRef} graphData={graphData} width={dims.w} height={dims.h}
              nodeLabel="name" nodeColor="color" nodeVal="val" nodeRelSize={6}
              linkDirectionalArrowLength={4} linkDirectionalArrowRelPos={1}
              linkDirectionalParticles={1} linkDirectionalParticleSpeed={0.004}
              linkLabel="label" linkColor={() => "rgba(148,163,184,0.25)"}
              onNodeClick={handleNodeClick} nodeCanvasObject={paintNode}
              nodePointerAreaPaint={nodePointerAreaPaint} backgroundColor="rgba(0,0,0,0)"
              autoPauseRedraw={false} cooldownTicks={Infinity}
            />
          ) : <EmptyGraph loading={graph.loading} hasLoaded={graph.hasLoaded} focusedRunId={workbench.focusedRunId} onReload={reload} />}
        </div>
        <AnimatePresence>{selected && <GraphNodeDetail node={selected} edges={graphData.links} onClose={() => setSelected(null)} onOpenMetrics={workbench.openMetrics} onNodeSelect={selectNodeById} />}</AnimatePresence>
      </div>
    </div>
  );
}
