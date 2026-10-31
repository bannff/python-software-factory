"use client";

import { useCallback, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import type { BoundedGraphContext, GraphNode } from "@/lib/types";
import {
  collectNeighbors, DEFAULT_NEIGHBOR_LIMIT, graphNodeFromEntity, positiveLimit, unwrap,
  type GraphData, type GraphStats,
} from "@/lib/graph-data-utils";

export { colorForType } from "@/lib/graph-data-utils";
export type { GraphData, GraphStats } from "@/lib/graph-data-utils";

const EXCLUDED_TYPES = new Set(["Document", "__Entity__", "Memory", "memory"]);
type EntityPayload = Record<string, unknown>;

function entityFromResult(result: EntityPayload | null): EntityPayload | null {
  if (!result || result.ok === false || result.found === false) return null;
  return (result.entity ?? result) as EntityPayload;
}

export function useGraphData(scoped = false) {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loadedContext, setLoadedContext] = useState<BoundedGraphContext | null>(null);
  const seenNodes = useRef(new Set<string>());
  const seenLinks = useRef(new Set<string>());
  const requestRef = useRef(0);

  const loadStats = useCallback(async () => {
    try {
      const result = unwrap(await callTool("graph_get_stats", {})) as Record<string, number>;
      setStats({ node_count: result?.node_count ?? 0, edge_count: result?.edge_count ?? 0 });
    } catch { /* non-critical */ }
  }, []);

  const beginLoad = useCallback(() => {
    const request = ++requestRef.current;
    setLoading(true);
    setError(null);
    setLoadedContext(null);
    seenNodes.current.clear();
    seenLinks.current.clear();
    return request;
  }, []);

  const loadTopology = useCallback(async (entityType?: string, nameQuery?: string) => {
    if (scoped) return;
    const request = beginLoad();
    try {
      void loadStats();
      const args: Record<string, unknown> = { limit: 300 };
      if (entityType) args.entity_type = entityType;
      if (nameQuery) args.properties = { name: nameQuery };
      const result = unwrap(await callTool("graph_find_entities", args)) as EntityPayload;
      if (request !== requestRef.current) return;
      const entities = (result?.entities ?? (Array.isArray(result) ? result : [])) as EntityPayload[];
      const nodes: GraphNode[] = [];
      for (const entity of entities) {
        const node = graphNodeFromEntity(entity);
        if (seenNodes.current.has(node.id) || (!entityType && EXCLUDED_TYPES.has(node.type))) continue;
        seenNodes.current.add(node.id);
        nodes.push(node);
      }
      setData({ nodes, links: [] });
    } catch (err) {
      if (request === requestRef.current) setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      if (request === requestRef.current) { setLoading(false); setHasLoaded(true); }
    }
  }, [beginLoad, loadStats, scoped]);

  const loadRunTopology = useCallback(async (runId: string) => {
    const request = beginLoad();
    try {
      const result = unwrap(await callTool("graph_get_run_topology", { run_id: runId, limit: 200 })) as EntityPayload;
      if (request !== requestRef.current) return;
      const nodes = ((result?.nodes ?? []) as EntityPayload[]).map((entity) => graphNodeFromEntity(entity));
      const links = ((result?.edges ?? []) as EntityPayload[]).map((edge) => ({
        source: String(edge.source ?? ""), target: String(edge.target ?? ""),
        label: typeof edge.type === "string" ? edge.type : "RELATED_TO",
      })).filter((link) => link.source && link.target);
      setData({ nodes, links });
    } catch (err) {
      if (request === requestRef.current) setError(err instanceof Error ? err.message : "Failed to load run topology");
    } finally {
      if (request === requestRef.current) { setLoading(false); setHasLoaded(true); }
    }
  }, [beginLoad]);

  const loadGraphContext = useCallback(async (
    queryRef: string, neighborhoodLimit: number, selectedRef = queryRef,
  ): Promise<GraphNode | null> => {
    if (scoped) return null;
    const request = beginLoad();
    const limit = positiveLimit(neighborhoodLimit);
    setData({ nodes: [], links: [] });
    try {
      void loadStats();
      const refs = [...new Set([queryRef, selectedRef])];
      const [results, neighborResult] = await Promise.all([
        Promise.all(refs.map(async (entityId) => unwrap(await callTool("graph_get_entity", { entity_id: entityId })) as EntityPayload)),
        callTool("graph_get_neighbors", { entity_id: queryRef, limit }).then(unwrap) as Promise<EntityPayload | null>,
      ]);
      if (request !== requestRef.current) return null;
      if (!neighborResult) throw new Error(`Graph neighborhood ${queryRef} was not found`);
      const nodes = results.map(entityFromResult).filter(Boolean).map((entity) => graphNodeFromEntity(entity as EntityPayload));
      nodes.forEach((node) => seenNodes.current.add(node.id));
      const neighbors = ((neighborResult.neighbors ?? []) as unknown[]).slice(0, limit);
      const additions = collectNeighbors(queryRef, neighbors, seenNodes.current, seenLinks.current);
      const allNodes = [...nodes, ...additions.nodes];
      const selected = allNodes.find((node) => node.id === selectedRef) ?? null;
      const queryNode = allNodes.find((node) => node.id === queryRef);
      if (!queryNode || !selected) throw new Error(`Graph entity ${selectedRef} was not found`);
      setLoadedContext({ query_ref: queryRef, neighborhood_limit: limit });
      setData({ nodes: allNodes, links: additions.links });
      return selected;
    } catch (err) {
      if (request === requestRef.current) setError(err instanceof Error ? err.message : "Failed to restore graph context");
      return null;
    } finally {
      if (request === requestRef.current) { setLoading(false); setHasLoaded(true); }
    }
  }, [beginLoad, loadStats, scoped]);

  const expandNode = useCallback(async (nodeId: string, neighborhoodLimit?: number) => {
    if (scoped) return false;
    const limit = positiveLimit(neighborhoodLimit ?? DEFAULT_NEIGHBOR_LIMIT);
    setExpanding(true);
    try {
      const result = unwrap(await callTool("graph_get_neighbors", { entity_id: nodeId, limit })) as EntityPayload | null;
      if (!result) return false;
      const neighbors = ((result.neighbors ?? []) as unknown[]).slice(0, limit);
      const additions = collectNeighbors(nodeId, neighbors, seenNodes.current, seenLinks.current);
      if (additions.nodes.length || additions.links.length) {
        setData((prev) => ({ nodes: [...prev.nodes, ...additions.nodes], links: [...prev.links, ...additions.links] }));
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to expand node");
      return false;
    } finally { setExpanding(false); }
  }, [scoped]);

  const listRecentRuns = useCallback(async (limit = 20) => {
    const result = unwrap(await callTool("graph_list_recent_runs", { limit })) as EntityPayload;
    return ((result?.runs ?? []) as EntityPayload[]).map((run) => ({
      run_id: String(run.run_id ?? ""), status: String(run.status ?? "unknown"), started_at: String(run.started_at ?? ""),
    })).filter((run) => run.run_id);
  }, []);

  const reset = useCallback(() => {
    requestRef.current += 1; seenNodes.current.clear(); seenLinks.current.clear();
    setData({ nodes: [], links: [] }); setStats(null); setLoadedContext(null); setError(null); setHasLoaded(false);
  }, []);
  const pushData = useCallback((incoming: GraphData) => setData((prev) => ({ nodes: [...prev.nodes, ...incoming.nodes], links: [...prev.links, ...incoming.links] })), []);

  return { data, loading, hasLoaded, expanding, error, stats, loadedContext, loadTopology, loadGraphContext, expandNode, pushData, reset, loadRunTopology, listRecentRuns };
}
