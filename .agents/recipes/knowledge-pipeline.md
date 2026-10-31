# Recipe: Knowledge Pipeline

Validates the RAG (Retrieval-Augmented Generation) pipeline.

## Bricks Used
- `kb` - Knowledge base with vector search (Neo4j or Chroma — all storage via `VectorStore` ABC)
- `llm_gateway` - LLM completions and embeddings
- `memory` - Agent memory for context

## Architecture

All KB operations go through the `VectorStore` ABC (`runtime/ports.py`). Neo4j is the single source of truth — there is no separate document store. The `VectorStore` interface covers the full lifecycle: `add()`, `search()`, `get()`, `delete()`, and `list_documents()`.

Key design points:
- `list_documents()` on `VectorStore` powers both BM25 fallback search (when vector search returns no results) and `get_collection_stats()`.
- `delete()` on the Neo4j adapter cleans up orphaned `__Entity__` nodes (entities no longer linked to any document via `HAS_ENTITY`).
- `search()` tries vector similarity first, falls back to BM25-ranked text search via `BM25Retriever`.

## Scenario

Ingest a document, create embeddings, perform semantic search, and remember the context for follow-up queries.

## Prerequisites

- Neo4j running and configured (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- AWS credentials available (for Bedrock embeddings/completions)
- Bricks instantiated with appropriate adapters

## AWS Detection

```python
import boto3
try:
    boto3.client('sts').get_caller_identity()
    AWS_AVAILABLE = True
except:
    AWS_AVAILABLE = False
```

If `AWS_AVAILABLE` is False, skip LLM steps and report.

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path

# KB
tmpdir_kb = Path(tempfile.mkdtemp())
(tmpdir_kb / "collections").mkdir(parents=True, exist_ok=True)

from factory.kb.runtime.runtime import KBRuntime
kb = KBRuntime(config_dir=tmpdir_kb)

# LLM Gateway (requires AWS)
from factory.llm_gateway.runtime.runtime import LLMRuntime
llm_runtime = LLMRuntime()
llm_provider = llm_runtime.get_provider("bedrock", region_name="us-east-1")
embedder = llm_runtime.get_embedder("bedrock", region_name="us-east-1")

# Memory
from factory.memory.runtime.runtime import MemoryRuntime
memory = MemoryRuntime()
```

### Step 2: Health Checks

```python
# KB - get collection stats (uses VectorStore.list_documents() internally)
stats = kb.get_collection_stats()
# Returns: CollectionStats(collection_id="default", document_count=0, ...)

# LLM provider health
health = llm_provider.health_check()
# Returns: LLMHealth(healthy=True, provider="bedrock", ...)

# Memory health
health = memory.health_check()
# Returns: MemoryHealth(healthy=True, backend="memory", ...)
```

### Step 3: Ingest Document

```python
result = kb.ingest(
    content="The Python Software Factory is a Polylith monorepo built for AI agents. Every brick exposes an MCP interface.",
    metadata={"source": "readme", "type": "documentation"},
    source="recipe-test",
    document_id="doc-001",
)
# Returns: IngestResult(document_id="doc-001", status="ingested", chunks_created=1)
```

### Step 4: Create Embeddings (Requires AWS)

```python
# Note: embed() takes a LIST of texts, returns EmbeddingResponse
response = embedder.embed(["What is the Python Software Factory?"])
embedding = response.embeddings[0]  # First embedding from list
# embedding is a list of floats (e.g., 1024 dimensions)
```

### Step 5: Semantic Search

```python
results = kb.search(
    query="What is the Python Software Factory?",
    limit=3,
)
# Returns: list of SearchResult objects
# Falls back to BM25-ranked text search if vector search returns no results
```

### Step 6: Generate Answer (Requires AWS)

```python
# Build context from search results
context = results[0].content if results else ""

prompt = f"""Based on this context: {context}

Answer the question: What is the Python Software Factory?"""

# Note: LLMResponse has 'content' not 'text'
response = llm_provider.complete(prompt, max_tokens=200)
answer = response.content  # not response.text
# response.usage contains {"input_tokens": N, "output_tokens": M}
```

### Step 7: Store in Memory

```python
# Note: category must be MemoryCategory enum, not string
from factory.memory.core import MemoryCategory

mem = memory.store(
    user_id="recipe-user",
    content="User asked about Python Software Factory. Answered with RAG pipeline.",
    memory_type="short_term",
    category=MemoryCategory.CONTEXT,  # enum, not "interaction"
    metadata={"topic": "factory", "method": "rag"},
)
# Returns: Memory(id="...", user_id="recipe-user", ...)
```

### Step 8: Retrieve Memory

```python
memories = memory.retrieve(
    user_id="recipe-user",
    query="Python Software Factory",
    limit=5,
)
# Returns: list of Memory objects
```

### Step 9: Memory Stats

```python
stats = memory.stats(user_id="recipe-user")
# Returns: MemoryStats(total_memories=1, by_type={"short_term": 1}, ...)
# Note: uses by_type dict, not short_term_count attribute
```

## Success Criteria

- [x] All health checks pass
- [x] Document ingested successfully
- [x] Semantic search returns results
- [x] (If AWS) Embeddings generated
- [x] (If AWS) LLM completion generated
- [x] Memory stored for context
- [x] Memory retrieved and stats available

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| kb | `factory.kb.runtime.runtime.KBRuntime` | `ingest()`, `search()`, `get_collection_stats()` |
| llm_gateway | `factory.llm_gateway.runtime.runtime.LLMRuntime` | `get_provider()`, `get_embedder()` |
| llm_gateway | Provider | `complete()` → `LLMResponse(content=..., usage={...})` |
| llm_gateway | Embedder | `embed([texts])` → `EmbeddingResponse(embeddings=[[...]])` |
| memory | `factory.memory.runtime.runtime.MemoryRuntime` | `store()`, `retrieve()`, `stats()` |
| memory | `factory.memory.core.MemoryCategory` | Enum: `PREFERENCE`, `FACT`, `SUMMARY`, `CONTEXT`, `CUSTOM` |

## Graph-RAG: Entity Extraction During Ingestion

When Neo4j is the vector backend, `kb_ingest` automatically extracts entities and relationships from document text and writes them as graph nodes linked to the source `KBDocument`. This turns your vector store into a knowledge graph — vector search for fuzzy retrieval, graph traversal for precise structural queries.

### How It Works

Entity extraction is **on by default** for Neo4j (`extract_entities: true` in `Neo4jVectorConfig`). Each `ingest()` call:

1. Stores the document and generates embeddings (as before)
2. Runs LLM-based entity extraction via `neo4j-graphrag` pipeline (falls back to raw LLM extraction if the library isn't available)
3. Creates `__Entity__` nodes with typed labels (Person, Organization, Technology, etc.)
4. Links entities to the source document via `HAS_ENTITY` relationships
5. Creates inter-entity relationships extracted from the text

Extraction is best-effort — failures never block the ingest. Results are logged with entity/relationship counts.

### Controlling Extraction

```python
# Per-call override (via MCP tool)
result = kb_ingest(
    content="...",
    extract_entities=True,   # Force on (even if config says False)
)

result = kb_ingest(
    content="...",
    extract_entities=False,  # Skip extraction for this document
)

# Omit the parameter to use the Neo4j config default (True)
result = kb_ingest(content="...")
```

### Querying the Knowledge Graph

Use the `graph` brick's portable typed tools for filtered entity reads,
relationship traversal, and path discovery. Combine `graph_find_entities`,
`graph_get_neighbors`, `graph_find_path`, and `graph_get_stats` rather than
relying on backend-specific query syntax:

```python
# Find all entities extracted from a specific document
graph_query(query_str="""
    MATCH (d:KBDocument {id: $doc_id})-[:HAS_ENTITY]->(e:__Entity__)
    RETURN e.name, e.type, e.description
""", params={"doc_id": "doc-001"})

# Count entity types across the knowledge base
graph_query(query_str="""
    MATCH (e:__Entity__)
    RETURN e.type AS type, count(*) AS count
    ORDER BY count DESC
""")

# Traverse relationships between entities
graph_query(query_str="""
    MATCH (a:__Entity__)-[r]->(b:__Entity__)
    WHERE a.name = $name
    RETURN a.name, type(r), b.name, b.type
""", params={"name": "Python Software Factory"})
```

### When to Use Graph-RAG vs Vector Search

| Use Case | Approach |
|----------|----------|
| "Find documents about authentication" | `kb_search` (vector similarity) |
| "How many organizations are mentioned?" | `graph_find_entities` (filter/count client-side) |
| "What's related to concept X?" | `graph_get_neighbors` / `graph_find_path` |
| "Summarize what we know about topic Y" | `kb_search` → LLM with context |

### Prerequisites

- Neo4j backend configured (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- AWS credentials for Bedrock LLM (entity extraction uses `llm_gateway`)
- Optional: `neo4j-graphrag>=1.0.0` for the optimized pipeline (falls back to raw LLM without it)

### Verifying Entity Extraction

After ingesting with `extract_entities=True`, verify entities and relationships were created:

```python
# 1. Check the ingest result
result = kb_ingest(content="OpenAI was founded by Sam Altman in San Francisco.", extract_entities=True)
assert result["extraction"]["status"] == "success"
assert result["extraction"]["entities_created"] > 0  # 0 = something broke

# 2. Verify entities linked to the document
entities = graph_query(query_str="""
    MATCH (d:KBDocument {id: $doc_id})-[:HAS_ENTITY]->(e:__Entity__)
    RETURN e.name, e.type
""", params={"doc_id": result["document_id"]})
# Expected: Sam Altman (Person), OpenAI (Organization), San Francisco (Location)

# 3. Verify inter-entity relationships
rels = graph_query(query_str="""
    MATCH (a:__Entity__)-[r]->(b:__Entity__)
    WHERE a.name = "Sam Altman"
    RETURN type(r), b.name
""")
```

`ExtractionResult` fields: `document_id` (str), `entities_created` (int), `relationships_created` (int), `entity_types` (list[str]), `status` (`"success"` | `"skipped"` | `"error"`), `message` (str).

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 entities, status `"success"` | Wrong `SimpleKGPipeline` params (old: `kg_creation_mode="from_text"`) | Fixed: now uses `from_pdf=False` |
| status `"error"`, LLM unavailable | Bedrock credentials missing/expired | Check AWS creds, verify `bedrock-runtime` IAM access |
| status `"error"`, Neo4j message | Neo4j connection failed | Verify `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` env vars |
| status `"rejected"` | Empty or whitespace-only content | `KBRuntime.ingest()` rejects empty content before reaching the vector store or entity extractor. Pass non-empty `content` to `kb_ingest` |
| Extraction hangs | Nested event loop deadlock (old: bare `asyncio.run()`) | Fixed: `ThreadPoolExecutor` pattern avoids nested loop |

**Bug fixes applied** (see `entity_extraction.py`):
- `SimpleKGPipeline(from_pdf=False)` — old `kg_creation_mode` param was silently ignored → 0 entities
- `ThreadPoolExecutor` + `asyncio.run()` in worker thread when loop already running
- LLM fallback returns `status="error"` (not `"skipped"`) when provider unavailable
- Extraction failures logged at ERROR (not WARNING) — search for `"Entity extraction failed"`
- Server init no longer swallows `ImportError` with bare `except: pass`

## Without AWS

If no AWS credentials:
- Skip steps 4 and 6 (embeddings and completion)
- Test kb ingestion and search with fallback text search
- Report: "Tested kb + memory, skipped LLM (no AWS)"
