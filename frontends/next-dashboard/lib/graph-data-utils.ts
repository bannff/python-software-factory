import type { GraphLink, GraphNode } from "@/lib/types";
import { deriveGraphNodeDisplayName } from "@/lib/graph-node-display";
import { unwrapToolResult } from "@companion-x/shared-renderer";

/** Node type → color mapping for real Neo4j entity types. */
const TYPE_COLORS: Record<string, string> = {
  Agent: "#3b82f6", Brick: "#a855f7", User: "#06b6d4", Session: "#38bdf8",
  KBDocument: "#10b981", Memory: "#8b5cf6", memory: "#8b5cf6", ToolInvocation: "#f97316", Event: "#eab308",
  EvalSuite: "#ec4899", EvalRun: "#ec4899", Finding: "#ef4444", Concept: "#6366f1",
  SwarmRun: "#14b8a6", Threat: "#f43f5e", SecurityFinding: "#f43f5e",
  ThreatModel: "#f43f5e", Application: "#0ea5e9", SecurityApp: "#0ea5e9",
  Project: "#22d3ee", IamRole: "#ef4444", Lambda: "#f59e0b", SNS: "#ec4899",
  SQS: "#d946ef", DynamoDB: "#f97316", S3: "#22c55e", Neo4j: "#4ade80",
  AWSResource: "#f59e0b", CVE: "#dc2626", Vulnerability: "#dc2626", default: "#6b7280",
};

export interface GraphData { nodes: GraphNode[]; links: GraphLink[] }
export interface GraphStats { node_count: number; edge_count: number }

export const MAX_NEIGHBOR_LIMIT = 200;
export const DEFAULT_NEIGHBOR_LIMIT = 20;

export function colorForType(type: string): string {
  return TYPE_COLORS[type] ?? TYPE_COLORS.default;
}

/** Unwrap both the API response and the canonical typed MCP data envelope. */
export function unwrap(raw: unknown): unknown {
  return unwrapToolResult(raw, "Graph request failed");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function graphNodeFromEntity(
  entity: Record<string, unknown>, fallbackId?: string,
): GraphNode {
  const id = String(entity.id ?? fallbackId ?? Math.random());
  const type = String(entity.type ?? "default");
  const properties = isRecord(entity.properties) ? entity.properties : {};
  return {
    id, name: deriveGraphNodeDisplayName(id, type, properties), type,
    color: colorForType(type), val: 1, properties,
  };
}

/** Build deduplicated node/link additions from a neighbors response. */
export function collectNeighbors(
  sourceId: string, neighbors: unknown[], seenNodes: Set<string>, seenLinks: Set<string>,
): GraphData {
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];
  for (const rawNeighbor of neighbors) {
    if (!isRecord(rawNeighbor)) continue;
    const neighbor = rawNeighbor;
    const id = String(neighbor.id ?? "");
    if (!id) continue;
    if (!seenNodes.has(id)) {
      seenNodes.add(id);
      nodes.push(graphNodeFromEntity(neighbor, id));
    }
    const relation = typeof neighbor.relationship_type === "string"
      ? neighbor.relationship_type : "RELATED_TO";
    const key = `${sourceId}-${relation}-${id}`;
    if (!seenLinks.has(key)) {
      seenLinks.add(key);
      links.push({ source: sourceId, target: id, label: relation });
    }
  }
  return { nodes, links };
}

export function positiveLimit(value: number): number {
  const normalized = Number.isFinite(value) ? Math.floor(value) : DEFAULT_NEIGHBOR_LIMIT;
  return Math.min(MAX_NEIGHBOR_LIMIT, Math.max(1, normalized));
}
