# Recipe: HTTP & Integrations

Validates the HTTP client, external service connectors, and webhook pipeline.

## Bricks Used
- `http` - HTTP client with retry and rate limiting
- `integrations` - External service connectors
- `cache` - Caching API responses
- `logger` - Logging HTTP activity

## Scenario

Configure HTTP clients with retry policies, register external service connectors, make API calls, cache responses, and log all activity.

## Prerequisites

- No AWS required
- Uses memory/mock adapters
- Note: HTTP calls to external URLs will fail without network; test the wiring, not the network

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path

# HTTP
from factory.http.runtime.runtime import HTTPRuntime
from factory.http.runtime.ports import RetryConfig, RateLimitConfig, AuthConfig
http = HTTPRuntime()

# Integrations
from factory.integrations.runtime.runtime import IntegrationsRuntime
integrations = IntegrationsRuntime()

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
http_backends = http.available_backends()
# Returns: ["httpx", "aiohttp", "tenacity_httpx"]

integrations_health = integrations.health_check()
# Returns: ConnectorHealth(healthy=True, connector_count=0, ...)
```

### Step 3: Configure HTTP Client with Retry

```python
client = http.get_client(
    backend="httpx",
    retry=RetryConfig(max_retries=3, backoff_factor=0.5, retry_statuses=(429, 500, 502, 503)),
    rate_limit=RateLimitConfig(requests_per_second=10.0, burst_size=20),
    auth=AuthConfig(auth_type="bearer", token="test-token-123"),
)
```

### Step 4: Register REST Connector

```python
connector = integrations.register(
    connector_id="github-api",
    name="GitHub API",
    base_url="https://api.github.com",
    connector_type="rest",
    headers={"Accept": "application/vnd.github.v3+json"},
    timeout_seconds=30,
    retry_count=3,
)
# Returns: Connector model
```

### Step 5: Register AWS Connector

```python
aws_connector = integrations.register(
    connector_id="s3-data",
    name="S3 Data Lake",
    base_url="aws://s3",
    connector_type="aws",
    metadata={"region": "us-east-1"},
)
```

### Step 6: List Connectors

```python
connectors = integrations.list_connectors()
# Returns: list of Connector models (github-api, s3-data)

connector = integrations.get("github-api")
# Returns: Connector model for github-api
```

### Step 7: Cache API Response Pattern

```python
# Simulate caching an API response
cache.set("api:github:rate-limit", '{"remaining": 4999}', 60)
cached = cache.get("api:github:rate-limit")
# Returns: '{"remaining": 4999}'
```

### Step 8: Log API Activity

```python
logger.info(
    "Connector registered",
    source="integrations",
    context={"connector_id": "github-api", "type": "rest"},
)
```

### Step 9: Unregister Connector

```python
result = integrations.unregister("s3-data")
# Returns: True

connectors = integrations.list_connectors()
# Returns: list with only github-api
```

### Step 10: Verify Health After Changes

```python
health = integrations.health_check()
# Returns: ConnectorHealth with updated counts
```

## Success Criteria

- [x] HTTP client created with retry, rate limit, and auth config
- [x] REST connector registered and retrievable
- [x] AWS connector registered
- [x] Connector listing works
- [x] API responses cacheable
- [x] Activity logged
- [x] Connector unregistration works

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| http | `factory.http.runtime.runtime.HTTPRuntime` | `get_client()`, `health_check()` |
| http | `factory.http.runtime.ports` | `RetryConfig`, `RateLimitConfig`, `AuthConfig`, `HTTPClient` |
| integrations | `factory.integrations.runtime.runtime.IntegrationsRuntime` | `register()`, `call()`, `list_connectors()` |
