"""Prompt templates for events MCP prompts."""

PROMPT_TEMPLATES = {
    "create_subscription": {
        "description": "Guide for creating a new event subscription",
        "template": """# Create Subscription: {name}

## Purpose
{purpose}

## Subscription Definition

Create `config/subscriptions/{id}.yaml`:

```yaml
id: {id}
event_type: {event_type}
handler: {handler}
description: {purpose}
enabled: true
priority: 0
```

## Event Type Patterns

- Exact: `user.created`
- Wildcard: `user.*` (matches user.created, user.updated)

## Validation

```
events_authoring_validate_subscriptions(dry_run=True)
```

## Test

```
events_publish(event_type="{event_type}", payload={{}}, source="test")
```
""",
    },
    "debug_events": {
        "description": "Help debugging event flow issues",
        "template": """# Debug Event Flow

## Issue
{issue}

## Steps

### 1. Check Recent Events
```
events_list_events(event_type="{event_type}", limit=10)
```

### 2. Check Subscriptions
```
events_get_subscription_registry()
```

### 3. Check History
```
events_list_history(event_type="{event_type}", limit=10)
```

### 4. Replay for Testing
```
events_replay(event_id="<event_id>")
```

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| No matches | Pattern mismatch | Check event_type |
| Not found | Not published | Verify publish |
| Not invoked | Disabled | Check enabled flag |
""",
    },
    "configure_storage": {
        "description": "Guide for configuring event storage backend",
        "template": """# Configure {backend} Storage

## Current: {current_config}

## Setup
{setup_guide}

## Settings (`config/settings.yaml`)

```yaml
storage:
  backend: {backend}
{backend_config}
```

## Verify

```
events_health_check()
events_publish(event_type="test", payload={{}}, source="test")
```
""",
    },
}

STORAGE_GUIDES = {
    "memory": {
        "setup_guide": "No setup required. In-memory, no persistence.",
        "backend_config": "  # Memory is default",
    },
    "sqlite": {
        "setup_guide": "SQLite provides file-based persistence.",
        "backend_config": "  sqlite:\n    filename: events.db",
    },
    "redis": {
        "setup_guide": "Redis for distributed pub/sub.\n```bash\ndocker run -d -p 6379:6379 redis:alpine\n```",
        "backend_config": "  redis:\n    url: redis://localhost:6379/0",
    },
}
