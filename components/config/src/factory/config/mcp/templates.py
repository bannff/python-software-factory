"""Prompt templates for config MCP prompts."""

PROMPT_TEMPLATES = {
    "configure_source": {
        "description": "Guide for setting up a configuration source",
        "template": """# Configure {backend} Source

## Current Environment: {environment}

## Setup Guide

{setup_guide}

## Configuration

{backend_config}

## Verification

```
config_get(key="test.key", default="not_found")
health_check()
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Key not found | Wrong prefix | Check prefix configuration |
| Permission denied | Missing access | Verify IAM/file permissions |
| Connection failed | Network issue | Check connectivity |
""",
    },
    "add_feature_flag": {
        "description": "Guide for adding a new feature flag",
        "template": """# Add Feature Flag: {flag_name}

## Purpose
{purpose}

## Configuration

```yaml
feature_flags:
  {flag_name}:
    enabled: {default_enabled}
    description: "{purpose}"
    rollout_percentage: {rollout_percentage}
```

## Usage in Code

```python
from factory.config import get_runtime

runtime = get_runtime()
flags = runtime.get_feature_flags()

if flags.is_enabled("{flag_name}"):
    # New behavior
    pass
```

## Rollout Strategy

- Start with 0% rollout
- Increase to 10%, monitor metrics
- Gradually increase to 100%
- Remove flag after full rollout
""",
    },
    "debug_config": {
        "description": "Guide for debugging configuration issues",
        "template": """# Debug Configuration Issue

## Issue
{issue}

## Diagnostic Steps

### 1. Check Current Environment
```
config_environment()
```

### 2. List Available Keys
```
config_keys(prefix="{prefix}")
```

### 3. Get Specific Value
```
config_get(key="{key}", default="NOT_FOUND")
```

### 4. Check Health
```
health_check()
```

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Value is None | Key doesn't exist | Check key spelling |
| Wrong value | Override in env | Check env vars |
| Type error | String vs int | Use get_typed() |
""",
    },
    "migrate_config": {
        "description": "Guide for migrating between configuration sources",
        "template": """# Migrate Configuration: {source_backend} -> {target_backend}

## Migration Plan

### Phase 1: Preparation
1. Export current configuration: `config_get_all(prefix="")`
2. Document all keys and values
3. Set up target backend:
{target_setup}

### Phase 2: Migration
1. Copy values to target backend
2. Verify values match

### Phase 3: Switchover
1. Update application to use new backend
2. Test all configuration access
3. Monitor for errors

### Phase 4: Cleanup
1. Remove old configuration source
2. Update documentation
""",
    },
}
