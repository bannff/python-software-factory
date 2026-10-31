"""Durable task journal value objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PayloadPredicate(BaseModel):
    """Exact JSON-Pointer equality predicate over a tool payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    pointer: str = Field(pattern=r"^(|/.*)$")
    equals: Any


class TaskOutcomePolicy(BaseModel):
    """Declarative classification for transport-successful tool payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    success: PayloadPredicate
    continuation: PayloadPredicate | None = None
    retryable: PayloadPredicate | None = None
    error_pointer: str | None = Field(default=None, pattern=r"^(|/.*)$")


@dataclass(frozen=True)
class CancelledAttempt:
    workflow_run_id: str
    attempt_id: str
    revision: int
    status: str
    canonical_input: str


@dataclass(frozen=True)
class AttemptClaim:
    attempt_id: str
    step_execution_id: str
    attempt_number: int
    revision: int
    status: str
    lease_token: str | None
    canonical_input: str
    output: Any | None = None
    error: str | None = None


@dataclass(frozen=True)
class VerifiedStepResult:
    attempt_id: str
    attempt_number: int
    output: Any
    evidence: dict[str, Any]


@dataclass(frozen=True)
class TaskExecutionResult:
    status: str
    output: Any | None = None
    transport_envelope: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    error: str | None = None
    retryable: bool = False
