"""Strict operational Permissions MCP DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue, field_validator

from .base import (
    Identifier,
    JsonObject,
    OutputModel,
    StrictModel,
    _MAX_BATCH_REQUESTS,
    _MAX_LIST_ITEMS,
    bounded_json,
    bounded_object,
)

_MAX_ISSUES = 64
ProviderErrorCode = Literal[
    "provider_error", "validation_error", "access_denied", "throttled", "internal_error",
]
ProviderDiagnosticCode = Literal[
    "provider_diagnostic", "validation_error", "access_denied", "throttled", "internal_error",
]


class EnvelopeInput(StrictModel):
    tenant_id: str | None = Field(default=None, max_length=128)
    principal_id: str | None = Field(default=None, max_length=256)
    session_id: str | None = Field(default=None, max_length=256)
    request_id: str | None = Field(default=None, max_length=256)
    correlation_id: str | None = Field(default=None, max_length=256)
    agent_id: str | None = Field(default=None, max_length=256)
    tool_name: str | None = Field(default=None, max_length=256)
    timestamp: datetime | None = None
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def _timestamp_is_timezone_aware(cls, value: object) -> object:
        """Accept only native or RFC3339/ISO date-times carrying a timezone."""
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("timestamp must include a timezone")
            return value
        if not isinstance(value, str):
            raise ValueError("timestamp must be a timezone-aware RFC3339 string")
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be a timezone-aware RFC3339 string") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return parsed

    @field_validator("attributes")
    @classmethod
    def _attributes_are_bounded(cls, value: dict[str, str | int | float | bool]) -> dict[str, str | int | float | bool]:
        if len(value) > 64:
            raise ValueError("attributes too large (max 64 keys)")
        for key, item in value.items():
            if not key or len(key) > 64:
                raise ValueError("attribute keys must be 1..64 characters")
            if isinstance(item, str) and len(item) > 512:
                raise ValueError("attribute string values must be at most 512 characters")
        bounded_json(value, label="envelope.attributes")
        return value


class ResourceInput(StrictModel):
    type: Identifier
    id: str | None = Field(default=None, max_length=256)
    owner: str | None = Field(default=None, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=128)
    visibility: Literal["private", "team", "public"] | None = None
    attributes: JsonObject = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def _attributes_are_bounded(cls, value: JsonObject) -> JsonObject:
        return bounded_object(value, label="resource.attributes")


class PermissionRequestInput(StrictModel):
    action: Identifier
    resource: ResourceInput
    context: JsonObject | None = None

    @field_validator("context")
    @classmethod
    def _context_is_bounded(cls, value: JsonObject | None) -> JsonObject | None:
        if value is not None:
            bounded_object(value, label="context")
        return value


class EvaluateInput(PermissionRequestInput):
    envelope: EnvelopeInput | None = None


class BatchEvaluateInput(StrictModel):
    requests: list[PermissionRequestInput] = Field(max_length=_MAX_BATCH_REQUESTS)
    envelope: EnvelopeInput | None = None


class PolicyEvidenceOutput(OutputModel):
    """Canonical bounded evidence for a determining policy or matched rule."""

    policy_id: str = Field(min_length=1, max_length=128)
    rule_id: str | None = Field(default=None, min_length=1, max_length=128)
    effect: Literal["allow", "deny"] | None = None

    @field_validator("policy_id", "rule_id")
    @classmethod
    def _ids_have_no_control_chars(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("policy evidence identifiers cannot contain control characters")
        return value


MatchedRuleOutput = PolicyEvidenceOutput


class ProviderDiagnosticOutput(OutputModel):
    code: ProviderDiagnosticCode


class ProviderErrorOutput(OutputModel):
    code: ProviderErrorCode


class DecisionOutput(OutputModel):
    decision: Literal["allow", "deny"]
    reason: str | None = Field(default=None, max_length=256)
    policy_id: str | None = Field(default=None, max_length=128)
    rule_id: str | None = Field(default=None, max_length=128)
    obligations: list[JsonObject] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)
    determining_policies: list[PolicyEvidenceOutput] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)
    diagnostics: list[ProviderDiagnosticOutput] = Field(default_factory=list, max_length=_MAX_ISSUES)
    errors: list[ProviderErrorOutput] = Field(default_factory=list, max_length=_MAX_ISSUES)

    @field_validator("obligations")
    @classmethod
    def _obligations_are_bounded(cls, value: list[JsonObject]) -> list[JsonObject]:
        for item in value:
            bounded_object(item, label="obligations item")
        return value


class BatchEvaluateOutput(OutputModel):
    decisions: list[DecisionOutput] = Field(max_length=_MAX_BATCH_REQUESTS)
    count: int = Field(ge=0, le=_MAX_BATCH_REQUESTS)


class ExplainOutput(OutputModel):
    decision: Literal["allow", "deny"]
    reason: str | None = Field(default=None, max_length=256)
    trace_id: str | None = Field(default=None, max_length=256)
    matched_rules: list[PolicyEvidenceOutput] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)
    obligations: list[JsonObject] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)
    determining_policies: list[PolicyEvidenceOutput] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)
    diagnostics: list[ProviderDiagnosticOutput] = Field(default_factory=list, max_length=_MAX_ISSUES)
    errors: list[ProviderErrorOutput] = Field(default_factory=list, max_length=_MAX_ISSUES)

    @field_validator("obligations")
    @classmethod
    def _obligations_are_bounded(cls, value: list[JsonObject]) -> list[JsonObject]:
        for item in value:
            bounded_object(item, label="explanation obligations")
        return value


__all__ = [
    "BatchEvaluateInput", "BatchEvaluateOutput", "DecisionOutput", "EnvelopeInput",
    "EvaluateInput", "ExplainOutput", "MatchedRuleOutput", "PermissionRequestInput",
    "PolicyEvidenceOutput", "ProviderDiagnosticOutput", "ProviderErrorOutput", "ResourceInput",
]
