"use client";

import { useState, useCallback, useRef } from "react";
import { useBridge } from "../bridge-adapter-context";
import type { GraphNode, GraphLink } from "./graph-types";

const TYPE_COLORS: Record<string, string> = {
  Agent:           "#3b82f6",
  Brick:           "#a855f7",
  User:            "#06b6d4",
  Session:         "#38bdf8",
  KBDocument:      "#10b981",
  Memory:          "#8b5cf6",
  ToolInvocation:  "#f97316",
  Event:           "#eab308",
  EvalSuite:       "#ec4899",
  EvalRun:         "#ec4899",
  Finding:         "#ef4444",
  Concept:         "#6366f1",
  SwarmRun:        "#14b8a6",
  Threat:          "#f43f5e",
  SecurityFinding: "#f43f5e",
  ThreatModel:     "#f43f5e",
  Application:     "#0ea5e9",
  SecurityApp:     "#0ea5e9",
  Project:         "#22d3ee",
  IamRole:         "#ef4444",
  Lambda:          "#f59e0b",
  SNS:             "#ec4899",
  SQS:             "#d946ef",
  DynamoDB:        "#f97316",
  S3:              "#22c55e",
  Neo4j:           "#4ade80",
  AWSResource:     "#f59e0b",
  CVE:             "#dc2626",
  Vulnerability:   "#dc2626",
  default:         "#6b7280",
};

export function colorForType(type: string): string {
  return TYPE_COLORS[type] ?? TYPE_COLORS.default;
}

export interface GraphData { nodes: GraphNode[]; links: GraphLink[] }
export interface GraphStats { node_count: number; edge_count: number }

const EXCLUDED_TYPES = new Set(["Document", "__Entity__", "Memory"]);

function deriveGraphNodeDisplayName(
  id: string,
  type: string,
  properties: Record<string, unknown> | undefined,
): string {
  const props = properties ?? {};
  if (typeof props.name === "string" && props.name !== "") return props.name;
  if (typeof props.tool_name === "string" && props.tool_name !== "") return props.tool_name;
  if (typeof props.brick_name === "string" && props.brick_name !== "") return props.brick_name;
  if (typeof props.agent_id === "string" && props.agent_id !== "") return `agent:${props.agent_id}`;
  if (typeof props.principal_id === "string" && props.principal_id !== "") return `user:${props.principal_id}`;
  if (typeof props.workflow_run_id === "string" && props.workflow_run_id !== "") {
    return `run:${String(props.workflow_run_id).slice(0, 8)}`;
  }
  if (type === "Session" && id.startsWith("session-")) {
    return `session:${id.slice("session-".length, "session-".length + 8)}`;
  }
  if (type === "ToolInvocation" && id.startsWith("tool-inv-")) {
    return `tool:${id.slice("tool-inv-".length, "tool-inv-".length + 8)}`;
  }
  return id;
}

function unwrap(raw: unknown): unknown {
  const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
  return parsed?.result ?? parsed;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function collectNeighbors(
  sourceId: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  neighbors: any[],
  seenNodes: Set<string>,
  seenLinks: Set<string>,
): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];
  for (const n of neighbors) {
    const id = n.id ?? String(Math.random());
    if (!seenNodes.has(id)) {
      seenNodes.add(id);
      const type = n.type ?? "default";
      nodes.push({
        id, name: deriveGraphNodeDisplayName(id, type, n.properties ?? {}), type,
        color: colorForType(type), val: 1, properties: n.properties ?? {},
      });
    }
    const rel = n.relationship_type ?? "RELATED_TO";
    const key = `${sourceId}-${rel}-${id}`;
    if (!seenLinks.has(key)) {
      seenLinks.add(key);
      links.push({ source: sourceId, target: id, label: rel });
    }
  }
  return { nodes, links };
}

export function useGraphData() {
  const { callTool } = useBridge();
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const seenNodes = useRef(new Set<string>());
  const seenLinks = useRef(new Set<string>());

  const loadStats = useCallback(async () => {
    try {
      const r = unwrap(await callTool("graph_get_stats", {})) as Record<string, number>;
      setStats({ node_count: r?.node_count ?? 0, edge_count: r?.edge_count ?? 0 });
    } catch { /* non-critical */ }
  }, [callTool]);

  const loadTopology = useCallback(async (entityType?: string, nameQuery?: string) => {
    setLoading(true);
    setError(null);
    seenNodes.current.clear();
    seenLinks.current.clear();

    try {
      loadStats();

      const args: Record<string, unknown> = { limit: 300 };
      if (entityType) args.entity_type = entityType;
      if (nameQuery) args.properties = { name: nameQuery };
      const result = unwrap(await callTool("graph_find_entities", args)) as Record<string, unknown>;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const entities = (result?.entities ?? (Array.isArray(result) ? result : [])) as any[];

      const nodes: GraphNode[] = [];
      for (const e of entities) {
        const id = e.id ?? String(Math.random());
        if (seenNodes.current.has(id)) continue;
        const type = e.type ?? "default";
        if (!entityType && EXCLUDED_TYPES.has(type)) continue;
        seenNodes.current.add(id);
        nodes.push({
          id, name: deriveGraphNodeDisplayName(id, type, e.properties ?? {}), type,
          color: colorForType(type), val: 1, properties: e.properties ?? {},
        });
      }
      setData({ nodes, links: [] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, [callTool, loadStats]);

  const expandNode = useCallback(async (nodeId: string) => {
    setExpanding(true);
    try {
      const result = unwrap(await callTool("graph_get_neighbors", { entity_id: nodeId })) as Record<string, unknown>;
      const { nodes: newNodes, links: newLinks } = collectNeighbors(
        nodeId, (result?.neighbors ?? []) as any[], seenNodes.current, seenLinks.current,
      );
      if (newNodes.length > 0 || newLinks.length > 0) {
        setData((prev) => ({
          nodes: [...prev.nodes, ...newNodes],
          links: [...prev.links, ...newLinks],
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to expand node");
    } finally {
      setExpanding(false);
    }
  }, [callTool]);

  const loadRunTopology = useCallback(async (runId: string) => {
    setLoading(true);
    setError(null);
    seenNodes.current.clear();
    seenLinks.current.clear();
    try {
      const result = unwrap(await callTool("graph_get_run_topology", { run_id: runId, limit: 200 })) as Record<string, unknown>;
      const rawNodes = (result?.nodes ?? []) as any[];
      const rawEdges = (result?.edges ?? []) as any[];
      const nodes: GraphNode[] = [];
      for (const n of rawNodes) {
        const id = n.id ?? String(Math.random());
        if (seenNodes.current.has(id)) continue;
        const type = n.type ?? "default";
        seenNodes.current.add(id);
        nodes.push({
          id, name: deriveGraphNodeDisplayName(id, type, n.properties ?? {}), type,
          color: colorForType(type), val: 1, properties: n.properties ?? {},
        });
      }
      const links: GraphLink[] = [];
      for (const e of rawEdges) {
        const source = String(e.source ?? "");
        const target = String(e.target ?? "");
        const rel = e.type ?? "RELATED_TO";
        const key = `${source}-${rel}-${target}`;
        if (seenLinks.current.has(key)) continue;
        seenLinks.current.add(key);
        links.push({ source, target, label: rel });
      }
      setData({ nodes, links });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run topology");
    } finally {
      setLoading(false);
    }
  }, [callTool]);

  const listRecentRuns = useCallback(async (limit = 20): Promise<Array<{ run_id: string; status: string; started_at: string }>> => {
    try {
      const result = unwrap(await callTool("graph_list_recent_runs", { limit })) as Record<string, unknown>;
      return ((result?.runs ?? []) as any[]).map((r) => ({
        run_id: String(r.run_id ?? ""),
        status: String(r.status ?? "unknown"),
        started_at: String(r.started_at ?? ""),
      })).filter((r) => r.run_id);
    } catch {
      return [];
    }
  }, [callTool]);

  const pushData = useCallback((incoming: GraphData) => {
    setData((prev) => ({
      nodes: [...prev.nodes, ...incoming.nodes],
      links: [...prev.links, ...incoming.links],
    }));
  }, []);

  const reset = useCallback(() => {
    seenNodes.current.clear();
    seenLinks.current.clear();
    setData({ nodes: [], links: [] });
    setStats(null);
    setError(null);
  }, []);

  return { data, loading, expanding, error, stats, loadTopology, expandNode, pushData, reset, loadRunTopology, listRecentRuns };
}
