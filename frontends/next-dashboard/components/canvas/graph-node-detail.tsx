"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, X, FileText, Network } from "lucide-react";
import { cn } from "@/lib/utils";
import type { GraphNode, GraphLink, NavigationRef } from "@/lib/types";
import { navigationForGraphNode } from "@/lib/graph-navigation";
import { GraphMiniRadial } from "./graph-mini-radial";
import { RelGroup, type EdgeInfo } from "./graph-relationship-group";
import { NodeProperties, groupFor, type PropGroup } from "./graph-node-props";

type Tab = "properties" | "relationships";

export interface GraphNodeDetailProps {
  node: GraphNode;
  edges: GraphLink[];
  onClose: () => void;
  onNodeSelect?: (id: string) => void;
  onOpenMetrics?: (navigation: NavigationRef) => void;
}

const HIDDEN_PREFIXES = ["embedding", "structural", "n2v"];
function isHidden(key: string): boolean {
  return HIDDEN_PREFIXES.some((p) => key.startsWith(p));
}

function nodeId(endpoint: string | { id?: string }): string {
  return typeof endpoint === "string" ? endpoint : (endpoint.id ?? "");
}

export function GraphNodeDetail({
  node, edges, onClose, onNodeSelect, onOpenMetrics,
}: GraphNodeDetailProps) {
  const [tab, setTab] = useState<Tab>("properties");
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [node.id]);

  const navigation = useMemo(
    () => navigationForGraphNode(node),
    [node.id, node.name],
  );

  const filteredProps = useMemo(
    () => Object.entries(node.properties ?? {}).filter(([k]) => !isHidden(k)),
    [node.properties],
  );

  const propGroups = useMemo(() => {
    const groups: Record<PropGroup, Array<[string, unknown]>> = {
      identity: [], activity: [], metadata: [],
    };
    for (const [k, v] of filteredProps) groups[groupFor(k)].push([k, v]);
    return groups;
  }, [filteredProps]);

  const connectedEdges = useMemo(() => {
    const id = node.id;
    const grouped = new Map<string, EdgeInfo[]>();
    for (const link of edges) {
      const src = nodeId(link.source);
      const tgt = nodeId(link.target);
      if (src !== id && tgt !== id) continue;
      const label = link.label ?? "RELATED_TO";
      const direction: "→" | "←" = src === id ? "→" : "←";
      const otherId = src === id ? tgt : src;
      const otherObj = src === id ? link.target : link.source;
      const otherName =
        typeof otherObj === "object" && otherObj !== null
          ? ((otherObj as Record<string, unknown>).name as string) ?? ""
          : "";
      if (!grouped.has(label)) grouped.set(label, []);
      grouped.get(label)!.push({ direction, otherName, otherId });
    }
    return grouped;
  }, [node.id, edges]);

  const edgeCount = useMemo(() => {
    let c = 0;
    connectedEdges.forEach((v) => (c += v.length));
    return c;
  }, [connectedEdges]);

  const radialEdges = useMemo(() => {
    const result: Array<{ direction: "→" | "←"; otherId: string; otherName: string; relType: string }> = [];
    connectedEdges.forEach((items, relType) => {
      for (const e of items) result.push({ ...e, relType });
    });
    return result;
  }, [connectedEdges]);

  const useRadial = edgeCount > 0 && edgeCount <= 20;

  return (
    <motion.div
      initial={{ x: 288, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 288, opacity: 0 }}
      transition={{ type: "spring", damping: 24, stiffness: 260 }}
      className="absolute right-0 top-0 bottom-0 w-72 border-l border-border/50 bg-card/30 backdrop-blur-sm z-20 flex flex-col"
    >
      <div className="flex items-start gap-2 border-b border-border/50 px-3 py-2.5">
        <div className="flex-1 min-w-0">
          <h3
            ref={headingRef}
            tabIndex={-1}
            className="text-xs font-semibold truncate text-foreground outline-none"
          >
            {node.name}
          </h3>
          <span
            className="mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ backgroundColor: node.color + "22", color: node.color }}
          >
            {node.type}
          </span>
          <button
            type="button"
            data-focus-origin={navigation.focus_origin?.token}
            onClick={() => onOpenMetrics?.(navigation)}
            disabled={!onOpenMetrics}
            aria-describedby="graph-metrics-help"
            title={!onOpenMetrics ? "Metrics navigation unavailable" : `Open metrics for ${node.name}`}
            className="mt-2 inline-flex items-center gap-1 rounded-md border border-border/50 px-2 py-1 text-[10px] text-muted-foreground transition-colors hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <BarChart3 className="h-3 w-3" aria-hidden="true" />
            Open metrics
          </button>
          {!onOpenMetrics && (
            <p id="graph-metrics-help" className="mt-1 text-[10px] text-muted-foreground">
              Metrics navigation is unavailable for this graph surface.
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex border-b border-border/50 px-3">
        {(["properties", "relationships"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "flex items-center gap-1 px-2 py-1.5 text-[11px] font-medium border-b-2 transition-colors",
              tab === t
                ? "border-violet-500 text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t === "properties" ? <FileText className="h-3 w-3" /> : <Network className="h-3 w-3" />}
            {t === "properties" ? "Properties" : "Relationships"}
            {t === "relationships" && edgeCount > 0 && (
              <span className="text-[9px] text-muted-foreground">({edgeCount})</span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 text-xs">
        {tab === "properties" && (
          <NodeProperties
            nodeId={node.id}
            groups={propGroups}
            hasProps={filteredProps.length > 0}
          />
        )}
        {tab === "relationships" && (
          <div className="space-y-1.5">
            {edgeCount === 0 && (
              <p className="text-muted-foreground text-[11px] italic">No relationships loaded</p>
            )}
            {useRadial ? (
              <div className="pt-2">
                <GraphMiniRadial
                  centerColor={node.color}
                  edges={radialEdges}
                  onNodeSelect={onNodeSelect}
                />
              </div>
            ) : (
              [...connectedEdges.entries()].map(([label, items]) => (
                <RelGroup key={label} label={label} edges={items} />
              ))
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
