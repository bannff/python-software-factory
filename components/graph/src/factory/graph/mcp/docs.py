"""Documentation content for portable Graph MCP resources."""

GRAPH_DOCS = {
    "overview": {
        "title": "Graph Brick Overview",
        "content": """# Graph Brick

Portable knowledge-graph operations for entities and relationships.

## Features

- **Entity management**: add, update, delete, fetch, and find entities
- **Relationship management**: create, delete, and traverse relationships
- **Path finding**: find shortest paths between entities
- **Evidence reads**: inspect workflow runs, findings, and tool invocations
- **Multi-backend**: NetworkX for local development, Neo4j and Neptune adapters for deployments

## MCP Tools

Use the typed portable tools: `graph_add_entity`, `graph_get_entity`,
`graph_find_entities`, `graph_add_relationship`, `graph_get_neighbors`,
`graph_find_path`, `graph_get_findings_for_run`, and
`graph_get_workflow_summary`. Provenance projection mutations are exposed as
`graph_write_relationship`, `graph_tombstone_relationship`, and `graph_rebuild`.
Every Graph tool returns `ToolResult[T]`; read
payload fields from `result.data` only after checking `result.ok`.

## MCP Resources

- `graph://schemas/node` — entity schema
- `graph://schemas/edge` — relationship schema
- `graph://schemas/taxonomy` — unified graph taxonomy
- `graph://schemas/taxonomy/{domain}` — registered domain taxonomy
- `graph://docs/overview` — this guide
- `graph://docs/adapters` — backend guide
- `graph://stats` — live graph statistics
- `graph://backends` — available backend information
""",
    },
    "adapters": {
        "title": "Graph Adapters",
        "content": """# Graph Adapters

The Graph brick uses the same portable entity, relationship, traversal, and
evidence-read contracts across its backends.

## NetworkX Adapter

In-memory graph for local development, testing, and small single-process
workloads.

## Neo4j Adapter

Persistent graph database for production or multi-process deployments. Set
`NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` when selecting this backend.

## Neptune Adapter

AWS Neptune adapter for portable entity and relationship operations.

All adapters implement the `KnowledgeGraph` protocol in `runtime/ports.py`.
Backend-specific query, vector, and graph-data-science APIs are intentionally
not exposed by this brick's public MCP surface.
""",
    },
}
