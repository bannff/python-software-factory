"""MCP primitives for events module.

This package contains:
- deterministic.py: Read-only query tools
- operational.py: Stateful event operations
- authoring.py: Security-gated configuration
- resources.py: Static/queryable data (schemas, docs, subscriptions)
- prompts.py: Guided workflows for common tasks
- views.py: UIView definitions for dashboard rendering
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, authoring, resources, prompts, views

__all__ = ["deterministic", "operational", "authoring", "resources", "prompts", "views"]
