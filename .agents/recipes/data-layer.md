# Recipe: Data Layer

Validates the storage, caching, and graph relationship pipeline.

## Bricks Used
- `storage` - Blob, document, SQL, and graph storage (includes low-level graph CRUD via MCP)
- `cache` - Ephemeral caching
- `graph` - Knowledge graph relationships (high-level: vector search, GDS, path finding)

> **storage graph vs graph brick**: The `storage` brick exposes low-level graph CRUD
> (`storage_graph_*` tools) — same abstraction layer as BlobStore and DocumentStore.
> The `graph` brick provides high-level knowledge graph operations: entity/relationship
> semantics, vector-powered search, graph algorithms, and path finding. Use storage
> graph for raw node/edge manipulation; use the graph brick for domain-level knowledge modeling.

### Storage MCP Result Contract

Every `storage_*` tool in this recipe accepts flat kwargs and returns a `ToolResult[OutputDTO]`. Check `result.ok` before accessing `result.data`; failures have `data: null`. Normal domain outcomes remain successful envelopes: missing graph nodes have `result.data.found == false` and `error == "not_found"`, while absent delete targets return `result.data.deleted == false`.

## Scenario

Store a blob, cache the hot path, and build entity relationships in the graph.

## Prerequisites

- No AWS required
- Bricks instantiated with memory adapters

## Steps

### Step 1: Initialize Bricks

```python
from pathlib import Path
import tempfile

from factory.storage.runtime.adapters import LocalBlobStore
from factory.cache.runtime.runtime import get_runtime as get_cache_runtime
from factory.graph.runtime.runtime import GraphRuntime

# Storage - use LocalBlobStore adapter
tmpdir = tempfile.mkdtemp()
storage = LocalBlobStore(root_path=Path(tmpdir))

# Cache - get from runtime
cache = get_cache_runtime().get_cache()

# Graph - get graph from runtime
graph = GraphRuntime().get_graph()
```

### Step 2: Health Check All Bricks

```python
# Cache health
from factory.cache.runtime.runtime import get_runtime
get_runtime().health_check()
# Expected: no exception

# Graph health
health = graph.health_check()
# Returns: GraphHealth(node_count=0, edge_count=0)

# Storage health
health = storage.health_check()
# Returns: StorageHealth(healthy=True, ...)
```

### Step 3: Store a Blob

```python
content = b"# Python Factory\nA Polylith monorepo."
meta = storage.put("docs/readme.md", content, content_type="text/markdown")
# Returns: BlobMeta(key="docs/readme.md", size=N, ...)

# Retrieve
data, meta = storage.get("docs/readme.md")
# Returns: (bytes, BlobMeta)
```

### Step 4: Cache the Hot Path

```python
cache.set("blob:docs/readme.md:exists", "true", 300)  # ttl in seconds
# Returns: None

value = cache.get("blob:docs/readme.md:exists")
# Returns: "true"
```

### Step 5: Add Graph Entities

```python
from factory.graph.runtime.ports import Entity

doc_entity = Entity(
    id="doc:readme",
    type="document",
    properties={"path": "docs/readme.md", "format": "markdown"}
)
graph.add_entity(doc_entity)

project_entity = Entity(
    id="project:factory",
    type="project",
    properties={"name": "python-factory"}
)
graph.add_entity(project_entity)
```

### Step 6: Create Relationship

```python
from factory.graph.runtime.ports import Relationship

rel = Relationship(
    id="rel:doc-readme-belongs-to-factory",  # id is required
    type="belongs_to",
    source_id="doc:readme",      # note: source_id not source
    target_id="project:factory", # note: target_id not target
    properties={"added_by": "recipe-test"}
)
graph.add_relationship(rel)
```

### Step 7: Query Graph

```python
# Get neighbors
neighbors = graph.get_neighbors("doc:readme")
# Returns: list of Entity objects

# Get specific entity
entity = graph.get_entity("doc:readme")
# Returns: Entity(id="doc:readme", type="document", ...)

# Check graph state
health = graph.health_check()
# Returns: GraphHealth(node_count=2, edge_count=1)
```

### Step 8: Verify Cache Stats

```python
stats = cache.stats()
# Returns: CacheStats(hits=N, misses=M, size=S)
```

### Step 9: Storage Graph Operations (Low-Level CRUD)

These steps exercise the `storage_graph_*` MCP tools — the low-level graph
interface on the storage brick. Unlike the graph brick (Steps 5–7), these
operate on raw nodes/edges with labels, not domain entities.

**9a. Add a Document node**

Call `storage_graph_add_node`:
```
labels: ["Document"]
properties: {"path": "docs/readme.md", "format": "markdown"}
```
Expected successful envelope (save `result.data.id` as `doc_node_id`):
```json
{"schema_version":"v1","ok":true,"data":{"id":"<generated>","labels":["Document"],"properties":{"path":"docs/readme.md","format":"markdown"}},"error":null,"idempotency_key":null}
```

**9b. Add a Project node**

Call `storage_graph_add_node`:
```
labels: ["Project"]
properties: {"name": "python-factory"}
```
Save the returned `id` as `project_node_id`.

**9c. Connect them with an edge**

Call `storage_graph_add_edge`:
```
source_id: <doc_node_id>
target_id: <project_node_id>
edge_type: "BELONGS_TO"
properties: {"added_by": "data-layer-recipe"}
```
Expected successful payload is under `result.data`; save `result.data.id` as `edge_id`:
```json
{"id":"<generated>","source_id":"...","target_id":"...","type":"BELONGS_TO","properties":{"added_by":"data-layer-recipe"}}
```

**9d. Query edges for the Document node**

Call `storage_graph_get_edges`:
```
node_id: <doc_node_id>
direction: "out"
```
Expected: `edges` array contains the BELONGS_TO edge, `count` is 1.

**9e. Run a Cypher query**

Call `storage_graph_query`:
```
cypher: "MATCH (d:Document)-[r:BELONGS_TO]->(p:Project) RETURN d, r, p"
```
Expected: `nodes` contains both nodes, `edges` contains the BELONGS_TO edge.

**9f. Verify node retrieval**

Call `storage_graph_get_node`:
```
node_id: <doc_node_id>
```
Expected: `result.ok` is true and `result.data` contains the Document node with correct labels and properties. A missing node is also `ok: true`; its typed payload has `found: false`, the requested `node_id`, and `error: "not_found"`.

**9g. Update node properties**

Call `storage_graph_update_node`:
```
node_id: <doc_node_id>
properties: {"path": "docs/readme.md", "format": "markdown", "reviewed": true}
```
Expected: `result.ok` is true and `result.data` returns the node with updated properties. Updating a missing node is a normal successful `found: false` / `error: "not_found"` payload.

**9h. Clean up**

Call `storage_graph_delete_edge` with `edge_id: <edge_id>`.
Expected: `result.ok` is true and `result.data` is `{"deleted": true, "edge_id": "..."}`.

Call `storage_graph_delete_node` with `node_id: <doc_node_id>`.
Call `storage_graph_delete_node` with `node_id: <project_node_id>`.
Expected: both return successful typed payloads with `deleted: true`. Retrying an already-completed delete remains successful with `deleted: false`; it is not a transport error.

```python
# Python API equivalent (for reference):
from factory.storage.runtime.runtime import get_runtime

store = get_runtime().get_graph_store()

# Add nodes
doc = store.add_node(["Document"], {"path": "docs/readme.md", "format": "markdown"})
proj = store.add_node(["Project"], {"name": "python-factory"})

# Add edge
edge = store.add_edge(doc.id, proj.id, "BELONGS_TO", {"added_by": "data-layer-recipe"})

# Query
edges = store.get_edges(doc.id, direction="out")
result = store.query("MATCH (d:Document)-[r:BELONGS_TO]->(p:Project) RETURN d, r, p")

# Update
store.update_node(doc.id, {"path": "docs/readme.md", "format": "markdown", "reviewed": True})

# Clean up
store.delete_edge(edge.id)
store.delete_node(doc.id)
store.delete_node(proj.id)
```

## Success Criteria

- [x] Blob stored successfully via `put()`
- [x] Blob retrieved via `get()`
- [x] Cache set/get works
- [x] Graph entities created via `add_entity()` (graph brick)
- [x] Graph relationship created via `add_relationship()` (graph brick)
- [x] Graph query returns related nodes (graph brick)
- [x] Cache stats show activity
- [x] Storage graph nodes created via `storage_graph_add_node`
- [x] Storage graph edge created via `storage_graph_add_edge`
- [x] Storage graph edge query returns correct results via `storage_graph_get_edges`
- [x] Cypher query returns nodes and edges via `storage_graph_query`
- [x] Node update works via `storage_graph_update_node`
- [x] Cleanup succeeds via `storage_graph_delete_edge` and `storage_graph_delete_node`

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| storage | `factory.storage.runtime.adapters.LocalBlobStore` | `put()`, `get()`, `health_check()` |
| storage (graph) | `factory.storage.runtime.runtime.get_runtime` | `get_graph_store()` → `add_node()`, `get_node()`, `update_node()`, `delete_node()`, `add_edge()`, `get_edges()`, `delete_edge()`, `query()` |
| cache | `factory.cache.runtime.runtime.get_runtime` | `get_cache()` → `set()`, `get()`, `stats()` |
| graph | `factory.graph.runtime.runtime.GraphRuntime` | `get_graph()` → `add_entity()`, `add_relationship()`, `get_neighbors()` |
| graph models | `factory.graph.runtime.ports` | `Entity`, `Relationship`, `GraphHealth` |
| storage graph models | `factory.storage.runtime.ports.graph` | `GraphNode`, `GraphEdge`, `GraphQueryResult` |

### Storage Graph MCP Tools

| Aggregator Tool Name | Parameters | Returns |
|---------------------|------------|---------|
| `storage_graph_add_node` | `labels: list[str]`, `properties: dict \| None` | `{id, labels, properties}` |
| `storage_graph_get_node` | `node_id: str` | `{id, labels, properties}` or `{error: "not_found"}` |
| `storage_graph_update_node` | `node_id: str`, `properties: dict` | `{id, labels, properties}` or `{error: "not_found"}` |
| `storage_graph_delete_node` | `node_id: str` | `{deleted: bool, node_id}` |
| `storage_graph_add_edge` | `source_id: str`, `target_id: str`, `edge_type: str`, `properties: dict \| None` | `{id, source_id, target_id, type, properties}` |
| `storage_graph_get_edges` | `node_id: str`, `direction: str = "both"` | `{edges: [...], count: int}` |
| `storage_graph_delete_edge` | `edge_id: str` | `{deleted: bool, edge_id}` |
| `storage_graph_query` | `cypher: str`, `params: dict \| None` | `{nodes: [...], edges: [...], raw: [...]}` |

## Agent Hooks

This recipe is referenced by the following hooks in `.kiro/hooks/`:

- `qa-on-stop.kiro.hook` — After agent execution, checks if changed code needs tests and directs the qa-tester to follow recipe steps for E2E test structure
- `recipe-validation.kiro.hook` — Before spec task execution, loads the matching recipe as implementation context
- `docs-on-stop.kiro.hook` — After agent execution, checks if recipe API reference tables need updating when MCP tools change

When writing E2E tests for storage graph tools, structure test files to mirror Steps 9a–9h above. See `components/storage/test/factory/storage/test_graph_e2e_*.py` for the reference implementation.
