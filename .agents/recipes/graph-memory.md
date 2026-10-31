# Recipe: Graph Memory

Validates Neo4j-backed agent memory with HNSW vector search, A-MEM Zettelkasten evolution, and cross-domain linking.

## Bricks Used
- `memory` — Agent memory with Neo4j graph backend, HNSW vector search, A-MEM evolution
- `llm_gateway` — LLM completions for content analysis and evolution decisions
- `graph` — (optional) Verify graph structure via Cypher queries

## Architecture

Two classes form the storage layer:
- `Neo4jMemoryStore` — CRUD + temporal `FOLLOWED_BY` edges between sequential memories per user
- `Neo4jEmbeddingMemoryStore` — Wraps base store, adds HNSW vector embeddings + A-MEM evolution

Evolution flow on each `memory_store`: embed content → `analyze_content` (LLM extracts keywords/context/tags) → `set_evolution_properties` on node → `_find_neighbors` (HNSW vector search) → `EvolutionEngine.analyze` (LLM decides connections) → `_apply_evolution_result` (creates `RELATED_TO` edges, updates neighbor context/tags, creates `EVOLVED_FROM` trail).

Cross-domain linking runs independently: vector similarity finds `KBDocument` nodes → `REFERENCES` edges; keyword match finds `Finding` nodes → `MENTIONS` edges.

Backfill: `memory_evolve` MCP tool re-runs evolution on memories that missed it (expired creds, LLM failures).

## Scenario

Store memories with evolution, verify graph edges (temporal, semantic, version trail), test semantic retrieval, and backfill unevolved memories.

## Prerequisites

- Neo4j running and configured (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- AWS credentials available (for Bedrock LLM completions + embeddings)
- Memory brick configured with `neo4j` backend and embeddings enabled

## AWS Detection

```python
import boto3
try:
    boto3.client('sts').get_caller_identity()
    AWS_AVAILABLE = True
except:
    AWS_AVAILABLE = False
```

If `AWS_AVAILABLE` is False, skip evolution steps and report.

## Steps

### Step 1: Initialize and Health Check

```python
from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
from factory.memory.runtime.embedding import LLMGatewayEmbedder
from factory.memory.runtime.runtime import MemoryRuntime
from factory.llm_gateway.runtime.runtime import LLMRuntime

base = Neo4jMemoryStore()  # reads NEO4J_URI/USER/PASSWORD from env
embedder = LLMGatewayEmbedder(backend="bedrock")
llm_runtime = LLMRuntime()
provider = llm_runtime.get_provider("bedrock", region_name="us-east-1")
llm_complete = lambda prompt: provider.complete(prompt, max_tokens=1024).content

store = Neo4jEmbeddingMemoryStore(base=base, embedder=embedder, llm_complete=llm_complete)
runtime = MemoryRuntime(store=store)
health = runtime.health_check()
# Returns: MemoryHealth(healthy=True, backend="neo4j",
#   message="Neo4j connected (embeddings: enabled, evolution: enabled)")
```

### Step 2: Store Memories with Evolution

```python
from factory.memory.core import MemoryCategory

m1 = runtime.store(user_id="recipe-user", content="Neo4j uses Cypher as its query language for graph traversal",
    memory_type="long_term", category=MemoryCategory.FACT.value, metadata={"topic": "databases"})
m2 = runtime.store(user_id="recipe-user", content="HNSW indexes enable fast approximate nearest neighbor search",
    memory_type="long_term", category=MemoryCategory.FACT.value, metadata={"topic": "vector-search"})
m3 = runtime.store(user_id="recipe-user", content="Graph databases excel at relationship-heavy queries compared to relational DBs",
    memory_type="short_term", category=MemoryCategory.CONTEXT.value, metadata={"topic": "databases"})
# Each store triggers: embed → content analysis (LLM) → evolution properties → neighbor search → evolution decision
```

### Step 3: Verify Evolution Properties

```python
mem = runtime.get(m1.id)
# metadata carries evolution properties: keywords, context, tags, evolution_status
assert "keywords" in mem.metadata, "Evolution should populate keywords"
assert "context" in mem.metadata, "Evolution should populate context"
assert mem.metadata.get("evolution_status") in ("success", "failed")
```

### Step 4: Verify Temporal Edges (FOLLOWED_BY)

```python
# FOLLOWED_BY links sequential memories for the same user
graph_query(query_str="""
    MATCH (a:Memory {user_id: $uid})-[:FOLLOWED_BY]->(b:Memory)
    RETURN a.id AS from_id, b.id AS to_id ORDER BY a.created_at
""", params={"uid": "recipe-user"})  # Expected: m1→m2, m2→m3
```

### Step 5: Verify RELATED_TO Edges

```python
graph_query(query_str="""
    MATCH (a:Memory)-[r:RELATED_TO]->(b:Memory) WHERE a.user_id = $uid
    RETURN a.id AS from_id, b.id AS to_id, r.reason
""", params={"uid": "recipe-user"})  # Expected: edges between m1↔m3 (both about databases)
```

### Step 6: Verify EVOLVED_FROM Trail

```python
# EVOLVED_FROM points from updated neighbor TO the memory that triggered the update
graph_query(query_str="""
    MATCH (neighbor:Memory)-[r:EVOLVED_FROM]->(trigger:Memory) WHERE neighbor.user_id = $uid
    RETURN neighbor.id AS updated_id, trigger.id AS trigger_id, r.trigger AS action
""", params={"uid": "recipe-user"})
```

### Step 7: Semantic Retrieval

```python
results = runtime.retrieve(user_id="recipe-user", query="graph query languages", limit=5, min_relevance=0.3)
# HNSW vector search ranked by cosine similarity; falls back to text CONTAINS if vector fails
assert len(results) > 0 and results[0].relevance_score >= 0.3
```

### Step 8: Evolution Backfill

```python
# MCP tool: memory_evolve(user_id="recipe-user") — re-runs evolution on unevolved memories
from factory.memory.runtime.evolve_backfill import fetch_unevolved_memories, evolve_memories
records = fetch_unevolved_memories(base.driver, base.database, "recipe-user")
if records:
    result = evolve_memories(base.driver, base.database, "recipe-user",
        llm_complete, embedder, lambda c, u: lambda: runtime.retrieve(user_id=u, query=c, limit=5), records)
    # Returns: {"evolved_count": N, "failed_count": M, "details": [...]}
```

### Step 9: Cross-Domain Linking (Optional)

```python
# REFERENCES: Memory→KBDocument (vector similarity >= 0.6); MENTIONS: Memory→Finding (keyword match)
graph_query(query_str="""
    MATCH (m:Memory)-[r:REFERENCES]->(d:KBDocument) RETURN m.id, d.id, r.score
    UNION ALL
    MATCH (m:Memory)-[r:MENTIONS]->(f:Finding) RETURN m.id, f.id, r.score
""")
```

### Step 10: Stats and Cleanup

```python
stats = runtime.stats(user_id="recipe-user")
# Returns: MemoryStats(total_memories=3, by_type={"long_term": 2, "short_term": 1}, ...)
assert stats.total_memories == 3

deleted = runtime.delete_user_memories("recipe-user")
assert deleted == 3
```

## Success Criteria

- [ ] Health check returns `healthy=True` with embeddings and evolution enabled
- [ ] Memories stored with evolution properties (keywords, context, tags)
- [ ] FOLLOWED_BY temporal edges link sequential memories
- [ ] RELATED_TO edges created between semantically related memories
- [ ] EVOLVED_FROM trail records neighbor updates
- [ ] Semantic retrieval returns ranked results via HNSW
- [ ] (If applicable) Evolution backfill processes unevolved memories
- [ ] (If KBDocument/Finding exist) Cross-domain REFERENCES/MENTIONS edges created
- [ ] Stats accurate, cleanup removes all user memories

## API Reference

| Tool | Parameters | Returns |
|------|-----------|---------|
| `memory_store` | content, user_id, memory_type, category, metadata, ttl_seconds | Memory dict with id, evolution metadata |
| `memory_retrieve` | query, user_id, memory_type, category, min_relevance, limit | List of Memory dicts with relevance_score |
| `memory_get` | memory_id | Memory dict or null |
| `memory_evolve` | user_id, memory_ids (optional) | `{evolved_count, failed_count, details}` |
| `memory_hybrid_search` | user_id, query, anchor_memory_id, limit, semantic/structural/traversal weights | `{results, count}` |
| `memory_search_by_time` | user_id, time_from, time_to, query, limit | `{results, count}` |
| `memory_embed_backfill` | user_id, limit | `{user_id, embedded, total_checked}` |
| `memory_stats` | user_id (optional) | MemoryStats dict |
| `memory_consolidate` | user_id | `{user_id, consolidated_count}` |
| `memory_delete` | memory_id | `{memory_id, deleted}` |
| `memory_delete_user` | user_id | `{user_id, deleted_count}` |

## Without AWS

If no AWS credentials:
- Skip steps requiring LLM (2, 3, 5, 6, 8) — evolution needs LLM completions + embeddings
- Test basic CRUD via `MemoryRuntime()` with default in-memory backend (no Neo4j needed)
- Temporal edges (step 4) require Neo4j but not AWS
- Report: "Tested basic CRUD, skipped evolution/embeddings (no AWS)"
