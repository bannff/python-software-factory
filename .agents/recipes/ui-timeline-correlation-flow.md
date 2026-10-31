# Recipe: Timeline Correlation Flow

Validates the lightweight local correlation story with no heavy external dependencies: two local runs are persisted into graph-backed history and remain visually separable by run identity in the Timeline pipeline.

## Bricks Used
- `api` - AG-UI ingress and SSE transport
- `agent` - `agent_reason` execution path
- `mcp_server` - graph sink materialization and session lineage
- `mcp_utils` - shared envelope/run correlation contract
- `graph` - lightweight in-memory history persistence via `networkx`

## Scenario

Two local runs are materialized through the graph sink against the lightweight `networkx` graph backend. The resulting `ToolInvocation` entities should carry the correct run/session identity, remain queryable through `graph_query`, and stay separated by `workflow_run_id` for Timeline grouping.

## Prerequisites

- No AWS required
- No Neo4j, Docker, or external graph service required
- AG-UI route available through the API base or a FastAPI test harness, or direct graph-sink invocation for the lower-level flow
- `TELEMETRY_GRAPH_SINK=true`
- `GRAPH_BACKEND=networkx` or an explicit in-memory graph runtime in the test harness

## Flow A: AG-UI Ingress Correlation

### Step 1: Register the AG-UI route

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from factory.api.runtime.ag_ui_routes import register_ag_ui_routes

app = FastAPI()
register_ag_ui_routes(app)
client = TestClient(app)
```

### Step 2: Arrange a tool call during the AG-UI run

```python
from factory.mcp_server.runtime import graph_sink

captured = []

async def fake_call(tool_name: str, arguments: dict):
    if tool_name == "ui_ui_start_session":
        return {"session_id": arguments["session_id"]}
    if tool_name == "agent_reason":
        graph_sink.materialize(
            "agent",
            "agent_reason",
            success=True,
            latency_ms=12.5,
            caller="ag_ui",
        )
        return {"text": "ok"}
    if tool_name == "ui_ui_end_session":
        return None
    return None
```

### Step 3: Execute the AG-UI run with explicit correlation IDs

```python
payload = {
    "threadId": "thread-99",
    "runId": "run-99",
    "messages": [{"role": "user", "content": "x"}],
}

resp = client.post("/ag-ui/run", content=json.dumps(payload))
_ = resp.text  # consume SSE stream
```

### Step 4: Inspect the materialized history writes

```python
tool_invocation = next(
    item for item in captured if item.get("entity_type") == "ToolInvocation"
)
session = next(
    item for item in captured if item.get("entity_type") == "Session"
)
relation = next(
    item for item in captured if item.get("relationship_type") == "CONTAINS_INVOCATION"
)
```

### Step 5: Verify the correlation contract at the history layer

```python
assert tool_invocation["properties"]["session_id"] == "thread-99"
assert tool_invocation["properties"]["workflow_run_id"] == "run-99"
assert tool_invocation["properties"]["caller"] == "ag_ui"
assert session["entity_id"] == "session-thread-99"
assert relation["source_id"] == "session-thread-99"
assert relation["target_id"] == tool_invocation["entity_id"]
```

## Flow B: Lightweight Two-Run Persisted History

### Step 1: Build a lightweight graph tool map

```python
import asyncio

from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import GraphRuntime

server = create_mcp_server(GraphRuntime(config={"default_backend": "networkx"}))
graph_tools = {
    name: asyncio.run(server.get_tool(name))
    for name in [
        "graph_add_entity",
        "graph_add_relationship",
        "graph_query",
        "graph_get_neighbors",
    ]
}
```

### Step 2: Materialize two runs through graph sink

```python
from unittest.mock import MagicMock, patch

from factory.mcp_server.runtime import graph_sink
from factory.mcp_utils.interface import push_envelope_updates, reset_envelope

queue_mock = MagicMock()
queue_mock.put.side_effect = lambda fn: fn()

graph_sink._graph_runtime = graph_tools

with patch.object(graph_sink, "_ensure_drain_thread"), \
     patch.object(graph_sink, "_SINK_QUEUE", queue_mock):
    token = push_envelope_updates(
        session_id="session-a",
        principal_id="principal-1",
        run_id="run-a",
    )
    try:
        graph_sink.materialize("agent", "agent_reason", success=True, latency_ms=12.5, caller="ag_ui")
        graph_sink.materialize("cache", "cache_get", success=True, latency_ms=3.0, caller="ag_ui")
    finally:
        reset_envelope(token)

    token = push_envelope_updates(
        session_id="session-b",
        principal_id="principal-1",
        run_id="run-b",
    )
    try:
        graph_sink.materialize("agent", "agent_reason", success=False, latency_ms=20.0, error="boom", caller="ag_ui")
    finally:
        reset_envelope(token)
```

### Step 3: Query Timeline history from the in-memory graph

```python
timeline_query = (
    "MATCH (t:ToolInvocation) "
    "RETURN t.tool_name AS tool_name, t.brick_name AS brick, "
    "t.success AS success, t.latency_ms AS latency_ms, "
    "t.created_at AS created_at, t.error AS error, "
    "t.workflow_run_id AS workflow_run_id, t.args_summary AS args_summary, "
    "t.caller AS caller, t.result_summary AS result_summary "
    "ORDER BY t.created_at DESC LIMIT 100"
)

timeline = graph_sink._graph_runtime["graph_query"].fn(query_str=timeline_query)
session_a = graph_sink._graph_runtime["graph_get_neighbors"].fn(
    entity_id="session-session-a",
    relationship_type="CONTAINS_INVOCATION",
    direction="out",
)
session_b = graph_sink._graph_runtime["graph_get_neighbors"].fn(
    entity_id="session-session-b",
    relationship_type="CONTAINS_INVOCATION",
    direction="out",
)
```

### Step 4: Verify two runs stay distinct in local history

```python
assert [row["workflow_run_id"] for row in timeline["raw"]] == [
    "run-b",
    "run-a",
    "run-a",
]
assert timeline["raw"][0]["success"] is False
assert timeline["raw"][0]["error"] == "boom"
assert all(row["caller"] == "ag_ui" for row in timeline["raw"])
assert session_a["count"] == 2
assert session_b["count"] == 1
```

### Step 5: Optional frontend-side grouping check

Feed `timeline["raw"]` into the dashboard Timeline helpers and confirm grouping stays coherent:

```python
# See frontends/next-dashboard/lib/timeline-history.ts
# and frontends/next-dashboard/lib/timeline-sessions.ts
```

## Success Criteria

- [x] The recipe runs on the lightweight local stack with `networkx`
- [x] AG-UI ingress accepts explicit `threadId` and `runId`
- [x] Tool telemetry materializes during the same request-scoped run
- [x] Two persisted runs remain distinct by `workflow_run_id`
- [x] The sink creates or reuses the expected `Session` nodes
- [x] The sink links invocations to sessions via `CONTAINS_INVOCATION`
- [x] Queried history rows are in the shape the Timeline consumes

## Notes

- This recipe is intentionally lightweight-first and avoids any containerized graph dependency.
- The executable regressions for this recipe live in `bases/api/test/factory/api/test_ag_ui_endpoint.py`, `bases/mcp_server/test/factory/mcp_server/test_graph_sink.py`, `frontends/next-dashboard/lib/timeline-history.test.ts`, and `frontends/next-dashboard/lib/timeline-sessions.test.ts`.
