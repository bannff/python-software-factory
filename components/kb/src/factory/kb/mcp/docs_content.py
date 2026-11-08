"""String constants for knowledge base documentation."""

KB_OVERVIEW = """# Knowledge Base Brick

The KB brick provides document storage and vector search for the Python Factory.

## Features

- Document ingestion and storage
- Collection management
- Vector search with Neo4j HNSW (plus graph and Bedrock KB backends)
- Graph-RAG entity extraction (Neo4j backend — auto-builds knowledge graph on ingest)
- Metadata filtering
- Context envelope support

## Architecture

```
kb/
├── runtime/
│   ├── runtime.py, collections.py, models.py, envelope.py
│   └── retrieval/  # neo4j_vector.py, graph.py, bedrock.py, entity_extraction.py
└── mcp/tools/
```

## Key Concepts

### Documents
Documents are the primary unit of storage. Each document has:
- Unique ID
- Content (text)
- Metadata (key-value pairs)
- Optional embeddings

### Collections
Collections group related documents. Each collection has:
- Configuration (chunking, embedding settings)
- Statistics (document count, size)

### Context Envelopes
Envelopes wrap search results with context for LLM consumption."""
NEO4J_GUIDE = """# Neo4j Vector Integration

The KB brick stores documents and embeddings in Neo4j and searches them with
HNSW cosine similarity. ChromaDB was retired in #353.

## Configuration

```bash
export KB_BACKEND=neo4j   # neo4j | graph | bedrock; anything else fails closed
```

## Features

- Automatic embedding generation
- Similarity search with cosine distance
- Metadata filtering
- Persistent storage

## Usage

```python
# Search with vector similarity
results = kb.search(
    query="machine learning concepts",
    collection_id="docs",
    top_k=5,
    filters={"category": "tutorial"}
)
```

## Best Practices

Use meaningful collection names, add rich metadata for filtering, and chunk
large documents appropriately.
4. Monitor collection sizes"""
COLLECTIONS_GUIDE = """# Collection Management

Collections organize documents by topic or purpose.

## Creating Collections

```python
# Via authoring tools (requires KB_ENABLE_AUTHORING_TOOLS=1)
kb.authoring_upsert_collection(
    collection_id="tutorials",
    name="Tutorial Documents",
    description="How-to guides and tutorials",
    chunk_size=500,
    chunk_overlap=50
)
```

## Collection Configuration

- `chunk_size`: Maximum tokens per chunk
- `chunk_overlap`: Overlap between chunks
- `embedding_model`: Model for embeddings

## Listing Collections

```python
registry = kb.get_collection_registry()
for collection in registry["collections"]:
    print(f"{collection['id']}: {collection['name']}")
```"""
SEARCH_GUIDE = """# Search Operations

The KB brick supports multiple search modes.

## Vector Search

Semantic similarity search using embeddings:

```python
results = kb.search(
    query="How do I configure authentication?",
    collection_id="docs",
    top_k=10
)
```

## Metadata Filtering

Combine vector search with metadata filters:

```python
results = kb.search(
    query="deployment guide",
    collection_id="docs",
    filters={"type": "guide", "version": "2.0"}
)
```

## Search Results

Results include:
- Document ID and content
- Relevance score
- Metadata
- Context envelope for LLM use"""
GRAPH_RAG_GUIDE = """# Graph-RAG Entity Extraction

When Neo4j is the backend, document ingestion automatically extracts entities
and relationships via LLM, building a knowledge graph alongside the vector index.

## Why Both Vector + Graph?

Vector search finds semantically similar documents — great for fuzzy retrieval.
But it can't answer structural questions: "How many organizations are mentioned?"
or "What connects concept A to concept B?" The knowledge graph handles those
via Cypher queries through the `storage` brick's `storage_graph_query` tool.

## How It Works

On `kb_ingest`, the Neo4j vector store:
1. Stores the document and generates embeddings
2. Runs entity extraction via `neo4j-graphrag` pipeline (or raw LLM fallback)
3. Creates `__Entity__` nodes and links them to `KBDocument` via `HAS_ENTITY`
4. Creates inter-entity relationships from the text

Extraction is best-effort — failures are logged but never block ingestion.

## Configuration

Entity extraction is **on by default** for Neo4j (`extract_entities: true`).

Override per-call:
```python
# Force extraction off for a specific document
kb_ingest(content="...", extract_entities=False)

# Force extraction on (even if config default is False)
kb_ingest(content="...", extract_entities=True)
```

## Querying the Graph

Use the `storage` brick's `storage_graph_query` tool with Cypher:

```python
# Entities from a document
storage_graph_query(cypher=\"\"\"
    MATCH (d:KBDocument {id: $id})-[:HAS_ENTITY]->(e:__Entity__)
    RETURN e.name, e.type
\"\"\", params={"id": "doc-001"})

# Count entity types
storage_graph_query(cypher=\"\"\"
    MATCH (e:__Entity__)
    RETURN e.type, count(*) AS n ORDER BY n DESC
\"\"\")
```

## Requirements

- Neo4j backend (bolt://...)
- AWS credentials for Bedrock LLM (extraction uses `llm_gateway`)
- Optional: `neo4j-graphrag>=1.0.0` for optimized pipeline"""
