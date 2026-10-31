"""MCP primitives for games module.

- deterministic.py: Contract tools + read-only queries
- operational.py: Game session management and moves
- authoring.py: Security-gated configuration changes (placeholder)
- resources.py: Schemas, docs, live data
- prompts.py: Guided workflows
- docs.py: Documentation content
- templates.py: Prompt templates
- views.py: Dashboard UI definitions
"""

from . import deterministic, operational, authoring, resources, prompts

__all__ = ["deterministic", "operational", "authoring", "resources", "prompts"]
