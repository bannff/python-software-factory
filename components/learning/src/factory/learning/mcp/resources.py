"""MCP resources for the learning brick — schemas + docs."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING, Callable

from .contracts import RewardSignalOutput

if TYPE_CHECKING:
    from ..runtime.runtime import LearningRuntime

_REWARD_SIGNAL_SCHEMA = RewardSignalOutput.model_json_schema()
_REWARD_SIGNAL_SCHEMA["description"] = "Canonical v1 reward signal data."
_REWARD_SIGNAL_SCHEMA["properties"]["provenance"]["description"] = "Bounded JSON source detail."

_DOC = (
    "# Learning brick\n\n"
    "Domain-agnostic reward-signal seam. `learning_compute_reward` iterates "
    "registered reward sources for a completed run and returns the winning "
    "neutral signal in a versioned ToolResult envelope (`ToolResult[ComputeRewardOutput]`). "
    "Both public tools retain flat keyword arguments and their existing defaults; "
    "strict same-brick Pydantic v2 DTOs reject unknown fields and non-coercive "
    "wire values before the runtime executes. A successful abstention has "
    "`signals=[]`, `source_id=\"\"`, and `verdict=\"no_reward\"`; unexpected "
    "tool failures use a failed envelope with `data=null`. The "
    "`learning://schemas/reward-signal` resource is a JSON Schema for one "
    "`RewardSignalOutput` data object, not the full compute output or its "
    "envelope. `learning://docs/learning` is this native human-readable "
    "overview and both URIs are stable resource contracts. Reward evidence is "
    "bounded JSON: at most 256 object keys/list items, nesting depth 12, "
    "65,536-character strings, 1,000,000,000-magnitude integers, and 1 MiB "
    "serialized UTF-8 per evidence object. Outputs cap signals at 64 and "
    "reward values at 1,000,000; wallet IDs use `[A-Za-z0-9_.:-]{1,128}`. "
    "Cross-brick adapters accept typed or serialized v1 success envelopes, "
    "reject failed/wrong-version/unbounded envelopes, and accept bare mappings "
    "only through explicit shape validators. Invalid or absent source results "
    "abstain rather than becoming a reward. Built-in sources are code-registered; packs and user extensions are DATA overlays registered "
    "through `factory.learning.interface.register_reward_source` — the engine "
    "never branches on a domain literal. Built-in sources are `gt-findings`, "
    "`llm-judge`, `user-feedback`, and `telemetry`; built-ins win on `source_id` "
    "collisions and a colliding pack/user source is ignored; packs may register more. "
    "The strict input DTOs intentionally do not expose `idempotency_key`, so "
    "Learning request tools do not provide request-level replay; the envelope "
    "idempotency field remains null. Downstream event idempotency is separate.\n"
)


def register(mcp: Any, get_runtime: Callable[[], "LearningRuntime"]) -> None:
    """Register learning resources with the MCP server."""

    @mcp.resource("learning://schemas/reward-signal")
    def reward_signal_schema() -> str:
        """JSON schema for a neutral reward signal."""
        return json.dumps(_REWARD_SIGNAL_SCHEMA, indent=2)

    @mcp.resource("learning://docs/learning")
    def learning_doc() -> str:
        """Human-readable overview of the learning brick."""
        return _DOC
