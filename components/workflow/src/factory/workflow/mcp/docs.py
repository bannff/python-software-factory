"""Documentation content for workflow MCP resources."""

WORKFLOW_DOCS = {
    "step-kinds": {
        "title": "Workflow Step Kinds",
        "content": """# Workflow Step Kinds

Workflows are composed of steps. Each step has a `kind` that determines its behavior.

## Available Step Kinds

### noop
A no-operation step that immediately completes. Useful for:
- Placeholder steps during development
- Conditional branching points

```yaml
- id: start
  kind: noop
  next: process_data
```

### wait_for_event
Pauses the workflow until a specific event is emitted.

```yaml
- id: await_approval
  kind: wait_for_event
  event_type: approval_received
  next: finalize
```

Emit events via `workflow.emit_event(run_id, event_type, payload)`.

### task
Executes a task via the configured executor backend.

```yaml
- id: process_data
  kind: task
  task_type: data_pipeline
  task_payload:
    source: s3://bucket/input
  task_options:
    queue: high_priority
  next: complete
```
""",
    },
    "executors": {
        "title": "Task Executor Backends",
        "content": """# Task Executor Backends

The workflow brick supports pluggable task executors.

## Available Backends

### local (default)
In-process execution with no external dependencies.

```yaml
executor:
  backend: local
```

### celery
Distributed task queue via Celery + Redis/RabbitMQ.

```yaml
executor:
  backend: celery
  celery:
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1
```

### dagster
Pipeline orchestration via Dagster.

```yaml
executor:
  backend: dagster
  dagster:
    host: localhost
    port: 4266
```

## Executor Protocol

All executors implement the `TaskExecutor` protocol:
- `submit(task_id, task_type, payload, options)`
- `get_status(task_id)`
- `cancel(task_id, reason)`
- `list_tasks(status, task_type, limit)`
- `health_check()`
""",
    },
    "overview": {
        "title": "Workflow Brick Overview",
        "content": """# Workflow Brick

Manage long-running process lifecycles with pluggable task executors.

## Core Concepts

- **Workflow Definition**: YAML file defining steps and transitions
- **Run**: An instance of a workflow execution
- **Step**: A unit of work (noop, wait_for_event, task)
- **Executor**: Backend for task execution (local, celery, dagster)

## Quick Start

1. Create workflow in `config/workflows/my-workflow.yaml`
2. Start: `workflow.start_run(workflow_name_or_id="my-workflow")`
3. Step: `workflow.step_run(run_id="...")`

## MCP Tools

- `workflow.start_run` - Start a new workflow run
- `workflow.get_run` - Get run status
- `workflow.list_runs` - List runs with filters
- `workflow.cancel_run` - Cancel a running workflow
- `workflow.step_run` - Execute next step(s)
- `workflow.emit_event` - Emit event for wait_for_event steps

## Resources

- `workflow://schemas/definition` - Workflow definition schema
- `workflow://workflows` - Registered workflows
- `workflow://docs/step-kinds` - Step documentation
- `workflow://docs/executors` - Executor documentation
""",
    },
}
