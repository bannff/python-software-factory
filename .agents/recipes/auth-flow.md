# Recipe: Auth Flow

Validates the authentication and authorization pipeline.

## Bricks Used
- `auth` - Token verification and user info
- `permissions` - Policy-based access control
- `cache` - Result caching
- `mcp_utils` - Envelope context propagation

## Scenario

A user presents a JWT token. The system must:
1. Verify the token is valid
2. Extract user info and roles
3. Check if user has permission for a specific action
4. Cache the permission result for subsequent requests
## Prerequisites

- Bricks instantiated with memory adapters (no external deps)
- A mock JWT token for testing

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path
import yaml

# Cache
from factory.cache.runtime.runtime import get_runtime as get_cache_runtime
cache = get_cache_runtime().get_cache()

# Auth - use MemoryBackend directly (simpler than full AuthRuntime)
from factory.auth.runtime.adapters import MemoryBackend
auth_backend = MemoryBackend()

# Permissions - needs config dir with settings and policies
tmpdir = Path(tempfile.mkdtemp())
(tmpdir / "policies").mkdir(parents=True, exist_ok=True)
(tmpdir / "settings.yaml").write_text(yaml.safe_dump({
    "schema_version": 1,
    "service_name": "recipe-test",
    "backend": "filesystem",
    "authoring": {"enabled": False},
    "policy_store": {"policies_subdir": "policies"},
}))
# Add a policy
(tmpdir / "policies" / "default.yaml").write_text(yaml.safe_dump({
    "schema_version": 1,
    "id": "default-policy",
    "name": "Default Policy",
    "version": "0.1",
    "rules": [
        {
            "id": "allow_read_documents",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["document"],
        },
    ],
}))

from factory.permissions.runtime.runtime import PermissionsRuntime
permissions = PermissionsRuntime.from_config_dir(tmpdir)
```

### Step 2: Health Check All Bricks

```python
# Cache health
from factory.cache.runtime.runtime import get_runtime
get_runtime().health_check()
# Expected: no exception

# Auth health
health = auth_backend.health_check()
# Returns: {"ok": True, "backend": "memory", ...}

# Permissions capabilities
caps = permissions.get_capabilities()
# Returns: {"tools": {"operational": [...], ...}}
```

### Step 3: Create User and Token

```python
# Add a user
auth_backend.add_user(
    "user-123", 
    "testuser", 
    email="test@example.com",
    scopes=["read", "write"],
    roles=["viewer"]
)

# Create token
token, token_info = auth_backend.create_token("user-123")
```

### Step 4: Verify Token

```python
from factory.auth.runtime.envelope import parse_envelope
env = parse_envelope(None)
result = auth_backend.verify_access_token(
    token, 
    required_audience=None, 
    required_scopes=None, 
    envelope=env
)
# Returns: {"ok": True, "principal": {"subject": "user-123", ...}, ...}
```

### Step 5: Introspect Token

```python
result = auth_backend.introspect_token(token, envelope=env)
# Returns: {"active": True, "sub": "user-123", ...}
```

### Step 6: Check Permission (allowed)

```python
from factory.permissions.runtime.envelope import Envelope
result = permissions.evaluate(
    action="read",
    resource={"type": "document", "id": "doc-1"},
    context={},
    envelope=Envelope(),
)
# Returns: {"decision": "allow", ...}
```

### Step 7: Check Permission (denied)

```python
result = permissions.evaluate(
    action="delete",
    resource={"type": "document", "id": "doc-1"},
    context={},
    envelope=Envelope(),
)
# Returns: {"decision": "deny", ...}
```

### Step 8: Cache Permission Result

```python
cache.set("perm:user-123:read:document", "allow", 300)  # ttl in seconds
value = cache.get("perm:user-123:read:document")
# Returns: "allow"
```

### Step 9: Invalid Token Test

```python
result = auth_backend.verify_access_token(
    "invalid-token-xyz", 
    required_audience=None, 
    required_scopes=None, 
    envelope=env
)
# Returns: {"ok": False, "error": "invalid_token"}
```

### Step 10: Envelope Context Propagation

```python
from factory.mcp_utils.interface import set_envelope, get_principal_id

set_envelope({"principal_id": "user-123", "tenant_id": "t-456"})
assert get_principal_id() == "user-123"  # bricks read this as fallback

set_envelope({})  # bases clear in finally block
assert get_principal_id() is None
```

## Success Criteria

- [x] All health checks pass
- [x] User created and token generated
- [x] Token verification returns valid user info
- [x] Token introspection works
- [x] Permission check returns allow for read
- [x] Permission check returns deny for delete
- [x] Cache stores and retrieves the result
- [x] Invalid token returns error
- [x] Envelope context propagates principal_id to downstream bricks

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| auth | `factory.auth.runtime.adapters.MemoryBackend` | `add_user()`, `create_token()`, `verify_access_token()`, `introspect_token()` |
| permissions | `factory.permissions.runtime.runtime.PermissionsRuntime` | `from_config_dir()`, `evaluate()`, `get_capabilities()` |
| cache | `factory.cache.runtime.runtime.get_runtime` | `get_cache()` → `set()`, `get()` |
| mcp_utils | `factory.mcp_utils.interface` | `set_envelope()`, `get_envelope()`, `get_principal_id()` |
