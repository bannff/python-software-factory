# Recipe: Graph Page — UI Data Flow

End-to-end data flow from the graph brick MCP tools through the custom `graph-view.tsx` renderer to the the control-plane runtime dashboard.

## Bricks Used
- `graph` — Entity management, neighbor traversal, graph backend (networkx for local dev, Neo4j for full stack)

## Scenario

Load the graph topology, auto-expand nodes to discover edges, click a node to expand its neighborhood, and inspect properties in the detail sidebar.

## Prerequisites

- **Local dev (no containers):** networkx adapter (`FACTORY_GRAPH_ADAPTER=networkx`). Graph data is ephemeral (in-memory), but CWE/OCSF taxonomy auto-seeds on startup so the graph is immediately usable. No Neo4j needed.
- **Full stack (Docker):** Neo4j (`bolt://localhost:7687`). Graph data persists across restarts (1034 nodes, 1670 edges in production dataset) — no seeding step required.

## Custom View: No item_list

The graph page uses a custom renderer (`graph-view.tsx`) instead of the standard `item_list` pattern. It renders a D3 force-directed layout via `react-force-graph-2d` with direct MCP tool calls through the `useGraphData` hook.

## Steps

### Step 1: Initial Load — Find Entities

```python
# Frontend calls on "Load Graph" button click (or page mount)
entities = graph_find_entities(limit=50)
# → {"entities": [{"id": "lambda-001", "type": "Lambda", "properties": {"name": "AuthHandler"}}, ...], "count": 50}

# Optional: filter by type
entities = graph_find_entities(entity_type="Lambda", limit=50)
```

### Step 2: Auto-Expand First 20 Nodes

```python
# useGraphData auto-expands the first 20 nodes to discover edges
# Each call runs in parallel via Promise.all
neighbors = graph_get_neighbors(entity_id="lambda-001")
# → {"entity_id": "lambda-001", "neighbors": [{"id": "dynamo-005", "type": "DynamoDB", "properties": {...}}, ...], "count": 3}
```

### Step 3: Frontend Rendering Pipeline

```typescript
// graph-view.tsx — custom renderer, NOT BrickViewRenderer

// 1. useGraphData hook manages node/edge state with dedup
const { data, loading, loadTopology, expandNode, reset } = useGraphData();

// 2. loadTopology() calls graph_find_entities, then auto-expands first 20
//    Dedup via seenNodes/seenLinks refs (Set<string>)

// 3. Color mapping applied per node type:
const TYPE_COLORS = {
  Lambda: "#3b82f6",      // blue
  S3: "#22c55e",          // green
  DynamoDB: "#f97316",    // orange
  Pipeline: "#a855f7",    // purple
  IamRole: "#ef4444",     // red
  EC2: "#06b6d4",         // cyan
  RDS: "#eab308",         // yellow
  SNS: "#ec4899",         // pink
  SQS: "#ec4899",         // pink
  KBDocument: "#10b981",  // emerald
  Memory: "#8b5cf6",      // violet
};

// 4. ForceGraph2D renders with:
//    - nodeCanvasObject: custom circle + label (label visible at zoom > 1.5x)
//    - linkDirectionalArrowLength: 4 (directed edges)
//    - linkDirectionalParticles: 1 (animated flow)
//    - Selected node gets amber stroke highlight

// 5. Click node → expandNode(id) → graph_get_neighbors
//    New nodes/edges merged into state, graph re-renders

// 6. Detail sidebar shows: name, ID, type, first 10 properties
//    Filters out embedding/structural/n2v properties
```

### Step 4: A2UI Agent State Bridge

```typescript
// If an agent pushes graph data via A2UI state, it merges automatically
const a2ui = agentState._a2ui_graph as { nodes?: GraphNode[]; links?: GraphLink[] };
const graphData = a2ui?.nodes ? { nodes: a2ui.nodes, links: a2ui.links ?? [] } : data;
// Agent-pushed data takes precedence over MCP-loaded data
```

### Step 5: Verify Data Flow

```python
# Stats — verify graph is populated
stats = graph_get_stats()
# Neo4j: → {"backend": "neo4j", "node_count": 1034, "edge_count": 1670, "healthy": True}
# networkx (local dev): → {"backend": "networkx", "node_count": N, "edge_count": M, "healthy": True}
#   (node/edge counts depend on auto-seeded CWE/OCSF taxonomy)

# Entity lookup — verify properties render in sidebar
entity = graph_get_entity(entity_id="lambda-001")
# → {"found": True, "id": "lambda-001", "type": "Lambda", "properties": {"name": "AuthHandler", ...}}

# Neighbor expansion — verify edges render
neighbors = graph_get_neighbors(entity_id="lambda-001", direction="both")
# → {"neighbors": [...], "count": N}
```

## Success Criteria

- [ ] "Load Graph" populates the canvas with nodes from `graph_find_entities`
- [ ] Auto-expand discovers edges via `graph_get_neighbors` (first 20 nodes)
- [ ] Node colors match type (Lambda=blue, S3=green, DynamoDB=orange, etc.)
- [ ] Clicking a node expands its neighborhood and highlights it amber
- [ ] Detail sidebar shows node name, type, and filtered properties
- [ ] Node labels appear when zoomed in past 1.5x
- [ ] Directed arrows and animated particles render on edges
- [ ] Reset button clears the graph and dedup sets
- [ ] Search/filter by entity type works via `graph_find_entities(entity_type=...)`

## API Reference

| Tool | Category | Key Args | Returns |
|------|----------|----------|---------|
| `graph_find_entities` | deterministic | `entity_type, limit` | `{entities: [{id, type, properties}], count}` |
| `graph_get_neighbors` | deterministic | `entity_id, relationship_type, direction` | `{neighbors: [{id, type, properties}], count}` |
| `graph_get_entity` | deterministic | `entity_id` | `{found, id, type, properties, labels}` |
| `graph_get_stats` | deterministic | `backend` | `{node_count, edge_count, healthy}` |
| `graph_health_check` | deterministic | — | `{healthy, graphs, gds}` |
