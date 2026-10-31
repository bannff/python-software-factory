# Memory: Use the control-plane runtime (NOT a-mem)

All agent memory operations MUST go through the the control-plane runtime memory brick via the `the control-plane runtime` Kiro power. Do NOT use `mcp_a_mem_*` tools — a-mem is disabled.

## Store a memory

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_store",
  arguments='{"content": "...", "user_id": "kiro-agent", "category": "fact", "metadata": {"source": "agent"}}'
)
```

Categories: `preference`, `fact`, `summary`, `context`, `custom`

IMPORTANT: Always pass `"user_id": "kiro-agent"` explicitly. There is no envelope auth in the current setup.

## Search memories (semantic)

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_retrieve",
  arguments='{"query": "...", "user_id": "kiro-agent", "limit": 5}'
)
```

## Search by time

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_search_by_time",
  arguments='{"user_id": "kiro-agent", "time_from": "2026-03-01T00:00:00Z", "time_to": "2026-03-10T00:00:00Z", "limit": 10}'
)
```

## Hybrid search (semantic + graph + temporal)

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_hybrid_search",
  arguments='{"user_id": "kiro-agent", "query": "...", "limit": 10}'
)
```

## Delete a memory

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_delete",
  arguments='{"memory_id": "..."}'
)
```

## Key facts

- **Full stack backend:** Neo4j with 1024-dim Bedrock Titan embeddings
- **Local dev backend:** ChromaDB A-MEM (`FACTORY_MEMORY_ADAPTER=amem`), persists to `./chroma_memory/` on disk — no containers needed. Uses ChromaDB's built-in `all-MiniLM-L6-v2` sentence-transformers model for embeddings, so no external embedding API is required for local dev.
- Fail-fast: store is atomic — embedding + keywords + tags all succeed or the memory is rolled back
- Graph edges: EVOLVED_FROM, RELATED_TO, FOLLOWED_BY, HAS_MEMORY
- AWS creds must be active for writes and semantic search when using the Neo4j backend (see Troubleshooting below)

## Which operations need Bedrock?

When using the **Neo4j backend** (full stack / Docker):
- WRITES (need Bedrock): `memory_store`, `memory_evolve` — these call Bedrock Titan for embeddings and Claude for content analysis
- SEMANTIC READS (need Bedrock): `memory_retrieve`, `memory_hybrid_search` — the MCP server embeds the query vector via Bedrock before searching Neo4j
- PURE NEO4J READS (no Bedrock): `memory_get`, `memory_search_by_time`, `memory_stats`, `memory_delete`, `memory_delete_user` — these query Neo4j directly

When using the **ChromaDB A-MEM backend** (local dev): embeddings are handled locally by ChromaDB's built-in `all-MiniLM-L6-v2` model. No Bedrock calls needed for any operation.

## Troubleshooting empty results

**ChromaDB A-MEM backend (local dev):**
- Data persists to `./chroma_memory/`. If results are empty, check the directory exists and has data.
- No AWS creds or Docker restarts needed.

**Neo4j backend (full stack / Docker):**
If `memory_retrieve` returns `[]` but you know memories exist:
1. The MCP server's boto3 session likely has stale AWS creds
2. Fix: `docker restart the control-plane project-the control-plane project-mcp-1` (restarts the server so it picks up fresh `~/.aws/credentials`)
3. Do NOT auth multiple AWS profiles — the container reads `AWS_PROFILE` from `.env`, just refresh that one profile
4. Fallback: use `memory_search_by_time` which doesn't need embeddings

## AWS credentials

When using the Neo4j backend (full stack / Docker):
- All AWS accounts in this workspace have Bedrock access — do not assume otherwise
- The Docker containers read `AWS_PROFILE` from `projects/the control-plane project/.env` and mount `~/.aws:/root/.aws:ro`

When using ChromaDB A-MEM (local dev): no AWS creds needed for memory operations.

### Refresh commands


- After refreshing, restart any running containers: `docker restart the control-plane project-the control-plane project-mcp-1`
