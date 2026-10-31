# Recipe: API Surface

Validates the HTTP API entry point with authentication and data layer routing.

## Bricks Used
- `api` (base) - HTTP API entry point
- `auth` - Token verification
- `cache` - Ephemeral caching
- `graph` - Knowledge graph operations
- `storage` - Document storage

## Scenario

An HTTP request arrives, gets authenticated, and routes to the appropriate data layer handler.

## Prerequisites

- No AWS required
- Auth brick uses MemoryBackend
- All data bricks use memory adapters

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path

# Auth - use MemoryBackend directly
from factory.auth.runtime.adapters import MemoryBackend
auth_backend = MemoryBackend()

# Cache
from factory.cache.runtime.runtime import get_runtime as get_cache_runtime
cache = get_cache_runtime().get_cache()

# Graph
from factory.graph.runtime.runtime import GraphRuntime
graph = GraphRuntime().get_graph()

# Storage - document store
from factory.storage.runtime.adapters import LocalBlobStore
tmpdir = Path(tempfile.mkdtemp())
storage = LocalBlobStore(root_path=tmpdir)

# API core types
from factory.api.core import APIHealth, RouteInfo, AdapterType
```

### Step 2: Health Checks

```python
# Auth health
health = auth_backend.health_check()
# Returns: {"ok": True, "backend": "memory", ...}

# Cache - verify set/get works
cache.set("test-key", "test-value", 300)
value = cache.get("test-key")
# Returns: "test-value"

# Graph health
health = graph.health_check()
# Returns: GraphHealth(node_count=0, edge_count=0)
```

### Step 3: Get API Capabilities

```python
from factory.api.server import get_capabilities
caps = get_capabilities()
# Returns: {"name": "api", "features": ["rest_api", "graphql_api", ...]}
```

### Step 4: Create User and Token

```python
auth_backend.add_user(
    "api-user-1",
    "apiuser",
    email="api@example.com",
    scopes=["read", "write", "admin"],
)
token, _ = auth_backend.create_token("api-user-1")
```

### Step 5: Verify Token

```python
from factory.auth.runtime.envelope import parse_envelope
env = parse_envelope(None)
result = auth_backend.verify_access_token(
    token,
    required_audience=None,
    required_scopes=["read"],
    envelope=env,
)
# Returns: {"ok": True, "claims": {"scope": "read write admin", ...}}
```

### Step 6: Test Invalid Token

```python
result = auth_backend.verify_access_token(
    "invalid-token",
    required_audience=None,
    required_scopes=None,
    envelope=env,
)
# Returns: {"ok": False, "error": "invalid_token"}
```

### Step 7: Graph Operations

```python
from factory.graph.runtime.ports import Entity, Relationship

graph.add_entity(Entity(
    id="user:1", type="user",
    properties={"name": "Test User", "role": "admin"},
))
graph.add_entity(Entity(
    id="resource:doc-1", type="document",
    properties={"title": "API Spec"},
))
graph.add_relationship(Relationship(
    id="rel:user1-owns-doc1", type="owns",
    source_id="user:1", target_id="resource:doc-1",
    properties={"since": "2024-01-01"},
))

neighbors = graph.get_neighbors("user:1")
# Returns: list of Entity objects
```

### Step 8: Storage Operations

```python
content = b'{"endpoint": "/health", "method": "GET", "status": 200}'
meta = storage.put("api_logs/log-001.json", content, content_type="application/json")
# Returns: BlobMeta(key="api_logs/log-001.json", size=N, ...)

data, meta = storage.get("api_logs/log-001.json")
# Returns: (bytes, BlobMeta)
```

### Step 9: Cache the Auth Result

```python
cache.set("perm:api-user-1:read", "allow", 300)
value = cache.get("perm:api-user-1:read")
# Returns: "allow"
```

### Step 10: API Route Info

```python
route = RouteInfo(
    path="/api/v1/health",
    method="GET",
    handler="health_check",
    tags=["health", "monitoring"],
)
route.to_dict()
# Returns: {"path": "/api/v1/health", "method": "GET", ...}
```

## Success Criteria

- [x] Auth brick initializes with MemoryBackend
- [x] Auth health check passes
- [x] API capabilities returned
- [x] Token verification works
- [x] Invalid token returns error
- [x] Graph entity and relationship operations work
- [x] Storage blob put/get works
- [x] Cache set/get works

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| auth | `factory.auth.runtime.adapters.MemoryBackend` | `add_user()`, `create_token()`, `verify_access_token()` |
| cache | `factory.cache.runtime.runtime.get_runtime` | `get_cache()` → `set()`, `get()` |
| graph | `factory.graph.runtime.runtime.GraphRuntime` | `get_graph()` → `add_entity()`, `add_relationship()`, `get_neighbors()` |
| graph models | `factory.graph.runtime.ports` | `Entity`, `Relationship` |
| storage | `factory.storage.runtime.adapters.LocalBlobStore` | `put()`, `get()` |
| api | `factory.api.core` | `APIHealth`, `RouteInfo`, `AdapterType` |
| api | `factory.api.server` | `get_capabilities()` |
