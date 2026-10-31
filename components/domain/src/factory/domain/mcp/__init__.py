"""MCP primitives for the domain brick.

- deterministic.py: read-only manifest queries
- operational.py: stateful engagement operations
- authoring.py: security-gated manifest CRUD
- resources.py: live manifest resource (domain://manifests/{domain_id})
- prompts.py: guided engagement workflow
"""

from .deterministic import register as register_deterministic
from .operational import register as register_operational
from .authoring import register as register_authoring
from .resources import register as register_resources
from .prompts import register as register_prompts

__all__ = [
    "register_deterministic",
    "register_operational",
    "register_authoring",
    "register_resources",
    "register_prompts",
]
