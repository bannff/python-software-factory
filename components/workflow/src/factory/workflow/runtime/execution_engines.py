"""Frozen provider-neutral execution-engine definitions for Workflow."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import canonical_json, canonical_loads
from .models import ToolTarget
from .task_models import TaskOutcomePolicy

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_ARGUMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REQUIRED = frozenset({"request", "provider_request_digest", "workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest"})


class ExecutionEngineSpec(BaseModel):
    """Frozen provider contract; Workflow forwards opaque request material."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    engine_id: str
    schema_version: str = "v1"
    invoke_target: ToolTarget
    cancel_target: ToolTarget | None = None
    target_arguments: dict[str, str] = Field(default_factory=lambda: {
        name: name for name in sorted(_REQUIRED)
    })
    outcome: TaskOutcomePolicy
    max_attempts: int = Field(default=2, ge=1, le=100)
    max_continuations: int = Field(default=0, ge=0, le=10_000)
    service_binding: str = "execution"

    @model_validator(mode="after")
    def _validate_contract(self) -> "ExecutionEngineSpec":
        if _ID.fullmatch(self.engine_id) is None:
            raise ValueError("engine_id must be a safe identifier")
        if self.service_binding != "execution":
            raise ValueError("execution engines require execution service binding")
        continued = self.outcome.continuation is not None
        if continued != (self.max_continuations > 0):
            raise ValueError("continuation outcome requires a positive cap")
        if set(self.target_arguments) != _REQUIRED:
            raise ValueError("target_arguments must map every execution field")
        values = list(self.target_arguments.values())
        if len(values) != len(set(values)) or any(_ARGUMENT.fullmatch(v) is None for v in values):
            raise ValueError("target argument names must be distinct identifiers")
        return self

    @property
    def registration_digest(self) -> str:
        return hashlib.sha256(canonical_json(self.model_dump(mode="json")).encode()).hexdigest()

    def frozen(self) -> dict[str, Any]:
        return canonical_loads(canonical_json(self.model_dump(mode="json")))


class ExecutionEngineRegistry:
    def __init__(self, specs: list[ExecutionEngineSpec]) -> None:
        self._specs = {spec.engine_id: spec for spec in specs}
        if len(self._specs) != len(specs):
            raise ValueError("execution engine ids must be unique")

    def resolve(self, engine_id: str) -> ExecutionEngineSpec:
        try:
            return self._specs[engine_id]
        except KeyError as exc:
            raise ValueError(f"unknown execution engine: {engine_id}") from exc

    def capabilities(self) -> list[dict[str, str]]:
        return [{"engine_id": s.engine_id, "registration_digest": s.registration_digest} for s in self._specs.values()]


def default_execution_engines() -> ExecutionEngineRegistry:
    """Return no providers; applications inject provider registrations at composition."""
    return ExecutionEngineRegistry([])


__all__ = ["ExecutionEngineRegistry", "ExecutionEngineSpec", "default_execution_engines"]
