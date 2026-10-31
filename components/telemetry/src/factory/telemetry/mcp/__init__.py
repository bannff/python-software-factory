"""MCP primitives for telemetry module.

This package contains:
- deterministic.py: Read-only queries (metrics, exporters, context)
- operational.py: Recording operations (logs, traces, metrics)
- authoring.py: Security-gated configuration
- resources.py: Static/queryable data (schemas, docs, registries)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, authoring, resources, prompts

__all__ = ["deterministic", "operational", "authoring", "resources", "prompts"]
