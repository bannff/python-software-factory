"""Owner-scoped skill enablement policy: which persona skills NOT to attach."""
from __future__ import annotations

import re
from threading import Lock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_SKILLS = 128
_SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SkillPolicy(BaseModel):
    """Skills the owner has switched off; empty means every persona skill attaches."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    disabled_skills: tuple[str, ...] = Field(default=(), max_length=_MAX_SKILLS)
    revision: int = Field(default=0, ge=0)

    @field_validator("disabled_skills")
    @classmethod
    def _valid_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(not _SKILL_ID.fullmatch(item) for item in value):
            raise ValueError("invalid skill ids")
        return value

    def apply(self, skills: list[str]) -> list[str]:
        """Persona skills minus the owner's disabled set, order preserved."""
        disabled = set(self.disabled_skills)
        return [item for item in skills if item not in disabled]


class StaleSkillPolicy(ValueError):
    """Raised when revision compare-and-swap fails."""


class SkillPolicyStore(Protocol):
    def get(self, tenant_id: str, owner_id: str) -> SkillPolicy: ...

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        disabled_skills: tuple[str, ...],
    ) -> SkillPolicy: ...


class InMemorySkillPolicyStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], SkillPolicy] = {}
        self._lock = Lock()

    def get(self, tenant_id: str, owner_id: str) -> SkillPolicy:
        with self._lock:
            return self._rows.get((tenant_id, owner_id), SkillPolicy())

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        disabled_skills: tuple[str, ...],
    ) -> SkillPolicy:
        with self._lock:
            current = self._rows.get((tenant_id, owner_id), SkillPolicy())
            if current.revision != expected_revision:
                raise StaleSkillPolicy("stale skill policy")
            result = SkillPolicy(disabled_skills=disabled_skills, revision=current.revision + 1)
            self._rows[(tenant_id, owner_id)] = result
            return result


__all__ = ["InMemorySkillPolicyStore", "SkillPolicy", "SkillPolicyStore", "StaleSkillPolicy"]
