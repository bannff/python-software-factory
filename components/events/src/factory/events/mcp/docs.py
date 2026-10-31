"""Documentation content for events MCP resources."""

EVENTS_DOCS = {
    "overview": {
        "title": "Events Brick Overview",
        "content": """# Events Brick

Event streaming and message bus integration for the Python Factory.

## Core Concepts

- **Event**: Atomic unit with type, payload, source, and timestamp
- **Subscription**: Pattern-based handler registration
- **History**: Audit trail of all published events
- **Replay**: Re-publish historical events

## Quick Start

1. Publish an event:
```
events_publish(
    event_type="user.created",
    payload={"user_id": "123", "email": "user@example.com"},
    source="auth-service"
)
```

2. Query events:
```
events_list_events(event_type="user.*", limit=10)
```

3. Create a subscription:
```
events_authoring_upsert_subscription(
    subscription_id="notify-on-user-created",
    subscription_data={
        "event_type": "user.created",
        "handler": "notification.send_welcome_email"
    }
)
```

## Storage Backends

- `memory` - In-memory (default, for dev/testing)
- `sqlite` - SQLite file-based persistence
- `redis` - Redis pub/sub for distributed systems

## MCP Tools

- `events_publish` - Publish an event
- `events_get_event` - Get event by ID
- `events_list_events` - Query events
- `events_list_history` - Query audit history
- `events_replay` - Replay historical event
""",
    },
    "event-types": {
        "title": "Event Type Conventions",
        "content": """# Event Type Conventions

Event types follow a hierarchical dot-notation pattern.

## Format

```
<domain>.<action>[.<detail>]
```

## Examples

### User Events
- `user.created` - New user registered
- `user.updated` - User profile changed
- `user.deleted` - User account removed
- `user.login.success` - Successful login
- `user.login.failed` - Failed login attempt

### Workflow Events
- `workflow.run.started` - Workflow run began
- `workflow.run.completed` - Workflow run finished
- `workflow.step.executed` - Step completed
- `workflow.step.failed` - Step failed

### System Events
- `system.health.degraded` - Service health issue
- `system.config.changed` - Configuration updated

## Subscription Patterns

Subscriptions support wildcards:
- `user.*` - All user events
- `workflow.run.*` - All workflow run events
- `*.failed` - All failure events
""",
    },
    "subscriptions": {
        "title": "Subscription Configuration",
        "content": """# Subscription Configuration

Subscriptions define how events are routed to handlers.

## Definition Schema

```yaml
id: notify-on-user-created
event_type: user.created
handler: notification.send_welcome_email
description: Send welcome email when user registers
enabled: true
priority: 10
filters:
  source: auth-service
```

## Fields

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique identifier |
| event_type | Yes | Pattern to match (supports wildcards) |
| handler | Yes | Handler identifier to invoke |
| description | No | Human-readable description |
| enabled | No | Active flag (default: true) |
| priority | No | Ordering (higher = first, default: 0) |
| filters | No | Additional matching criteria |

## File Location

Place subscription YAML files in:
```
config/subscriptions/<subscription-id>.yaml
```

## Wildcard Patterns

- `user.*` matches `user.created`, `user.updated`
- `*.failed` matches `login.failed`, `payment.failed`
- `workflow.run.*` matches `workflow.run.started`
""",
    },
    "storage": {
        "title": "Storage Backend Configuration",
        "content": """# Storage Backend Configuration

The events brick supports pluggable storage backends.

## Available Backends

### memory (default)
In-memory storage, no persistence.
```yaml
storage:
  backend: memory
```

### sqlite
SQLite file-based persistence.
```yaml
storage:
  backend: sqlite
  sqlite:
    filename: events.db
```

### redis
Redis for distributed pub/sub.
```yaml
storage:
  backend: redis
  redis:
    url: redis://localhost:6379/0
    key_prefix: events:
```

## Choosing a Backend

| Backend | Use Case | Persistence | Distributed |
|---------|----------|-------------|-------------|
| memory | Dev/testing | No | No |
| sqlite | Single instance | Yes | No |
| redis | Production | Optional | Yes |

## Custom Backends

Implement the `EventStore` protocol:
- `store(event)` - Store an event
- `get(event_id)` - Retrieve by ID
- `list_events(...)` - Query events
""",
    },
}
