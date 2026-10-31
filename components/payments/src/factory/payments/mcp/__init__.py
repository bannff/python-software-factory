"""MCP primitives for payments module.

This package contains:
- deterministic.py: Read-only queries (capabilities, schemas, history)
- operational.py: Stateful payment operations (create, refund)
- authoring.py: Security-gated provider configuration
- resources.py: Static/queryable data (schemas, docs, providers)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, authoring, resources, prompts

__all__ = ["deterministic", "operational", "authoring", "resources", "prompts"]
