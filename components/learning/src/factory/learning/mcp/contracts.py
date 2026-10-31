"""Strict DTOs for the Learning brick MCP boundary."""
from __future__ import annotations

import json
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, field_validator

_MAX_EVIDENCE_KEYS = 256
_MAX_NESTING = 12
_MAX_EVIDENCE_STRING = 65_536
_MAX_EVIDENCE_INTEGER = 1_000_000_000
_MAX_EVIDENCE_BYTES = 1_048_576
_MAX_REWARD_VALUE = 1_000_000.0
_MAX_ID_LENGTH = 256
_MAX_INPUT_TEXT = 65_536
_WALLET_PATTERN = r"^[A-Za-z0-9_.:-]{1,128}$"


class StrictModel(BaseModel):
    """Reject unknown fields, non-finite values, and oversized evidence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("provenance", "raw", "scoring", check_fields=False)
    @classmethod
    def _validate_evidence(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(value) > _MAX_EVIDENCE_KEYS or not _json_safe(value) or not _json_size_ok(value):
            raise ValueError("evidence must be a bounded JSON object")
        return value


class EmptyInput(StrictModel):
    """Input DTO for a tool with no public arguments."""


class RewardSourcesOutput(StrictModel):
    """Registered neutral reward-source identifiers."""

    source_ids: list[str] = Field(default_factory=list, max_length=128)


class ComputeRewardInput(StrictModel):
    """Flat public inputs for neutral reward computation."""

    graph_id: str = Field(default="", max_length=_MAX_ID_LENGTH)
    run_id: str = Field(default="", max_length=_MAX_ID_LENGTH)
    vuln_class: str = Field(default="", max_length=_MAX_ID_LENGTH)
    domain_class: str = Field(default="", max_length=_MAX_ID_LENGTH)
    workflow_type: str = Field(default="auto", max_length=128)
    target_app: str = Field(default="", max_length=_MAX_ID_LENGTH)
    input_summary: str = Field(default="", max_length=_MAX_INPUT_TEXT)
    output_summary: str = Field(default="", max_length=_MAX_INPUT_TEXT)
    feedback_verdict: str = Field(default="", max_length=128)
    tool_error_rate: FiniteFloat | None = None


RewardVerdict = Literal["rewarded", "no_reward", "penalized"]


class RewardSignalOutput(StrictModel):
    """One signed, source-agnostic reward signal."""

    source_id: str = Field(min_length=1, max_length=128)
    scalar: FiniteFloat = Field(ge=-1, le=1)
    verdict: RewardVerdict
    reward_value: FiniteFloat = Field(ge=0, le=_MAX_REWARD_VALUE)
    wallet_id: str = Field(pattern=_WALLET_PATTERN)
    provenance: dict[str, JsonValue] = Field(
        default_factory=dict, max_length=_MAX_EVIDENCE_KEYS,
    )


class ComputeRewardOutput(StrictModel):
    """Winning signal plus bounded JSON source evidence."""

    signals: list[RewardSignalOutput] = Field(default_factory=list, max_length=64)
    source_id: str = Field(default="", max_length=128)
    verdict: RewardVerdict = "no_reward"
    scalar: FiniteFloat = Field(default=0.0, ge=-1, le=1)
    reward_value: FiniteFloat = Field(default=0.0, ge=0, le=_MAX_REWARD_VALUE)
    wallet_id: str = Field(default="wallet-kiro-agent", pattern=_WALLET_PATTERN)
    provenance: dict[str, JsonValue] = Field(
        default_factory=dict, max_length=_MAX_EVIDENCE_KEYS,
    )
    raw: dict[str, JsonValue] = Field(
        default_factory=dict, max_length=_MAX_EVIDENCE_KEYS,
    )
    scoring: dict[str, JsonValue] = Field(
        default_factory=dict, max_length=_MAX_EVIDENCE_KEYS,
    )


def _json_safe(value: Any, depth: int = 0) -> bool:
    if depth > _MAX_NESTING:
        return False
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        return len(value) <= _MAX_EVIDENCE_STRING
    if isinstance(value, int):
        return abs(value) <= _MAX_EVIDENCE_INTEGER
    if isinstance(value, float):
        return isfinite(value)
    if isinstance(value, dict):
        return len(value) <= _MAX_EVIDENCE_KEYS and all(
            isinstance(key, str)
            and len(key) <= _MAX_EVIDENCE_STRING
            and _json_safe(item, depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return len(value) <= _MAX_EVIDENCE_KEYS and all(
            _json_safe(item, depth + 1) for item in value
        )
    return False


def _json_size_ok(value: Any) -> bool:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError):
        return False
    return len(encoded.encode("utf-8")) <= _MAX_EVIDENCE_BYTES


__all__ = [
    "ComputeRewardInput",
    "ComputeRewardOutput",
    "EmptyInput",
    "RewardSignalOutput",
    "RewardSourcesOutput",
    "RewardVerdict",
    "StrictModel",
]
