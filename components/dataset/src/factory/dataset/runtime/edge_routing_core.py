"""Immutable edge-routing decision snapshot contracts."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .base import _normalize_digest, _require_non_empty


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _stable_id(value: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise ValueError("Routing IDs must be stable nonblank ASCII identifiers")
    return value
def _utc_time(value: datetime | str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Routing timestamps must be RFC 3339 UTC") from error
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Routing timestamps must be RFC 3339 UTC")
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("Routing timestamps must use UTC offset zero")
    return value.astimezone(UTC)
def _immutable_sequence(value: object) -> object:
    """Accept JSON arrays while storing validated sequences as immutable tuples."""
    return tuple(value) if isinstance(value, list) else value
class _RoutingValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
class RoutingContentRef(_RoutingValue):
    """A separately verifiable immutable JSON evidence object."""

    uri: str
    sha256: str

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return _require_non_empty(value, "Routing evidence URI")

    @field_validator("sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _normalize_digest(value, "routing evidence")
class RoutingCandidateSnapshot(_RoutingValue):
    """Only values observed about a candidate before the route decision."""

    candidate_id: str
    capability_id: str
    capabilities: tuple[str, ...] = Field(min_length=1, max_length=16)
    role: str
    model_id: str
    model_artifact_sha256: str
    observed_at: datetime
    expires_at: datetime
    status: Literal["available", "unavailable"]
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    cpu_utilization_pct: int | None = Field(default=None, ge=0, le=100)
    memory_available_mib: int | None = Field(default=None, ge=0, le=1_048_576)
    estimated_link_latency_ms: int | None = Field(default=None, ge=0, le=600_000)

    @field_validator("candidate_id", "capability_id", "role", "model_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value)

    @field_validator("capabilities")
    @classmethod
    def _capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Candidate capabilities must be unique")
        return tuple(_stable_id(item) for item in value)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _json_capabilities(cls, value: object) -> object:
        return _immutable_sequence(value)

    @field_validator("model_artifact_sha256")
    @classmethod
    def _model_digest(cls, value: str) -> str:
        return _normalize_digest(value, "routing model artifact")

    @field_validator("observed_at", "expires_at", mode="before")
    @classmethod
    def _time(cls, value: datetime | str) -> datetime:
        return _utc_time(value)

    @model_validator(mode="after")
    def _valid_window(self) -> RoutingCandidateSnapshot:
        if self.expires_at <= self.observed_at:
            raise ValueError("Candidate expiry must follow observation")
        return self
class RoutingDecisionFeatures(_RoutingValue):
    """Explicit feature allowlist frozen at decision time; no result fields."""

    group_id: str
    session_id: str
    task_id: str
    source_event_id: str
    source_event_ref: RoutingContentRef
    source_event_at: datetime
    decision_at: datetime
    task_kind: str
    policy_version: str
    policy_sha256: str
    reducer_sha256: str
    scenario_sha256: str
    required_capabilities: tuple[str, ...] = Field(min_length=1, max_length=16)
    candidate_snapshot_ref: RoutingContentRef
    candidates: tuple[RoutingCandidateSnapshot, ...] = Field(min_length=1, max_length=32)
    eligible_candidate_ids: tuple[str, ...] = Field(max_length=32)

    @field_validator(
        "required_capabilities", "candidates", "eligible_candidate_ids", mode="before",
    )
    @classmethod
    def _json_arrays(cls, value: object) -> object:
        return _immutable_sequence(value)

    @field_validator(
        "group_id", "session_id", "task_id", "source_event_id",
        "task_kind", "policy_version",
    )
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value)

    @field_validator("required_capabilities", "eligible_candidate_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Routing capability/candidate IDs must be unique")
        return tuple(_stable_id(item) for item in value)

    @field_validator("policy_sha256", "reducer_sha256", "scenario_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _normalize_digest(value, "routing pin")

    @field_validator("source_event_at", "decision_at", mode="before")
    @classmethod
    def _time(cls, value: datetime | str) -> datetime:
        return _utc_time(value)

    @model_validator(mode="after")
    def _decision_snapshot(self) -> RoutingDecisionFeatures:
        if self.source_event_at > self.decision_at:
            raise ValueError("Source event cannot follow route decision")
        by_id = {candidate.candidate_id: candidate for candidate in self.candidates}
        if len(by_id) != len(self.candidates):
            raise ValueError("Candidate IDs must be unique")
        if len({candidate.capability_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("Candidate capability IDs must be unique")
        required = set(self.required_capabilities)
        for candidate in self.candidates:
            if candidate.observed_at > self.decision_at:
                raise ValueError("Candidate snapshot cannot follow route decision")
        for candidate_id in self.eligible_candidate_ids:
            candidate = by_id.get(candidate_id)
            if candidate is None:
                raise ValueError("Eligible candidate is absent from snapshot")
            if candidate.status != "available" or candidate.expires_at <= self.decision_at:
                raise ValueError("Eligible candidate is unavailable or expired")
            if not required.issubset(candidate.capabilities):
                raise ValueError("Eligible candidate lacks required capability")
        return self
