"""Strict Events-local normalization for the Learning MCP result envelope."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, ValidationError,
    field_validator,
)

from factory.mcp_utils.interface import ToolResult, is_bounded_json, to_plain_json

_MAX_EVIDENCE_KEYS = 256
_MAX_REWARD_VALUE = 1_000_000.0
_WALLET_PATTERN = r"^[A-Za-z0-9_.:-]{1,128}$"
_REQUIRED_RESULT_KEYS = frozenset({
    "signals", "source_id", "verdict", "scalar", "reward_value", "wallet_id",
    "provenance", "raw", "scoring",
})


class _RewardSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(min_length=1, max_length=128)
    scalar: FiniteFloat = Field(ge=-1, le=1)
    verdict: Literal["rewarded", "no_reward", "penalized"]
    reward_value: FiniteFloat = Field(ge=0, le=_MAX_REWARD_VALUE)
    wallet_id: str = Field(pattern=_WALLET_PATTERN)
    provenance: dict[str, JsonValue] = Field(
        default_factory=dict, max_length=_MAX_EVIDENCE_KEYS,
    )

    @field_validator("provenance")
    @classmethod
    def _validate_provenance(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _validate_evidence(value)


class _ComputeRewardResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    signals: list[_RewardSignal] = Field(default_factory=list, max_length=64)
    source_id: str = Field(default="", max_length=128)
    verdict: Literal["rewarded", "no_reward", "penalized"] = "no_reward"
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

    @field_validator("provenance", "raw", "scoring")
    @classmethod
    def _validate_evidence_fields(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _validate_evidence(value)


class _SuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["v1"]
    ok: Literal[True]
    data: dict[str, JsonValue]
    error: None = None
    idempotency_key: str | None = Field(default=None, max_length=256)


def normalize_learning_result(result: Any) -> dict[str, Any] | None:
    """Return a canonical Learning success result or ``None`` on any failure."""
    data = _unwrap(result)
    if data is None or not _REQUIRED_RESULT_KEYS.issubset(data):
        return None
    try:
        return _ComputeRewardResult.model_validate(data).model_dump(mode="json")
    except ValidationError:
        return None


def _unwrap(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    if isinstance(result, ToolResult):
        if result.schema_version != "v1" or result.ok is not True:
            return None
        try:
            candidate = to_plain_json(result.model_dump(mode="python"))
        except (TypeError, ValueError):
            return None
    elif isinstance(result, Mapping):
        if "schema_version" not in result:
            return None
        candidate = dict(result)
    else:
        return None
    if not is_bounded_json(candidate, max_sequence_items=_MAX_EVIDENCE_KEYS):
        return None
    try:
        return dict(_SuccessEnvelope.model_validate(candidate).data)
    except ValidationError:
        return None


def _validate_evidence(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if len(value) > _MAX_EVIDENCE_KEYS or not is_bounded_json(
        value, max_sequence_items=_MAX_EVIDENCE_KEYS,
    ):
        raise ValueError("evidence must be a bounded JSON object")
    return value


__all__ = ["normalize_learning_result"]
