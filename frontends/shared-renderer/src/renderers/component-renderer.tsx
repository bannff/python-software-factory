"use client";

import React, { useCallback } from "react";
import { FallbackComponent, getRenderer, normalizeComponentName } from "./component-map";
import { AnimationWrapper } from "./animation-wrapper";
import type { ReactAdapterNode } from "./renderers";

export type { ReactAdapterNode };

interface ComponentRendererProps {
  node: ReactAdapterNode;
}

/**
 * Recursive renderer for ReactAdapter JSON output.
 *
 * Looks up the `component` (or `type`) field via ``getRenderer``, which
 * resolves case- and underscore-insensitively against ``COMPONENT_MAP``
 * (``component-map.ts``). Renders children recursively and wraps with
 * ``AnimationWrapper`` when an animation hint is present.
 *
 * ``renderChildren`` is memoised so layout renderers (PageRenderer
 * etc.) receive a stable prop and don't force their subtree to
 * re-mount on every parent render — which would reset useState in
 * stateful children like ItemListRenderer.
 *
 * bd:python-factory-3hkqx round 3 — pivoted from exact-key
 * ``COMPONENT_MAP[key]`` lookup to ``getRenderer(key)`` so PascalCase
 * (``Card``), lower_snake (``item_list``), and mixed (``Item_List``)
 * all resolve to the same renderer (meta-architect verdict
 * ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q2(iv)).
 */
export function ComponentRenderer({ node }: ComponentRendererProps) {
  const key = node.component || (node as Record<string, unknown>).type as string || "";
  const Comp = getRenderer(key) ?? FallbackComponent;

  const renderChildren = useCallback(
    (children?: ReactAdapterNode[]): React.ReactNode => {
      if (!children || children.length === 0) return null;
      return children.map((child) => (
        <ComponentRenderer key={child.id} node={child} />
      ));
    },
    [],
  );

  const rendered = <Comp node={node} renderChildren={renderChildren} />;

  // bd:python-factory-3hkqx round 6 — decorative-prop pass-through
  // (qa-tester verdict `e9deb353-5a9b-4a54-90f9-35b99e682210`,
  // meta-architect Option A). Renderers don't plumb arbitrary
  // ``props.style`` through to their root element, and ~8 renderers
  // also drop ``props.className``. Without this wrapper, the
  // agent's gradient/neon/colored-border decorations (e.g.
  // "Synthwave Arcade" scene) drop on the floor and Cards surface
  // as empty boxes. Wrap only when a decorative prop is present so
  // unstyled nodes keep their existing DOM shape — no layout
  // regression. Renderers that already honor ``className`` will
  // see a duplicate class on the wrapper + their root; harmless.
  // Pinned by ``renderers-style-passthrough.test.tsx`` (round 6).
  const style = (node.props as { style?: React.CSSProperties }).style;
  const className = (node.props as { className?: string }).className;
  const hasStyle = style && typeof style === "object";
  const hasClass = typeof className === "string" && className.length > 0;
  const decorated = (hasStyle || hasClass)
    ? <div style={hasStyle ? style : undefined} className={hasClass ? className : undefined}>{rendered}</div>
    : rendered;

  if (node.animation) {
    return <AnimationWrapper animation={node.animation}>{decorated}</AnimationWrapper>;
  }

  return decorated;
}

/* ── Metric strip grouping (bd:python-factory-3jcls.2) ────────────
 *
 * Brick views declare stat cards as a flat run of sibling ``metric``
 * nodes (views are data — the payload carries no container type). Left
 * as-is they stack into full-width rows, so the ML Overview's seven
 * integers needed ~1.4 viewports. Consecutive metrics are tiled into
 * one responsive grid here, at the renderer, so EVERY brick that emits
 * a metric run reads at a glance. A lone metric keeps its original DOM
 * shape (no wrapper) so single-stat layouts don't shift.
 */

const METRIC_COMPONENTS = new Set(["metric", "metriccard"]);

function isMetricNode(node: ReactAdapterNode): boolean {
  const key = node.component || (node as unknown as Record<string, unknown>).type as string || "";
  return METRIC_COMPONENTS.has(normalizeComponentName(key));
}

type TreeGroup =
  | { kind: "single"; node: ReactAdapterNode }
  | { kind: "metrics"; nodes: ReactAdapterNode[] };

export function groupMetricRuns(nodes: ReactAdapterNode[]): TreeGroup[] {
  const out: TreeGroup[] = [];
  let run: ReactAdapterNode[] = [];
  const flush = () => {
    if (run.length > 1) out.push({ kind: "metrics", nodes: run });
    else if (run.length === 1) out.push({ kind: "single", node: run[0] });
    run = [];
  };
  for (const node of nodes) {
    if (isMetricNode(node)) run.push(node);
    else { flush(); out.push({ kind: "single", node }); }
  }
  flush();
  return out;
}

/**
 * Renders an array of top-level ReactAdapterNodes.
 * Convenience wrapper for rendering a full view's component list.
 */
export function ComponentTree({ nodes, onItemSelect }: { nodes: ReactAdapterNode[]; onItemSelect?: (entityId: string) => void }) {
  // Inject onItemSelect into each node's props so downstream renderers can use it
  const enriched = onItemSelect
    ? nodes.map((n) => ({ ...n, props: { ...n.props, onItemSelect } }))
    : nodes;
  return (
    <>
      {groupMetricRuns(enriched).map((group) =>
        group.kind === "single" ? (
          <ComponentRenderer key={group.node.id} node={group.node} />
        ) : (
          <div
            key={`metrics-${group.nodes[0].id}`}
            data-metric-strip="true"
            className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3 xl:grid-cols-4"
          >
            {group.nodes.map((node) => (
              <ComponentRenderer key={node.id} node={node} />
            ))}
          </div>
        ),
      )}
    </>
  );
}
