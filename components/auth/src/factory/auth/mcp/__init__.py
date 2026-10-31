"""MCP primitives for auth module.

This package contains:
- deterministic.py: Read-only queries (capabilities, health, schemas)
- operational.py: Token operations (verify, introspect, refresh, revoke)
- authoring.py: Security-gated backend configuration
- resources.py: Static/queryable data (schemas, docs, backends)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, authoring, resources, prompts

__all__ = ["deterministic", "operational", "authoring", "resources", "prompts"]
