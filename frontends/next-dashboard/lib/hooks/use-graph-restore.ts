"use client";

import { useEffect, useRef, useState } from "react";
import type { GraphData } from "@/lib/graph-data-utils";
import { focusNavigationOrigin } from "@/lib/graph-navigation";
import type { BoundedGraphContext, GraphNode, NavigationRef } from "@/lib/types";

type LoadGraphContext = (
  queryRef: string, neighborhoodLimit: number, selectedRef: string,
) => Promise<GraphNode | null>;
type ExpandNode = (nodeId: string, neighborhoodLimit?: number) => Promise<boolean>;

interface GraphRestoreOptions {
  request: NavigationRef | null;
  data: GraphData;
  scoped?: boolean;
  loadedContext: BoundedGraphContext | null;
  selected: GraphNode | null;
  onSelect: (node: GraphNode) => void;
  loadGraphContext: LoadGraphContext;
  expandNode: ExpandNode;
  acknowledgeGraphRestore: (targetRef?: string, status?: string) => void;
  reportNavigationStatus: (status: string) => void;
}

function requestKey(request: NavigationRef, context: BoundedGraphContext): string {
  return JSON.stringify({
    version: request.version, surface: request.surface, target: request.target_ref,
    selected: request.graph_selected_ref, query: context.query_ref,
    limit: context.neighborhood_limit, focus: request.focus_origin?.token ?? null,
  });
}

/** Restore a Graph selection/context before clearing the workbench request. */
export function useGraphRestore({
  request, data, scoped = false, loadedContext, selected, onSelect, loadGraphContext, expandNode,
  acknowledgeGraphRestore, reportNavigationStatus,
}: GraphRestoreOptions): void {
  const attempted = useRef<NavigationRef | null>(null);
  const transaction = useRef<NavigationRef | null>(null);
  const [readyRequest, setReadyRequest] = useState<NavigationRef | null>(null);
  const latest = useRef({
    data, loadedContext, selected, onSelect, loadGraphContext, expandNode,
    acknowledgeGraphRestore, reportNavigationStatus,
  });
  latest.current = {
    data, loadedContext, selected, onSelect, loadGraphContext, expandNode,
    acknowledgeGraphRestore, reportNavigationStatus,
  };

  const context = request?.graph_context ?? null;
  const selectedRef = request?.graph_selected_ref ?? null;
  const key = request && context ? requestKey(request, context) : null;

  useEffect(() => {
    if (transaction.current !== request) {
      transaction.current = request;
      attempted.current = null;
      setReadyRequest(null);
    }
    const graphContext = request?.graph_context;
    const targetRef = request?.graph_selected_ref;
    if (!request || !graphContext || !targetRef || !key) return;
    if (attempted.current === request) return;
    attempted.current = request;
    let cancelled = false;
    let stage: "load" | "expand" = "load";

    const restore = async () => {
      try {
        const current = latest.current;
        let node = current.data.nodes.find((candidate) => candidate.id === targetRef) ?? null;
        if (scoped) {
          if (!node) {
            attempted.current = null;
            current.reportNavigationStatus(
              `Unable to restore Graph item ${request.label}; it is not present in the focused run.`,
            );
            return;
          }
          current.onSelect(node);
          setReadyRequest(request);
          return;
        }
        const contextMatches = current.loadedContext?.query_ref === graphContext.query_ref
          && current.loadedContext.neighborhood_limit === graphContext.neighborhood_limit;
        if (!node || !contextMatches) {
          node = await current.loadGraphContext(
            graphContext.query_ref, graphContext.neighborhood_limit, targetRef,
          );
        }
        if (cancelled || transaction.current !== request) return;
        if (!node) {
          attempted.current = null;
          current.reportNavigationStatus(
            `Unable to restore Graph item ${request.label}; the requested context is unavailable.`,
          );
          return;
        }
        current.onSelect(node);
        stage = "expand";
        const expanded = await current.expandNode(targetRef, graphContext.neighborhood_limit);
        if (cancelled || transaction.current !== request) return;
        if (!expanded) {
          attempted.current = null;
          current.reportNavigationStatus(
            `Unable to restore Graph item ${request.label}; its neighborhood is unavailable.`,
          );
          return;
        }
        setReadyRequest(request);
      } catch {
        if (cancelled || transaction.current !== request) return;
        attempted.current = null;
        latest.current.reportNavigationStatus(
          stage === "expand"
            ? `Unable to restore Graph item ${request.label}; its neighborhood is unavailable.`
            : `Unable to restore Graph item ${request.label}; the requested context is unavailable.`,
        );
      }
    };

    void restore();
    return () => { cancelled = true; };
  }, [request, key, scoped]);

  useEffect(() => {
    if (!request || !selectedRef || readyRequest !== request
      || latest.current.selected?.id !== selectedRef) return;
    const originToken = request.focus_origin?.token;
    const focused = originToken ? focusNavigationOrigin(originToken) : false;
    const focusStatus = originToken && focused
      ? " Focus restored to the initiating Graph control."
      : " Focus origin unavailable; use the Graph detail controls to continue.";
    latest.current.acknowledgeGraphRestore(
      selectedRef,
      `Returned to ${request.label}.${focusStatus}`,
    );
    setReadyRequest(null);
  }, [request, selected, selectedRef, readyRequest]);
}
