import type { GraphData } from "@/lib/graph-data-utils";

export function graphTypeCounts(nodes: GraphData["nodes"]): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const node of nodes) counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

export function filterGraphData(data: GraphData, hiddenTypes: Set<string>): GraphData {
  if (hiddenTypes.size === 0) return data;
  const visibleIds = new Set<string>();
  const nodes = data.nodes.filter((node) => {
    if (hiddenTypes.has(node.type)) return false;
    visibleIds.add(node.id);
    return true;
  });
  const links = data.links.filter((link) => {
    const source = typeof link.source === "string"
      ? link.source : (link.source as { id?: string }).id ?? "";
    const target = typeof link.target === "string"
      ? link.target : (link.target as { id?: string }).id ?? "";
    return visibleIds.has(source) && visibleIds.has(target);
  });
  return { nodes, links };
}
