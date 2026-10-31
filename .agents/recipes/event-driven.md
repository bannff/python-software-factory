# Recipe: Event-Driven

Validates the event streaming, workflow triggering, and notification pipeline.

## Bricks Used
- `events` - Event streaming and pub/sub
- `workflow` - Long-running process management
- `notification` - Alert delivery

## Scenario

An event fires, triggers a workflow, and sends a notification on completion.

## Events MCP Boundary

The Events brick exposes **20 strict FastMCP tools**: 9 deterministic, 7 operational, and 4 authoring. All retain their flat public arguments, validate them with same-brick Pydantic v2 DTOs (`strict=True`, `extra="forbid"`), and return `ToolResult[OutputDTO]`. Invoke them through the control-plane runtime; read successful payloads from `result.data` only after checking `result.ok`.

A missing event (`events_get_event`) or absent replay target (`events_replay`) is a normal successful typed result: inspect `result.data.found` or `result.data.ok` and its `error`. Do not treat those domain outcomes as transport failures. The complete tool sets are deterministic: `events_get_capabilities`, `events_health_check`, `events_describe_config_schema`, `events_get_subscription_registry`, `events_query_events`, `events_get_dashboard_summary`, `events_get_event_history_entry`, `events_get_event_graph_context`, `events_get_views`; operational: `events_publish`, `events_get_event`, `events_list_events`, `events_replay`, `events_list_history`, `events_query_history`, `events_prune_history`; authoring: `events_authoring_get_status`, `events_authoring_validate_subscriptions`, `events_authoring_upsert_subscription`, `events_authoring_delete_subscription`.

## Prerequisites

- No AWS required
- Bricks instantiated with memory adapters

## Steps

### Step 1: Initialize Bricks

```python
import asyncio
import tempfile
from pathlib import Path
import yaml

# Events
tmpdir_events = Path(tempfile.mkdtemp())
(tmpdir_events / "subscriptions").mkdir(parents=True, exist_ok=True)

from factory.events.runtime.runtime import EventsRuntime
events = EventsRuntime(config_dir=tmpdir_events)

# Workflow
tmpdir_wf = Path(tempfile.mkdtemp())
(tmpdir_wf / "workflows").mkdir(parents=True, exist_ok=True)
(tmpdir_wf / "settings.yaml").write_text(yaml.safe_dump({
    "schema_version": "v1",
    "default_timeout": 300,
    "storage": {"sqlite": {"filename": "workflow.db"}},
    "executor": {"backend": "local"},
}))
# Add a workflow (note: version must be int, not string)
(tmpdir_wf / "workflows" / "process-order.yaml").write_text(yaml.safe_dump({
    "schema_version": "v1",
    "id": "process-order",
    "name": "Process Order",
    "version": 1,  # int, not "1.0.0"
    "tags": ["order"],
    "steps": [
        {"id": "validate", "kind": "noop"},
        {"id": "process", "kind": "noop"},
        {"id": "complete", "kind": "noop"},
    ],
}))

from factory.workflow.runtime.runtime import WorkflowRuntime
workflow = WorkflowRuntime.from_config_dir(tmpdir_wf)

# Notification (async initialization)
tmpdir_notif = Path(tempfile.mkdtemp())
(tmpdir_notif / "channels").mkdir(parents=True, exist_ok=True)
(tmpdir_notif / "templates").mkdir(parents=True, exist_ok=True)
(tmpdir_notif / "settings.yaml").write_text(yaml.safe_dump({
    "service": {"name": "notification-test"},
}))

from factory.notification.runtime.dispatcher import NotificationRuntime
notification = NotificationRuntime(config_dir=tmpdir_notif)
await notification.initialize()  # async!
```

### Step 2: Health Checks

```python
# Events - verify registry
registry = events.get_subscription_registry()
# Returns: SubscriptionRegistry object

# Workflow health
health = workflow.health_check()
# Returns: {"status": "ok", "storage": {...}, "executor": {...}}

# Notification health (async)
health = await notification.health_check()
# Returns: {"ok": True, "backend": "stdio", ...}
```

### Step 3: Register Subscription

```python
from factory.events.runtime.subscriptions import SubscriptionDefinition

# Note: uses 'handler' string, not handler_type/handler_config
sub = SubscriptionDefinition(
    id="order-workflow-trigger",
    event_type="order.created",
    handler="workflow:process-order",  # handler is a string identifier
    description="Trigger process-order workflow on order.created",
)
events.get_subscription_registry().register(sub)
```

### Step 4: Publish Event

```python
event_result = events.publish(
    event_type="order.created",
    payload={"order_id": "ORD-001", "amount": 99.99},
    source="recipe-test",
)
# Returns: EventResult(event_id="...", status="published", subscriptions_matched=1)
```

### Step 5: Verify Event Stored

```python
stored_event = events.get_event(event_result.event_id)
# Returns: Event(id="...", type="order.created", payload={...})
```

### Step 6: Start Workflow

```python
from factory.workflow.runtime.envelope import Envelope
result = workflow.start_run(
    workflow_name_or_id="process-order",
    input={"order_id": "ORD-001", "amount": 99.99},
    envelope=Envelope(),
)
run_id = result.get("run_id")
# Returns: {"run_id": "...", "status": "succeeded"}
```

### Step 7: Check Workflow Status

```python
result = workflow.get_run(run_id=run_id, envelope=Envelope())
# Returns: {"status": "succeeded", "current_step_index": None, ...}
```

### Step 8: Send Notification (async)

```python
result = await notification.send_notification(
    recipient="user@example.com",
    subject="Order Processed",
    content="Your order ORD-001 has been processed successfully.",
    priority="normal",
)
# Returns: {"message_id": "...", "status": "sent"}
```

### Step 9: List Event History

```python
history = events.list_event_history(limit=10)
# Returns: list of EventHistoryEntry objects
```

## Success Criteria

- [x] Event subscription created
- [x] Event published and delivered
- [x] Workflow started and completed
- [x] Notification sent (via mock channel)
- [x] Event history recorded

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| events | `factory.events.runtime.runtime.EventsRuntime` | `publish()`, `get_event()`, `list_event_history()` |
| events | `factory.events.runtime.subscriptions.SubscriptionDefinition` | Model with `id`, `event_type`, `handler` |
| workflow | `factory.workflow.runtime.runtime.WorkflowRuntime` | `from_config_dir()`, `start_run()`, `get_run()` |
| notification | `factory.notification.runtime.dispatcher.NotificationRuntime` | `initialize()`, `send_notification()` (async) |

## Notes

- Notification runtime requires async initialization and operations
- WorkflowDefinition `version` must be an integer, not a string
- SubscriptionDefinition uses `handler` string, not `handler_type`/`handler_config`
