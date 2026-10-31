# Recipe: KB Graph-RAG: Entity Extraction Pipeline

Validates the Graph-RAG entity extraction pipeline — turning ingested documents into a traversable knowledge graph alongside vector search.

## Bricks Used
- `kb` — Knowledge base with Neo4j vector store + entity extraction
- `graph` — Portable graph entity and relationship reads for verification
- `llm_gateway` — LLM completions for entity extraction

## Architecture

When documents are ingested into a Neo4j-backed KB, the `EntityExtractor` automatically extracts named entities and relationships from the text and writes them as graph nodes. This turns the vector store into a knowledge graph — vector search for fuzzy retrieval, graph traversal for precise structural queries.

The extraction pipeline runs inside `Neo4jVectorStore.add()`:

```
ingest() → VectorStore.add()
             ├── MERGE KBDocument node
             ├── Generate embedding (if embed_on_ingest)
             └── EntityExtractor.extract_and_store() (if extract_entities)
                   ├── Path A: SimpleKGPipeline (neo4j-graphrag, preferred)
                   │     └── _link_entities_to_document() — links orphan __Entity__ nodes to KBDocument
                   └── Path B: Raw LLM fallback
                         └── _write_entities_to_neo4j() — manual MERGE of entities + relationships
```

Key design points:
- Two extraction paths: `neo4j-graphrag` `SimpleKGPipeline` (preferred) or raw LLM fallback via `_EXTRACTION_PROMPT`. The graphrag path is used when `neo4j-graphrag>=1.0.0` is installed; otherwise falls back automatically.
- Creates `__Entity__` nodes with typed labels (`Person`, `Organization`, `Location`, `Event`, `Concept`, `Technology`, `Document`).
- Links entities to source `KBDocument` via `HAS_ENTITY` relationships.
- Creates inter-entity relationships extracted from text (e.g., `FOUNDED`, `LOCATED_IN`).
- On `delete()`, orphaned `__Entity__` nodes (no remaining `HAS_ENTITY` edges) are cleaned up automatically.
- Extraction is best-effort — failures never block the ingest. Errors are logged at WARNING level and an `ExtractionResult` with `status="error"` is returned.
- When an event loop is already running (e.g., inside an async server), the graphrag pipeline runs in a `ThreadPoolExecutor` to avoid nested `asyncio.run()` deadlocks.

## Scenario

Ingest documents with entity extraction, verify the knowledge graph, query entities via Cypher, demonstrate shared entities across documents, and validate orphan cleanup on delete.

## Prerequisites

- Neo4j running and configured (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- AWS credentials available (for Bedrock LLM — entity extraction and embeddings)
- Optional: `neo4j-graphrag>=1.0.0` (falls back to raw LLM without it)

## AWS Detection

```python
import boto3
try:
    boto3.client('sts').get_caller_identity()
    AWS_AVAILABLE = True
except:
    AWS_AVAILABLE = False
```

If `AWS_AVAILABLE` is False, skip all steps — entity extraction requires LLM access.

## Steps

### Step 1: Initialize KB with Neo4j Backend

```python
import tempfile
from factory.kb.runtime.runtime import KBRuntime
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorStore, Neo4jVectorConfig
from factory.kb.runtime.retrieval.neo4j_embedding import LLMGatewayKBEmbedder

cfg = Neo4jVectorConfig(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    extract_entities=True,  # default — enables extraction for all ingests
)
embedder = LLMGatewayKBEmbedder()  # uses llm_gateway Bedrock adapter
store = Neo4jVectorStore(cfg, embedder=embedder)

kb = KBRuntime(config_dir=tempfile.mkdtemp())
kb.set_vector_store(store)
```

### Step 2: Ingest with Entity Extraction

```python
result = kb.ingest(
    content="OpenAI was founded by Sam Altman in San Francisco. The company develops GPT models.",
    document_id="doc-001",
    source="recipe-test",
    extract_entities=True,  # can omit — config default is True
)
# Returns: IngestResult(
#   document_id="doc-001",
#   status="ingested",
#   chunks_created=1,
#   extraction_status="success",    # "success" | "skipped" | "error" | "failed"
#   entities_created=4,             # e.g. Sam Altman, OpenAI, San Francisco, GPT
#   relationships_created=3,        # e.g. FOUNDED, LOCATED_IN, DEVELOPS
#   extraction_message="Extracted via neo4j-graphrag pipeline",
# )
```

### Step 3: Verify Entities via graph_query

```python
# Find all entities linked to a document
graph_query(query_str="""
    MATCH (d:KBDocument {id: $doc_id})-[:HAS_ENTITY]->(e:__Entity__)
    RETURN e.name AS name, e.type AS type, e.description AS description
""", params={"doc_id": "doc-001"})
# Expected: Sam Altman (Person), OpenAI (Organization), San Francisco (Location), GPT (Technology)

# Count entity types across the knowledge base
graph_query(query_str="""
    MATCH (e:__Entity__)
    RETURN e.type AS type, count(*) AS count
    ORDER BY count DESC
""")

# Traverse inter-entity relationships
graph_query(query_str="""
    MATCH (a:__Entity__)-[r]->(b:__Entity__)
    WHERE a.name = $name
    RETURN a.name AS source, type(r) AS relationship, b.name AS target, b.type AS target_type
""", params={"name": "Sam Altman"})
# Expected: Sam Altman -[FOUNDED]-> OpenAI, Sam Altman -[LOCATED_IN]-> San Francisco
```

### Step 4: Query the Knowledge Graph

Practical Cypher patterns for working with extracted entities:

```python
# Find all Person entities
graph_query(query_str="""
    MATCH (e:__Entity__ {type: "Person"})
    RETURN e.name AS name, e.description AS description
""")

# Find what organizations a person is connected to
graph_query(query_str="""
    MATCH (p:__Entity__ {name: $name})-[r]->(o:__Entity__ {type: "Organization"})
    RETURN o.name AS organization, type(r) AS relationship
""", params={"name": "Sam Altman"})

# Find all entities of a specific type with their source documents
graph_query(query_str="""
    MATCH (d:KBDocument)-[:HAS_ENTITY]->(e:__Entity__ {type: $entity_type})
    RETURN e.name AS entity, d.id AS document_id, d.source AS source
""", params={"entity_type": "Technology"})
```

### Step 5: Ingest Another Document (Shared Entities)

Entities from different documents can overlap — the same `__Entity__` node gets linked to multiple `KBDocument` nodes via separate `HAS_ENTITY` edges.

```python
result2 = kb.ingest(
    content="Sam Altman spoke at a conference in New York about OpenAI's mission.",
    document_id="doc-002",
    source="recipe-test",
)
# "Sam Altman" and "OpenAI" already exist as __Entity__ nodes.
# They get MERGE'd (not duplicated) and linked to doc-002 via new HAS_ENTITY edges.

# Verify shared entities span both documents
graph_query(query_str="""
    MATCH (d:KBDocument)-[:HAS_ENTITY]->(e:__Entity__ {name: $name})
    RETURN e.name AS entity, collect(d.id) AS documents
""", params={"name": "Sam Altman"})
# Expected: entity="Sam Altman", documents=["doc-001", "doc-002"]
```

### Step 6: Delete Document and Verify Orphan Cleanup

```python
# Delete doc-001
kb.delete_document("doc-001")

# "San Francisco" was only linked to doc-001 → orphaned → auto-deleted
# "Sam Altman" is still linked to doc-002 → preserved

# Verify orphan cleanup
graph_query(query_str="""
    MATCH (e:__Entity__ {name: "San Francisco"})
    RETURN count(e) AS count
""")
# Expected: count=0 (orphan cleaned up)

graph_query(query_str="""
    MATCH (e:__Entity__ {name: "Sam Altman"})
    RETURN count(e) AS count
""")
# Expected: count=1 (still linked to doc-002)
```

The cleanup query in `Neo4jVectorStore.delete()`:
```cypher
MATCH (e:__Entity__) WHERE NOT (e)<-[:HAS_ENTITY]-() DELETE e
```

### Step 7: Controlling Extraction

The `extract_entities` parameter follows a three-level precedence:

```python
# 1. Per-call override — force ON
result = kb.ingest(content="...", extract_entities=True)

# 2. Per-call override — force OFF
result = kb.ingest(content="...", extract_entities=False)

# 3. Omit parameter — uses Neo4jVectorConfig.extract_entities (default: True)
result = kb.ingest(content="...")
```

Resolution logic in `Neo4jVectorStore.add()`:
```python
should_extract = extract_entities if extract_entities is not None else cfg.extract_entities
```

## ExtractionResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | `str` | ID of the source document |
| `entities_created` | `int` | Number of `__Entity__` nodes created (default: 0) |
| `relationships_created` | `int` | Number of inter-entity relationships created (default: 0) |
| `entity_types` | `list[str]` | Distinct entity types found (e.g., `["Organization", "Person"]`) |
| `status` | `str` | `"success"`, `"skipped"`, or `"error"` |
| `message` | `str` | Human-readable detail (e.g., `"Extracted via neo4j-graphrag pipeline"`) |

`IngestResult` surfaces extraction data via: `extraction_status`, `entities_created`, `relationships_created`, `extraction_message`.

## Success Criteria

- [x] Neo4j backend initialized with entity extraction enabled
- [x] Document ingested with `extraction_status == "success"`
- [x] `__Entity__` nodes created with correct types
- [x] `HAS_ENTITY` relationships link entities to source document
- [x] Inter-entity relationships extracted from text
- [x] Shared entities linked to multiple documents (no duplicates)
- [x] Orphaned entities cleaned up on document delete
- [x] Per-call `extract_entities` override works

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 entities, status `"success"` | Wrong `SimpleKGPipeline` params (old: `kg_creation_mode="from_text"`) | Fixed: now uses `from_pdf=False` |
| status `"error"`, LLM unavailable | Bedrock credentials missing or expired | Check AWS creds, verify `bedrock-runtime` IAM access |
| status `"error"`, Neo4j message | Neo4j connection failed | Verify `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` env vars |
| status `"rejected"` | Empty or whitespace-only content | `KBRuntime.ingest()` rejects empty content at the runtime level before reaching the vector store or entity extractor. Pass non-empty `content` to `ingest()` |
| Extraction hangs | Nested event loop deadlock | Fixed: `ThreadPoolExecutor` pattern avoids nested `asyncio.run()` |
| `ImportError: neo4j` | Neo4j driver not installed | `pip install neo4j` |
| Fallback path used unexpectedly | `neo4j-graphrag` not installed | `pip install neo4j-graphrag>=1.0.0` for preferred pipeline |
| `extraction_status` is `None` | Vector store is not Neo4j (e.g., Chroma) | Entity extraction only runs on `Neo4jVectorStore` |

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| kb | `factory.kb.runtime.runtime.KBRuntime` | `ingest(extract_entities=)`, `delete_document()`, `search()` |
| kb | `factory.kb.runtime.retrieval.neo4j_vector.Neo4jVectorStore` | `add(document, extract_entities=)`, `delete()` |
| kb | `factory.kb.runtime.retrieval.neo4j_vector.Neo4jVectorConfig` | `extract_entities`, `embed_on_ingest`, `node_label` |
| kb | `factory.kb.runtime.retrieval.entity_extraction.EntityExtractor` | `extract_and_store(document_id, content, metadata)` |
| kb | `factory.kb.runtime.retrieval.neo4j_embedding.KBEmbedder` | Protocol: `embed(texts)`, `dimensions` property |
| kb | `factory.kb.runtime.retrieval.neo4j_embedding.LLMGatewayKBEmbedder` | Adapter: Bedrock embeddings via `llm_gateway` |
| kb | `factory.kb.runtime.models.ExtractionResult` | `document_id`, `entities_created`, `relationships_created`, `entity_types`, `status`, `message` |
| kb | `factory.kb.runtime.models.IngestResult` | `extraction_status`, `entities_created`, `relationships_created`, `extraction_message` |
| graph | MCP tools `graph_find_entities`, `graph_get_neighbors`, `graph_find_path` | typed flat parameters |
| llm_gateway | `factory.llm_gateway.runtime.runtime.LLMRuntime` | `get_provider()`, `get_embedder()` |

## Without AWS

Entity extraction requires LLM access (Bedrock). Without AWS credentials:
- Ingestion still works — documents are stored and (if possible) embedded
- Entity extraction returns `status="error"` with `message="LLM unavailable: ..."`
- Graph queries still work on any previously extracted entities
- Report: "Tested kb ingest + search, skipped entity extraction (no AWS)"
