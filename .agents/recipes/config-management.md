# Recipe: Config Management

Validates centralized configuration, feature flags, and layered config resolution.

## Bricks Used
- `config` - Centralized configuration with pluggable backends
- `cache` - Caching resolved config values
- `logger` - Logging config changes

## Scenario

Set up layered configuration (env → file → overrides), resolve values with precedence, cache hot config paths, and log config changes.

## Prerequisites

- No AWS required
- All bricks use memory/local adapters

## Steps

### Step 1: Initialize Bricks

```python
import os
import tempfile
from pathlib import Path

# Config
from factory.config.runtime.runtime import ConfigRuntime
config_runtime = ConfigRuntime(environment="development")

# Cache
from factory.cache.runtime.runtime import get_runtime as get_cache_runtime
cache = get_cache_runtime().get_cache()

# Logger
tmpdir_log = Path(tempfile.mkdtemp())
from factory.logger.runtime.runtime import LoggerRuntime
logger = LoggerRuntime(log_dir=str(tmpdir_log))
```

### Step 2: Health Checks

```python
# Config - empty until backends are created
health = config_runtime.health_check()
# Returns: {} (no active configs yet)

backends = config_runtime.available_backends()
# Returns: ["env", "file", "ssm", "pydantic"]
```

### Step 3: Set Up Env Config Layer

```python
os.environ["APP_NAME"] = "python-factory"
os.environ["APP_DEBUG"] = "true"
os.environ["APP_PORT"] = "8080"

env_config = config_runtime.get_config("env", prefix="APP_")
value = env_config.get("APP_NAME")
# Returns: "python-factory"
```

### Step 4: Set Up File Config Layer

```python
import yaml
tmpdir_cfg = Path(tempfile.mkdtemp())
(tmpdir_cfg / "config.yaml").write_text(yaml.safe_dump({
    "app_name": "factory-override",
    "database_url": "sqlite:///local.db",
    "max_workers": 4,
}))

file_config = config_runtime.get_config("file", config_path=str(tmpdir_cfg / "config.yaml"))
value = file_config.get("app_name")
# Returns: "factory-override"
```

### Step 5: Layered Resolution

```python
config_runtime.add_layer(env_config)
config_runtime.add_layer(file_config)  # File overrides env

# File layer wins for app_name
resolved = config_runtime.get_layered("app_name")
# Returns: "factory-override" (file layer overrides env)

# Env layer provides values not in file
resolved = config_runtime.get_layered("APP_DEBUG")
# Returns: "true" (from env layer)
```

### Step 6: Infrastructure Config via InfraEnv + `get_infra()`

The `get_infra()` convenience function is the standard way bricks resolve infrastructure settings. It calls `get_layered()` which auto-bootstraps two layers on first access:

1. **SSM** (lowest priority) — reads `/art/support/*` parameters (best-effort, skipped if unavailable)
2. **InfraEnv** (highest priority) — maps dot-notation keys to unprefixed env vars (`neo4j.uri` → `NEO4J_URI`)

```python
from factory.config.interface import get_infra

# Dot-notation key → env var lookup (NEO4J_URI), then SSM, then default
uri = get_infra("neo4j.uri", "bolt://localhost:7687")
# Returns: value of NEO4J_URI if set, else SSM /art/support/neo4j.uri, else default

backend = get_infra("memory.backend", "memory")
# Returns: value of MEMORY_BACKEND if set, else SSM, else "memory"

# InfraEnv convention: dots become underscores, uppercased
# storage.doc.backend → STORAGE_DOC_BACKEND
doc_backend = get_infra("storage.doc.backend", "memory")
```

> **Note**: `get_infra()` replaces direct `os.environ.get()` calls for infrastructure wiring. The InfraEnvConfigStore is separate from `EnvConfigStore` (which uses a `FACTORY_` prefix for application-level config).

### Step 7: Neo4j Connection Config

For Neo4j specifically, `get_neo4j_config()` resolves all four connection parameters via layered config:

```python
from factory.config.interface import get_neo4j_config

neo4j = get_neo4j_config()
# Returns: {"uri": ..., "user": ..., "password": ..., "database": ...}
# Defaults: bolt://localhost:7687, neo4j, password, neo4j

# Each key resolves via get_infra():
#   neo4j.uri      → NEO4J_URI      → SSM → "bolt://localhost:7687"
#   neo4j.user     → NEO4J_USER     → SSM → "neo4j"
#   neo4j.password → NEO4J_PASSWORD → SSM → "password"
#   neo4j.database → NEO4J_DATABASE → SSM → "neo4j"
```

### Step 8: Cache Hot Config Values

```python
cache.set("config:app_name", resolved, 600)
cached = cache.get("config:app_name")
# Returns: "factory-override"
```

### Step 9: Log Config Change

```python
logger.info(
    "Config resolved",
    source="config-management",
    context={"environment": config_runtime.environment, "sources": config_runtime.sources},
)
```

### Step 10: Verify Config Sources

```python
sources = config_runtime.sources
# Returns: list of active config source keys

env = config_runtime.environment
# Returns: "development"
```

### Step 11: Probe AWS Identity

```python
identity = config_runtime.get_aws_identity()
if identity.available:
    print(f"Account: {identity.account_id}, Region: {identity.region}")
    print(f"ARN: {identity.identity_arn}")
else:
    print(f"No AWS credentials: {identity.error}")
# Cached for 5 minutes; use force=True to bypass
identity_fresh = config_runtime.get_aws_identity(force=True)
```

## Success Criteria

- [x] Env config reads environment variables
- [x] File config reads YAML files
- [x] Layered resolution respects precedence (later layers win)
- [x] InfraEnv adapter maps dot-notation keys to unprefixed env vars
- [x] `get_infra()` auto-bootstraps SSM + InfraEnv layers on first call
- [x] `get_neo4j_config()` resolves full Neo4j connection dict via layered config
- [x] Config values cached for hot paths
- [x] Config changes logged
- [x] AWS identity probed and available

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| config | `factory.config.interface` | `get_infra()`, `get_neo4j_config()` |
| config | `factory.config.runtime.runtime.ConfigRuntime` | `get_config()`, `add_layer()`, `get_layered()`, `get_aws_identity()` |
| config | `factory.config.runtime.ports.ConfigStore` | `get()`, `set()`, `exists()`, `keys()`, `get_all()` |
| config | `factory.config.runtime.adapters.infra_env.InfraEnvConfigStore` | `get()`, `set()`, `exists()`, `keys()`, `get_all()`, `get_typed()` |
| config | `factory.config.runtime.adapters.aws_identity.AWSIdentity` | `to_dict()`, `.available`, `.account_id`, `.region` |

## Cleanup

```python
del os.environ["APP_NAME"]
del os.environ["APP_DEBUG"]
del os.environ["APP_PORT"]
```
