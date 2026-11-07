# Memory: Use Companion X (NOT a-mem)

All agent memory operations MUST go through the Companion X memory brick via the `companion-x` Kiro power. Do NOT use `mcp_a_mem_*` tools — a-mem is disabled.

## Store a memory

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_store",
  arguments='{"content": "...", "category": "fact", "metadata": {"source": "agent"}}'
)
```

Categories: `preference`, `fact`, `summary`, `context`, `custom`

Omit `user_id`: memories are stored and read under the authenticated principal (the signed-in UI user, or `local-operator` locally). Pass it only to act on another principal explicitly.

## Search memories (semantic)

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_retrieve",
  arguments='{"query": "...", "limit": 5}'
)
```

## Search by time

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_search_by_time",
  arguments='{"time_from": "2026-03-01T00:00:00Z", "time_to": "2026-03-10T00:00:00Z", "limit": 10}'
)
```

## Hybrid search (semantic + graph + temporal)

```
call_brick_tool(
  brick_name="memory",
  tool_name="memory_hybrid_search",
  arguments='{"query": "...", "limit": 10}'
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
- **Local dev backend:** in-process memory (`MEMORY_BACKEND=memory`) or the persistent NetworkX graph store (`MEMORY_BACKEND=graph`) — no containers needed. The ChromaDB A-MEM adapter was retired in #353.
- Fail-fast: store is atomic — embedding + keywords + tags all succeed or the memory is rolled back
- Graph edges: EVOLVED_FROM, RELATED_TO, FOLLOWED_BY, HAS_MEMORY
- AWS creds must be active for writes and semantic search when using the Neo4j backend (see Troubleshooting below)

## Which operations need Bedrock?

When using the **Neo4j backend** (full stack / Docker):
- WRITES (need Bedrock): `memory_store`, `memory_evolve` — these call Bedrock Titan for embeddings and Claude for content analysis
- SEMANTIC READS (need Bedrock): `memory_retrieve`, `memory_hybrid_search` — the MCP server embeds the query vector via Bedrock before searching Neo4j
- PURE NEO4J READS (no Bedrock): `memory_get`, `memory_search_by_time`, `memory_stats`, `memory_delete`, `memory_delete_user` — these query Neo4j directly

When using the **in-process or graph backend** (local dev): embeddings use the local keyword-hash embedder unless `MEMORY_LOCAL_EMBED_MODEL` names a GGUF file. No Bedrock calls needed for any operation.

## Troubleshooting empty results

**In-process / graph backend (local dev):**
- `MEMORY_BACKEND=memory` loses data on restart by design; `MEMORY_BACKEND=graph` persists to the local Storage blob store snapshot.
- No AWS creds or Docker restarts needed.

**Neo4j backend (full stack / Docker):**
If `memory_retrieve` returns `[]` but you know memories exist:
1. The MCP server's boto3 session likely has stale AWS creds
2. Fix: `docker restart companion_x-companion_x-mcp-1` (restarts the server so it picks up fresh `~/.aws/credentials`)
3. Do NOT auth multiple AWS profiles — the container reads `AWS_PROFILE` from `.env`, just refresh that one profile
4. Fallback: use `memory_search_by_time` which doesn't need embeddings

## AWS credentials

When using the Neo4j backend (full stack / Docker):
- All AWS accounts in this workspace have Bedrock access — do not assume otherwise
- The Docker containers read `AWS_PROFILE` from `projects/companion_x/.env` and mount `~/.aws:/root/.aws:ro`

When using the in-process or graph backend (local dev): no AWS creds needed for memory operations.

### Refresh commands


- After refreshing, restart any running containers: `docker restart companion_x-companion_x-mcp-1`
