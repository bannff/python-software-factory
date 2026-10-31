"""Prompt templates for workflow MCP prompts."""

PROMPT_TEMPLATES = {
    "create_workflow": {
        "description": "Guide for creating a new workflow definition",
        "template": """# Create Workflow: {name}

## Purpose
{purpose}

## Workflow Definition

Create a file at `config/workflows/{id}.yaml`:

```yaml
schema_version: v1
id: {id}
name: {name}
version: 1
tags: [{tags}]
steps:
{steps_yaml}
```

## Step Kinds Reference

- `noop`: Immediate completion, use for branching/placeholders
- `wait_for_event`: Pause until event emitted (requires `event_type`)
- `task`: Execute via executor backend (requires `task_type`)

## Validation

After creating, validate with:
```
workflow.authoring.validate_workflows(dry_run=True)
```

## Start a Run

```
workflow.start_run(workflow_name_or_id="{id}", input={{}})
```
""",
    },
    "debug_run": {
        "description": "Help debugging a stuck or failed workflow run",
        "template": """# Debug Workflow Run: {run_id}

## Current Status
{status_info}

## Debugging Steps

### 1. Check Run Details
```
workflow.get_run(run_id="{run_id}")
```

### 2. For "waiting" Status
Emit the expected event:
```
workflow.emit_event(run_id="{run_id}", event_type="<type>", payload={{}})
workflow.step_run(run_id="{run_id}")
```

### 3. For "failed" Status
Check the `error` field. Common causes:
- Missing workflow definition
- Invalid step configuration
- Executor backend unavailable

### 4. Check Executor
```
workflow.executor.get_status()
workflow.executor.list_tasks(status="failed", limit=10)
```

### 5. Resume or Cancel
```
workflow.resume_run(run_id="{run_id}")
workflow.cancel_run(run_id="{run_id}", reason="Manual cancellation")
```
""",
    },
    "configure_executor": {
        "description": "Guide for configuring Celery or Dagster executor",
        "template": """# Configure {backend} Executor

## Current Configuration
{current_config}

## Setup Guide
{setup_guide}

## Settings File

Update `config/settings.yaml`:

```yaml
executor:
  backend: {backend}
{backend_config}
```

## Verification

1. Check health: `workflow.executor.get_status()`
2. Test run: `workflow.start_run(workflow_name_or_id="test", input={{}})`
3. Monitor: `workflow.executor.list_tasks(limit=5)`
""",
    },
}

EXECUTOR_GUIDES = {
    "celery": {
        "setup_guide": """### Prerequisites
- Redis or RabbitMQ running
- Celery workers started

```bash
docker run -d -p 6379:6379 redis:alpine
celery -A factory.workflow worker -l info
```""",
        "backend_config": """  celery:
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1""",
    },
    "dagster": {
        "setup_guide": """### Prerequisites
- Dagster instance running

```bash
dagster dev -h 0.0.0.0 -p 4266
```""",
        "backend_config": """  dagster:
    host: localhost
    port: 4266""",
    },
    "local": {
        "setup_guide": """### No Setup Required
The local executor runs tasks in-process. No external dependencies.
Best for development and testing.""",
        "backend_config": """  # Local executor is the default""",
    },
}
