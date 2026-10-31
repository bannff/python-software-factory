"use client";

import React from "react";
import { AlertTriangle, Link2 } from "lucide-react";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { resolve } from "./renderers-item-list-utils";
import { useToolData } from "./use-tool-data";

const MAX_NODES = 100;

type LineageNode = {
  node_id: string;
  entity_id?: string | null;
  entity_type?: string;
  source?: string;
  source_ref?: string;
  evidence?: string;
};

type LineageEdge = {
  source: string;
  target: string;
  relation?: string;
  verified?: boolean;
};

type LineageData = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  missing_links: Array<{ node_id?: string; kinds?: string[] }>;
  truncated: boolean;
  dropped_edges: number;
};

export function normalizeLineageData(raw: unknown): LineageData {
  const input = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  const sourceNodes = Array.isArray(input.nodes) ? input.nodes as LineageNode[] : [];
  const nodes = [...sourceNodes]
    .filter((node) => typeof node?.node_id === "string")
    .sort((a, b) => a.node_id.localeCompare(b.node_id))
    .slice(0, MAX_NODES);
  const ids = new Set(nodes.map((node) => node.node_id));
  const sourceEdges = Array.isArray(input.edges) ? input.edges as LineageEdge[] : [];
  const edges = sourceEdges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .sort((a, b) => `${a.source}:${a.target}`.localeCompare(`${b.source}:${b.target}`));
  return {
    nodes,
    edges,
    missing_links: Array.isArray(input.missing_links)
      ? input.missing_links as LineageData["missing_links"] : [],
    truncated: input.truncated === true || sourceNodes.length > MAX_NODES,
    dropped_edges: sourceEdges.length - edges.length,
  };
}

function layersFor(data: LineageData): LineageNode[][] {
  const byId = new Map(data.nodes.map((node) => [node.node_id, node]));
  const incoming = new Map(data.nodes.map((node) => [node.node_id, 0]));
  const outgoing = new Map(data.nodes.map((node) => [node.node_id, [] as string[]]));
  data.edges.forEach((edge) => {
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
    outgoing.get(edge.source)?.push(edge.target);
  });
  const depth = new Map<string, number>();
  const queue = [...byId.keys()].filter((id) => incoming.get(id) === 0).sort();
  queue.forEach((id) => depth.set(id, 0));
  while (queue.length) {
    const id = queue.shift() as string;
    for (const target of (outgoing.get(id) ?? []).sort()) {
      depth.set(target, Math.max(depth.get(target) ?? 0, (depth.get(id) ?? 0) + 1));
      incoming.set(target, (incoming.get(target) ?? 1) - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
    queue.sort();
  }
  [...byId.keys()].filter((id) => !depth.has(id)).sort().forEach((id) => depth.set(id, 0));
  const layers: LineageNode[][] = [];
  [...byId.values()].forEach((node) => {
    const index = depth.get(node.node_id) ?? 0;
    (layers[index] ??= []).push(node);
  });
  layers.forEach((layer) => layer.sort((a, b) => a.node_id.localeCompare(b.node_id)));
  return layers;
}

export function LineageRenderer({ node }: RendererProps) {
  const {
    data: staticData, data_tool, data_path, empty_message, className,
  } = node.props as {
    data?: unknown; data_tool?: string; data_path?: string;
    empty_message?: string; className?: string;
  };
  const { data: toolData, loading, error } = useToolData(data_tool);
  const raw = data_tool ? toolData : staticData ?? node.props;
  const selected = data_path && raw && typeof raw === "object"
    ? resolve(raw as Record<string, unknown>, data_path) : raw;
  const data = normalizeLineageData(selected);
  const layers = layersFor(data);

  if (loading) return <div className="h-48 animate-pulse rounded-lg border bg-muted/40" />;
  if (error) return <p className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{error}</p>;
  if (data.nodes.length === 0) {
    return <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">{empty_message ?? "No lineage evidence available."}</p>;
  }
  return (
    <section className={cn("space-y-3 rounded-lg border p-4", className)}>
      {(data.truncated || data.dropped_edges > 0) && (
        <div className="flex items-center gap-2 text-xs text-amber-500">
          <AlertTriangle className="h-4 w-4" />
          Showing at most {MAX_NODES} nodes; {data.dropped_edges} dangling or truncated edges omitted.
        </div>
      )}
      <div className="flex min-w-max items-start gap-6 overflow-x-auto" data-testid="lineage-layers">
        {layers.map((layer, index) => (
          <div key={index} className="w-56 shrink-0 space-y-2" data-layer={index}>
            {layer.map((item) => (
              <article key={item.node_id} className="rounded-md border bg-card p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{item.entity_type ?? "Entity"}</p>
                <p className="truncate text-sm font-semibold" title={item.source_ref}>{item.entity_id ?? item.source_ref ?? item.node_id}</p>
                <p className="mt-1 text-xs text-muted-foreground">{item.source}</p>
                {item.evidence && <p className="mt-2 text-xs">{item.evidence}</p>}
              </article>
            ))}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {data.edges.map((edge) => (
          <span key={`${edge.source}:${edge.target}:${edge.relation}`} className="inline-flex items-center gap-1 rounded bg-muted px-2 py-1 text-xs">
            <Link2 className="h-3 w-3" />{edge.relation ?? "RELATED"}
          </span>
        ))}
      </div>
      {data.missing_links.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Missing links: {data.missing_links.flatMap((item) => item.kinds ?? []).join(", ")}
        </div>
      )}
    </section>
  );
}
