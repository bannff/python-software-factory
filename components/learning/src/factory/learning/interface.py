"""Polylith Interface for the learning module.

The public MCP surface is intentionally small: the two live tools keep their
flat wire contracts while using strict local DTOs and typed v1 ToolResult
egress; resources remain native string schema/document resources. Typed and
serialized v1 success envelopes are accepted at cross-brick adapter seams;
failed, wrong-version, or unbounded results abstain, while bare mappings need
an explicit shape validator. Learning inputs omit ``idempotency_key`` and
therefore do not expose request-level replay. The runtime and RewardSignal
API below are the pack-facing seam for registering neutral reward sources
without domain branches or cross-brick imports.
"""

from .server import create_mcp_server as create_server
from .runtime.runtime import LearningRuntime as Runtime
from .runtime.registry import (
    register_reward_source,
    get_registry,
    reset_registry,
)
from .runtime.ports import RewardSourcePort
from .runtime.models import RewardSignal

__all__ = [
    "Runtime",
    "create_server",
    "register_reward_source",
    "get_registry",
    "reset_registry",
    "RewardSourcePort",
    "RewardSignal",
]
