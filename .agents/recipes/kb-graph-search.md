# Recipe: KB Graph Search — Graph-Enriched Semantic Search

Search documents by meaning, then enrich results with structural context from the knowledge graph.

## Bricks Used
- `kb` — Knowledge base with Neo4j HNSW vector search
- `llm_gateway` — Embeddings via Bedrock Titan

## Architecture

`Neo4jVectorStore.search()` implements a three-tier search strategy. Each tier activates only when the previous one fails or returns empty.

### Tier 1: Vector Search (HNSW)

`_vector_search()` calls Neo4j's `db.index.vector.queryNodes` with cosine similarity on the HNSW index. This is the primary path — fast approximate nearest-neighbor over embedding vectors.

### Tier 2: Text Fallback

`_text_search()` runs a Cypher `CONTAINS` substring match against `KBDocument.content`. Activates when the embedder fails (exception) or vector search returns no results.

### Tier 3: BM25 Fallback

`BM25Retriever` at the `KBRuntime` level. If `VectorStore.search()` returns `[]` (both vector and text tiers empty), `KBRuntime.search()` falls back to BM25+ ranked retrieval. Rebuilds the index on each query from `list_documents()` — suitable for small-to-medium corpora.

Why BM25Plus over BM25Okapi: BM25+ guarantees non-negative term scores regardless of corpus size, handling the single-document edge case correctly.

### Graph Enrichment Layer

`search(include_graph_context=True)` calls `_enrich_graph_context()` after vector search succeeds. For each result, queries neighboring nodes via `MATCH (n)-[r]-(m)` (limit 5 per document) and injects a `graph_context` list into `result.metadata`. This gives agents structural context — entity relationships, linked documents — alongside semantic similarity scores.

Graph enrichment only applies to Tier 1 (vector search). Text fallback results are not enriched.

```
KBRuntime.search(query)
  └─► VectorStore.search(query)
        ├─► _vector_search()  ──► results? ──► _enrich_graph_context() ──► return
        └─► _text_search()    ──► return (no enrichment)
  └─► BM25Retriever.retrieve(query)  ──► return (fallback)
```

## Prerequisites

- Neo4j running with HNSW vector index (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- AWS credentials for Bedrock embeddings (or use `NoOpKBEmbedder` for text-only mode)
- Documents ingested with embeddings (or use `backfill_embeddings()` after the fact)

## AWS Detection

```python
import boto3
try:
    boto3.client('sts').get_caller_identity()
    AWS_AVAILABLE = True
except:
    AWS_AVAILABLE = False
```

If `AWS_AVAILABLE` is False, skip embedding steps and use text/BM25 fallback.

## Steps

### Step 1: Initialize KB with Neo4j + Embedder

```python
import tempfile
from pathlib import Path

from factory.kb.runtime.runtime import KBRuntime
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorStore, Neo4jVectorConfig
from factory.kb.runtime.retrieval.neo4j_embedding import LLMGatewayKBEmbedder

cfg = Neo4jVectorConfig(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    embedding_dimensions=1024,  # Titan v2 default
)
embedder = LLMGatewayKBEmbedder()  # Uses llm_gateway → Bedrock Titan
store = Neo4jVectorStore(cfg, embedder=embedder)

tmpdir = Path(tempfile.mkdtemp())
(tmpdir / "collections").mkdir(parents=True, exist_ok=True)
kb = KBRuntime(config_dir=tmpdir)
kb.set_vector_store(store)
```

`Neo4jVectorStore.__init__` automatically creates the HNSW index via `_ensure_index()`. If the embedder can't initialize (no AWS creds), it falls back to `NoOpKBEmbedder` (dimensions=0, no vectors generated).

### Step 2: Ingest Documents with Embeddings

```python
# embed_on_ingest=True (default) generates embeddings automatically
r1 = kb.ingest(
    content="The Python Software Factory is a Polylith monorepo built for AI agents.",
    metadata={"source": "readme", "type": "overview"},
    source="docs",
    document_id="doc-overview",
)
r2 = kb.ingest(
    content="Every brick exposes a full MCP interface with tools, resources, and prompts.",
    metadata={"source": "readme", "type": "architecture"},
    source="docs",
    document_id="doc-mcp",
)
r3 = kb.ingest(
    content="Neo4j HNSW indexes enable fast approximate nearest-neighbor vector search.",
    metadata={"source": "technical", "type": "infrastructure"},
    source="docs",
    document_id="doc-neo4j",
)
# Returns: IngestResult(document_id="doc-overview", status="ingested", chunks_created=1)
```

Each `ingest()` call: stores the document as a `KBDocument` node → generates embedding via `LLMGatewayKBEmbedder` → sets the vector on the node. Entity extraction also runs by default (see knowledge-pipeline recipe).

### Step 3: Basic Semantic Search

```python
results = kb.search(query="What is the Python Software Factory?", limit=5)
# Returns: list[SearchResult]
for r in results:
    print(f"{r.document_id}: {r.score:.4f} — {r.content[:80]}")
```

This goes through the full fallback chain: vector → text → BM25. The `KBRuntime.search()` method handles the BM25 fallback transparently.

### Step 4: Graph-Enriched Search

```python
# Call the vector store directly for graph context
results = store.search(
    query="Python Software Factory",
    limit=5,
    include_graph_context=True,
)

for r in results:
    print(f"{r.document_id}: {r.score:.4f}")
    if "graph_context" in r.metadata:
        for ctx in r.metadata["graph_context"]:
            print(f"  └─ {ctx['relationship']} → {ctx['labels']} ({ctx['id']})")
```

`graph_context` is a list of neighboring node summaries:

```python
# Example graph_context entry
{
    "relationship": "HAS_ENTITY",   # relationship type
    "labels": ["__Entity__"],       # node labels
    "id": "entity-python-factory",  # node id
}
```

Each result gets up to 5 neighboring nodes. The Cypher pattern is undirected (`-[r]-` not `-[r]->`) so it captures both incoming and outgoing relationships.

### Step 5: Search Fallback Chain

The fallback is automatic — no caller action needed:

```python
# Scenario: embedder is down or returns no vectors
# _vector_search() fails → _text_search() via CONTAINS
results = store.search(query="Polylith monorepo")
# score=0.5 for all text matches (no similarity ranking)

# Scenario: VectorStore.search() returns [] entirely
# KBRuntime falls back to BM25Retriever
results = kb.search(query="some query with no vector or text hits")
# BM25+ scores normalized to 0-1 via score/(score+1)
```

Text search scores are fixed at `0.5`. BM25 scores are normalized: `min(score / (score + 1.0), 1.0)`. Results with BM25 score ≤ 0 are filtered out.

### Step 6: Backfill Embeddings

```python
count = store.backfill_embeddings(limit=100)
print(f"Re-embedded {count} documents")
# Finds KBDocument nodes where embedding IS NULL and content IS NOT NULL
```

When to use:
- Embedder was down during ingest (`NoOpKBEmbedder` was auto-selected)
- Switched from `NoOpKBEmbedder` to `LLMGatewayKBEmbedder` after initial setup
- AWS credentials became available after documents were already ingested

Returns 0 immediately if the current embedder has `dimensions == 0` (NoOp).

### Step 7: Verify HNSW Index

```python
# Via the graph brick's graph_query tool
from factory.graph.interface import graph_query

result = graph_query(query_str="SHOW INDEXES WHERE type = 'VECTOR'")
# Expect: index named "kb_documents" on KBDocument.embedding
```

The index is created automatically by `_ensure_index()` on `Neo4jVectorStore.__init__`. Config: cosine similarity, 1024 dimensions (Titan v2 default).

## Neo4jVectorConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `uri` | `str` | `bolt://localhost:7687` | Neo4j connection URI |
| `user` | `str` | `neo4j` | Neo4j username |
| `password` | `str` | `password` | Neo4j password |
| `database` | `str` | `neo4j` | Neo4j database name |
| `index_name` | `str` | `kb_documents` | HNSW vector index name |
| `node_label` | `str` | `KBDocument` | Label for document nodes |
| `embedding_property` | `str` | `embedding` | Property storing the vector |
| `embedding_dimensions` | `int` | `1024` | Vector dimensionality (Titan v2) |
| `embed_on_ingest` | `bool` | `True` | Generate embeddings on `add()` |
| `extract_entities` | `bool` | `True` | Run entity extraction on `add()` |

## SearchResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | `str` | Document identifier |
| `content` | `str` | Document content or snippet (BM25 truncates to 500 chars) |
| `score` | `float` | Relevance score (0–1). Cosine similarity for vector, 0.5 for text, normalized BM25+ for fallback |
| `metadata` | `dict[str, Any]` | Document metadata. Contains `graph_context` list when `include_graph_context=True` |

## When to Use Which Search Approach

| Use Case | Approach | Why |
|----------|----------|-----|
| Semantic similarity | `kb.search()` | Vector search with automatic fallback chain |
| Need structural context | `store.search(include_graph_context=True)` | Adds neighboring nodes/relationships to results |
| Exact text match | Falls back to `_text_search` automatically | Cypher `CONTAINS` — no ranking, score=0.5 |
| No embeddings available | BM25 fallback (automatic) | TF-IDF-like ranking via BM25+ |
| Precise graph queries | `graph_find_entities` (portable filtered reads) | Cypher for aggregation, path traversal, counting |
| Backfill after setup | `store.backfill_embeddings()` | Re-embed documents missing vectors |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Vector search returns `[]`, text search works | Embeddings missing on documents | Run `store.backfill_embeddings()` |
| All scores are `0.5` | Fell through to text search | Check embedder: `store._embedder.dimensions` should be > 0 |
| `ImportError: neo4j required` | `neo4j` Python package not installed | `pip install neo4j` |
| `NoOpKBEmbedder` auto-selected | `LLMGatewayKBEmbedder` init failed (no AWS creds) | Set AWS credentials, reinstantiate store |
| `graph_context` missing from metadata | `include_graph_context=False` (default) | Pass `include_graph_context=True` to `store.search()` |
| `graph_context` empty list | No neighboring nodes for that document | Ingest with `extract_entities=True` to build graph structure |
| BM25 returns nothing | All BM25 scores ≤ 0 (no term overlap) | Check query terms exist in corpus; try broader query |
| `backfill_embeddings` returns 0 | Embedder is NoOp (dimensions=0) or all docs already have vectors | Switch to `LLMGatewayKBEmbedder`; check `embedding IS NULL` in Neo4j |

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| kb | `factory.kb.runtime.runtime.KBRuntime` | `search()`, `ingest()`, `set_vector_store()` |
| kb | `factory.kb.runtime.retrieval.neo4j_vector.Neo4jVectorStore` | `search(include_graph_context=)`, `backfill_embeddings()` |
| kb | `factory.kb.runtime.retrieval.neo4j_vector.Neo4jVectorConfig` | Pydantic config for Neo4j connection + index settings |
| kb | `factory.kb.runtime.retrieval.neo4j_embedding.LLMGatewayKBEmbedder` | `embed([texts])` → `list[list[float]]`, `.dimensions` → `int` |
| kb | `factory.kb.runtime.retrieval.neo4j_embedding.NoOpKBEmbedder` | Null embedder (dimensions=0, returns `[]`) |
| kb | `factory.kb.runtime.retrieval.bm25_retriever.BM25Retriever` | `retrieve(query, limit=)` → `list[SearchResult]` |
| kb | `factory.kb.runtime.models.SearchResult` | `document_id`, `content`, `score`, `metadata` |

## Without AWS

If no AWS credentials:
- `LLMGatewayKBEmbedder` init fails → `NoOpKBEmbedder` auto-selected (dimensions=0)
- Vector search skipped (no embeddings generated) → text search via `CONTAINS`
- If text search returns `[]` → BM25 fallback at `KBRuntime` level
- `backfill_embeddings()` returns 0 immediately (NoOp embedder)
- Graph enrichment still works if entities were extracted by other means
- Report: "Tested kb search with text/BM25 fallback, skipped vector search (no AWS)"
