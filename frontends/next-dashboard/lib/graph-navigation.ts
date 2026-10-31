import type { GraphNode, NavigationRef } from "@/lib/types";

/** Stable token shared by the Graph detail control and return-focus lookup. */
export function graphMetricsFocusToken(nodeId: string): string {
  return `graph-open-metrics:${encodeURIComponent(nodeId)}`;
}

export function navigationForGraphNode(node: GraphNode): NavigationRef {
  return {
    version: "v1",
    surface: "graph",
    target_ref: node.id,
    label: node.name,
    graph_selected_ref: node.id,
    graph_context: { query_ref: node.id, neighborhood_limit: 20 },
    focus_origin: {
      token: graphMetricsFocusToken(node.id),
      surface: "graph",
      control: "open-metrics",
    },
  };
}

/** Focus a currently-mounted control without retaining a stale DOM node. */
export function focusNavigationOrigin(token: string): boolean {
  if (typeof document === "undefined") return false;
  const controls = document.querySelectorAll<HTMLElement>("[data-focus-origin]");
  for (const control of controls) {
    if (control.dataset.focusOrigin !== token) continue;
    control.focus();
    return document.activeElement === control;
  }
  return false;
}
