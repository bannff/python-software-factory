"""MCP primitives for permissions brick.

This package contains:
- deterministic.py: Pure query tools (capabilities, registries, schemas)
- operational.py: Stateful evaluation tools (evaluate, batch, explain)
- authoring.py: Security-gated policy management tools
- resources.py: Static/queryable data (schemas, docs, policies)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from .resources import register as register_resources
from .prompts import register as register_prompts
from .deterministic import register as register_deterministic
from .operational import register as register_operational
from .authoring import register as register_authoring

__all__ = [
    "register_resources",
    "register_prompts",
    "register_deterministic",
    "register_operational",
    "register_authoring",
]
