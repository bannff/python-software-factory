"""Prompt templates for cache MCP prompts."""

PROMPT_TEMPLATES = {
    "configure_cache": {
        "description": "Guide for setting up cache backend",
        "template": """# Configure Cache Backend: {backend}

## Current Configuration
{current_config}

## Setup Guide
{setup_guide}

## Configuration Options

```python
from factory.cache.runtime.runtime import CacheRuntime

runtime = CacheRuntime()
cache = runtime.get_cache("{backend}"{config_params})
```

## Verification Steps

1. Check health:
```
health_check()
```

2. Test operations:
```
cache_set(key="test:key", value="test_value", ttl_seconds=60)
cache_get(key="test:key")
cache_delete(key="test:key")
```

3. Check statistics:
```
cache_stats()
```
""",
    },
    "debug_cache": {
        "description": "Help debugging cache issues",
        "template": """# Debug Cache Issues

## Issue
{issue}

## Diagnostic Steps

### 1. Check Cache Health
```
health_check()
```

### 2. Check Statistics
```
cache_stats()
```

Look for:
- High miss rate (> 50%) indicates cache not being utilized
- Size at max_size indicates eviction pressure

### 3. List Keys
```
cache_keys(pattern="{pattern}")
```

### 4. Check Specific Key
```
cache_get(key="{key}")
```

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Always miss | TTL too short | Increase TTL |
| Key not found | Never set | Verify set call |
| Stale data | TTL too long | Decrease TTL |
| High eviction | max_size too small | Increase max_size |
| Connection error | Redis down | Check Redis status |

## Redis-Specific Debugging

```bash
# Check Redis connection
redis-cli ping

# Monitor commands
redis-cli monitor
```
""",
    },
    "optimize_cache": {
        "description": "Guide for cache optimization",
        "template": """# Optimize Cache Performance

## Current Statistics
{current_stats}

## Analysis

### Hit Rate: {hit_rate}
{hit_rate_analysis}

### Cache Size: {size}/{max_size}
{size_analysis}

## Optimization Recommendations

### 1. Key Design
- Use hierarchical keys: `entity:id:field`
- Keep keys short but descriptive
- Use consistent prefixes for grouping

### 2. TTL Tuning
| Data Type | Current | Recommended |
|-----------|---------|-------------|
{ttl_recommendations}

### 3. Size Optimization
{size_recommendations}

### 4. Backend Selection
{backend_recommendations}

## Implementation Checklist

- [ ] Review key naming conventions
- [ ] Audit TTL values
- [ ] Monitor hit rate after changes
- [ ] Consider cache warming for critical data
""",
    },
}

BACKEND_GUIDES = {
    "memory": {
        "setup_guide": "No external setup required. In-memory cache is the default.",
        "config_params": ", max_size=1000",
    },
    "redis": {
        "setup_guide": """Redis provides distributed caching.

```bash
# Start Redis with Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
brew install redis  # macOS
apt install redis   # Ubuntu
```""",
        "config_params": ', url="redis://localhost:6379/0", prefix="app:"',
    },
}
