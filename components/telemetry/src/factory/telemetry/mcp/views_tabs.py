"""Tab and action builders for Telemetry (Observability) dashboard.

Exports:
- telemetry_read_tabs(): read-only tabs component
- telemetry_actions(): list of write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



# ── Read-only tabs ─────────────────────────────────────────────────


def telemetry_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only telemetry data."""
    return {
        "id": "telemetry-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "metrics", "label": "Metrics Summary",
                 "lazy_tool": "telemetry_get_metrics_summary",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "registry", "label": "Metric Registry",
                 "lazy_tool": "telemetry_get_metric_registry",
                 "result_hints": {"searchable": True}},
                {"id": "exporters", "label": "Exporters",
                 "lazy_tool": "telemetry_get_exporter_registry",
                 "result_hints": {"prefer": "stat_grid"}},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def telemetry_actions() -> list[dict[str, Any]]:
    """Return action definitions for the telemetry action pane."""
    return [
        _record_llm(),
        _record_agent(),
        _record_tool(),
        _record_log(),
        _flush(),
    ]


def _record_llm() -> dict[str, Any]:
    return {
        "id": "record-llm", "label": "Record LLM Interaction",
        "icon": "🤖",
        "tool": "telemetry_record_llm_interaction",
        "submit_label": "Record",
        "fields": [
            {"name": "model", "label": "Model", "type": "text",
             "placeholder": "anthropic.claude-sonnet-4-5-20250929-v1:0",
             "tooltip": "Model identifier for the LLM call"},
            {"name": "input_tokens", "label": "Input Tokens",
             "type": "number", "placeholder": "500",
             "tooltip": "Number of prompt tokens consumed"},
            {"name": "output_tokens", "label": "Output Tokens",
             "type": "number", "placeholder": "200",
             "tooltip": "Number of completion tokens generated"},
            {"name": "latency_ms", "label": "Latency (ms)",
             "type": "number", "placeholder": "1200",
             "tooltip": "Round-trip latency in milliseconds"},
            {"name": "cost_usd", "label": "Cost (USD)",
             "type": "number", "placeholder": "0.003",
             "tooltip": "Estimated cost of this LLM call"},
        ],
    }


def _record_agent() -> dict[str, Any]:
    return {
        "id": "record-agent", "label": "Record Agent Execution",
        "icon": "⚡",
        "tool": "telemetry_record_agent_execution",
        "submit_label": "Record",
        "fields": [
            {"name": "agent_id", "label": "Agent ID", "type": "text",
             "placeholder": "reasoning-agent",
             "tooltip": "Identifier of the agent that executed"},
            {"name": "workflow_id", "label": "Workflow ID",
             "type": "text", "placeholder": "wf-001",
             "tooltip": "Workflow this execution belongs to"},
            {"name": "success", "label": "Success", "type": "select",
             "options": [{"value": "true", "label": "✅ Success"},
                         {"value": "false", "label": "❌ Failed"}],
             "tooltip": "Whether the agent execution succeeded"},
            {"name": "latency_ms", "label": "Latency (ms)",
             "type": "number", "placeholder": "3500",
             "tooltip": "Total execution time in milliseconds"},
        ],
    }


def _record_tool() -> dict[str, Any]:
    return {
        "id": "record-tool", "label": "Record Tool Invocation",
        "icon": "🔧",
        "tool": "telemetry_record_tool_invocation",
        "submit_label": "Record",
        "fields": [
            {"name": "tool_name", "label": "Tool Name", "type": "text",
             "placeholder": "graph_find_entities",
             "tooltip": "Name of the MCP tool that was invoked"},
            {"name": "success", "label": "Success", "type": "select",
             "options": [{"value": "true", "label": "✅ Success"},
                         {"value": "false", "label": "❌ Failed"}],
             "tooltip": "Whether the tool call succeeded"},
            {"name": "latency_ms", "label": "Latency (ms)",
             "type": "number", "placeholder": "150",
             "tooltip": "Tool execution time in milliseconds"},
        ],
    }


def _record_log() -> dict[str, Any]:
    return {
        "id": "record-log", "label": "Record Log Entry", "icon": "📝",
        "tool": "telemetry_record_log",
        "submit_label": "Record",
        "fields": [
            {"name": "severity", "label": "Severity", "type": "select",
             "options": [
                 {"value": "DEBUG", "label": "🔍 DEBUG"},
                 {"value": "INFO", "label": "ℹ️ INFO"},
                 {"value": "WARN", "label": "⚠️ WARN"},
                 {"value": "ERROR", "label": "🔴 ERROR"},
             ],
             "tooltip": "Log severity level (OTLP standard)"},
            {"name": "body", "label": "Message", "type": "textarea",
             "placeholder": "Something happened...",
             "tooltip": "Log message body"},
        ],
    }


def _flush() -> dict[str, Any]:
    return {
        "id": "flush", "label": "Flush Telemetry", "icon": "🔄",
        "tool": "telemetry_flush_telemetry",
        "submit_label": "Flush Now",
        "fields": [
            {"name": "timeout_ms", "label": "Timeout (ms)",
             "type": "number", "placeholder": "5000",
             "tooltip": "Max wait time for flush to complete"},
        ],
    }
