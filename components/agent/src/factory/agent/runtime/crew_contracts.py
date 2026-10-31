"""Strict frozen Crew configuration and typed Crew failures.

A Crew is a named configuration bundle — persona, project, workspace,
memory scope, inheritable model, and discovery triggers — NOT a runtime.
Identity (``tenant_id``/``owner_id``) is ambient-derived by the lifecycle
from the authenticated envelope and is never accepted from raw client
input. Crew id / memory scope use a strict lowercase grammar plus the
shared credential-shape rejection so a leaked token can never masquerade
as an identifier. Mirrors the persona ``AgentConfig`` discipline.
"""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Ambient authority — matches Session's ``Identity`` shape so the two
# owner-scoped stores agree on what a principal looks like.
Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")]

_CREW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_PERSONA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_MODEL_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")

# Known credential shapes an identifier alphabet could otherwise accept.
_CREDENTIALS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj_)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
)


def credential_clean(value: str) -> bool:
    """Reject values shaped like a known credential."""
    return not any(pattern.fullmatch(value) for pattern in _CREDENTIALS)


class CrewConflictError(RuntimeError):
    """Optimistic-concurrency (expected-revision) failure."""


class CrewNotFoundError(LookupError):
    """No owner-scoped Crew matches the reference."""


class CrewExistsError(RuntimeError):
    """Exclusive create found an existing Crew id."""


class CrewIdentityError(PermissionError):
    """Ambient identity was absent or malformed."""


class CrewModelUnresolvedError(ValueError):
    """No non-empty effective model could be resolved."""


class CrewConfig(BaseModel):
    """Frozen, owner-scoped Crew definition persisted as typed data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: Identity
    owner_id: Identity
    id: str
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=2000)] = ""
    persona_id: str
    project: Annotated[str, Field(min_length=1, max_length=512)]
    workspace: Annotated[str, Field(max_length=512)] = ""
    memory_scope: str
    model: Annotated[str, Field(max_length=256)] = ""
    triggers: Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]],
                        Field(max_length=32)] = Field(default_factory=list)
    revision: int = Field(ge=1)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _CREW_ID_RE.fullmatch(value) or not credential_clean(value):
            raise ValueError("CrewConfig.id is invalid")
        return value

    @field_validator("memory_scope")
    @classmethod
    def _validate_scope(cls, value: str) -> str:
        if not _SCOPE_RE.fullmatch(value) or not credential_clean(value):
            raise ValueError("CrewConfig.memory_scope is invalid")
        return value

    @field_validator("persona_id")
    @classmethod
    def _validate_persona(cls, value: str) -> str:
        if not _PERSONA_ID_RE.fullmatch(value) or not credential_clean(value):
            raise ValueError("CrewConfig.persona_id is invalid")
        return value

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        if value and not _MODEL_RE.fullmatch(value):
            raise ValueError("CrewConfig.model is invalid")
        return value


__all__ = [
    "CrewConfig", "CrewConflictError", "CrewExistsError", "CrewIdentityError",
    "CrewModelUnresolvedError", "CrewNotFoundError", "Identity", "credential_clean",
]
