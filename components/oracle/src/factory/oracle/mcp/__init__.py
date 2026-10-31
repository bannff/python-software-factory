"""MCP primitives for the oracle brick.

- deterministic.py: contract tools + read-only verifier/state queries
- operational.py: ``oracle_verify_finding`` (verify + atomic persist)
- authoring.py: security-gated config changes (none today)
- resources.py: schemas + docs
- prompts.py: guided verification workflow
"""

from . import deterministic, operational, authoring, resources, prompts
from .resources import register as register_resources
from .prompts import register as register_prompts

__all__ = [
    "deterministic",
    "operational",
    "authoring",
    "resources",
    "prompts",
    "register_resources",
    "register_prompts",
]
