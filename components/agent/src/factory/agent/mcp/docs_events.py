"""Event protocol documentation content."""

EVENT_PROTOCOL = """
# Agent Event Protocol

Events emitted during agent workflow execution for live UI updates.
All events go through the events brick MCP interface (events_publish).

## Event Types

| Type | Payload Fields | When |
|------|---------------|------|
| agent.session.start | session_id, user_id | Session created |
| agent.session.end | session_id, event_count | Session closed |
| agent.step.start | session_id, node_id, step_name | Agent starts a step |
| agent.step.complete | session_id, node_id, result_summary, duration_ms | Step finishes |
| agent.tool.call | session_id, tool_name, arguments_summary | Agent calls a tool |
| agent.output.text | session_id, text, format | Plain text output |
| agent.workflow.complete | session_id, status, summary, duration_ms, token_usage | Workflow done |

## Required Fields

All events MUST include: session_id, trace_id (for correlation).

## A2UI Payload Format

The a2ui field uses the standard A2UI flat component format:
```json
{"components": [
    {"id": "1", "type": "Card", "props": {"title": "..."}},
    {"id": "2", "type": "Table", "parent": "1", "props": {...}}
]}
```

Supported types: Card, Text, Table, Chart, Metric, Alert, List, Progress.
"""
