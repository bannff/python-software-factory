"use client";

/**
 * Carrier #2 (canvas-paint) state-shape contract + view-side helpers.
 *
 * The `ui_paint_canvas` MCP tool (bd-D, ``python-factory-syh1``) emits
 * ``STATE_DELTA`` patches against ``state.canvas.<slot>`` per the State
 * Shape Contract in ``.agents/steering/a2ui-protocol.md``:
 *
 *     {
 *       "canvas": {
 *         "graph":    { "components": [...], "name": "graph" },
 *         "timeline": { "components": [...], "name": "timeline" },
 *         "findings": { "components": [...], "name": "findings" },
 *         "live":     { "components": [...], "name": "live" }
 *       }
 *     }
 *
 * Each slot value is a normal A2UI payload — the same shape as carrier
 * #1 tool results — so it can flow through ``<ComponentTree>`` without
 * a translation layer.
 *
 * The legacy ``_a2ui_graph`` / ``_a2ui_timeline`` / ``_a2ui_findings`` /
 * ``_a2ui_canvas`` flat-key vocabulary is dropped under bd-F.
 *
 * Slot rename ``canvas`` → ``live`` under bd:python-factory-3hkqx —
 * the slot key now matches the FE view id so the agent's prompt and
 * the user's mental model align.
 */

import { useMemo } from "react";
import type { ReactAdapterNode } from "@companion-x/shared-renderer";
import type { GraphNode, GraphLink } from "@/lib/types";
import { a2uiToReactAdapterNodes } from "./a2ui-tree";

export interface CanvasSlot {
  components?: unknown[];
  name?: string;
}

export interface CanvasState {
  graph?: CanvasSlot;
  timeline?: CanvasSlot;
  findings?: CanvasSlot;
  live?: CanvasSlot;
}

/**
 * Memoised slot → ReactAdapterNode[] translate.
 *
 * Delegates the A2UI → ReactAdapterNode tree shape transform to
 * ``a2ui-tree.ts::a2uiToReactAdapterNodes`` (carved out to keep this
 * module under 200 LOC). bd:python-factory-3hkqx round 3,
 * meta-architect verdict ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7``.
 *
 * Per strands-expert verdict ``87e4611d-843d-47d0-9732-bdabbab7d4e9``,
 * ``useAgent`` ``forceUpdate``s on every state change with no per-key
 * selector. Per-slot ``useMemo`` is the canvas-view's mitigation: the
 * slot reference is stable across un-painted renders because
 * ``StateManager.getStateByRun`` deep-clones.
 */
export function usePaintedComponents(
  slot: CanvasSlot | undefined,
): ReactAdapterNode[] {
  return useMemo(
    () => a2uiToReactAdapterNodes(slot?.components ?? []),
    [slot],
  );
}

const NODE_TYPES = new Set(["graph_node", "GraphNode", "node"]);
const LINK_TYPES = new Set(["graph_link", "GraphLink", "link", "edge"]);

interface A2UIComponentLite {
  id?: string;
  component?: string;
  originalType?: string;
  type?: string;
  props?: Record<string, unknown>;
}

function compType(c: A2UIComponentLite): string {
  return c.originalType ?? c.component ?? c.type ?? "";
}

/**
 * Best-effort transform of a graph slot payload into the bespoke
 * ``GraphView`` force-graph data shape ``{nodes, links}``.
 *
 * Components whose type is ``graph_node`` / ``graph_link`` are extracted;
 * everything else is dropped. Returns ``null`` when no nodes are
 * extractable so the caller can fall back to its MCP-loaded data — keeps
 * today's UX intact when the agent emits a generic A2UI tree the
 * force-graph renderer can't natively consume.
 */
export function a2uiSlotToGraphData(
  slot: CanvasSlot | undefined,
): { nodes: GraphNode[]; links: GraphLink[] } | null {
  const comps = (slot?.components as A2UIComponentLite[] | undefined) ?? [];
  if (comps.length === 0) return null;
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];
  for (const c of comps) {
    const t = compType(c);
    const p = (c.props ?? {}) as Record<string, unknown>;
    if (NODE_TYPES.has(t)) {
      nodes.push({
        id: String(c.id ?? p.id ?? ""),
        name: String(p.name ?? p.label ?? c.id ?? ""),
        type: String(p.type ?? "Unknown"),
        color: String(p.color ?? "#a78bfa"),
        val: Number(p.val ?? p.size ?? 1),
        properties: p,
      });
    } else if (LINK_TYPES.has(t)) {
      const src = p.source ?? p.from;
      const tgt = p.target ?? p.to;
      if (src && tgt) {
        links.push({
          source: String(src),
          target: String(tgt),
          label: p.label ? String(p.label) : undefined,
        });
      }
    }
  }
  return nodes.length > 0 ? { nodes, links } : null;
}
