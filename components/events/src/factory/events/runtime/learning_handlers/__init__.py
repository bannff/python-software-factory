"""Canonical learning-event handlers package.

Re-exports the public ``handle_*`` callables so existing import paths
(``from factory.events.runtime.learning_handlers import ...``) keep working.
"""

from __future__ import annotations

from .convergence import handle_convergence_check
from .improvement import handle_workflow_improvement
from .memory import handle_memory_learning
from .reward import handle_blockchain_reward

__all__ = [
    "handle_blockchain_reward",
    "handle_memory_learning",
    "handle_convergence_check",
    "handle_workflow_improvement",
]
