"""MCP primitives for the learning brick.

- deterministic.py: contract-adjacent read tools (list reward sources)
- operational.py: ``learning_compute_reward`` (iterate sources → neutral result)
- resources.py: reward-signal schema + docs
"""

from . import deterministic, operational, resources
from .resources import register as register_resources

__all__ = [
    "deterministic",
    "operational",
    "resources",
    "register_resources",
]
