"""Strict MCP contracts for the owner skill enablement policy."""
from __future__ import annotations

import re

from pydantic import Field, field_validator

from .discovery import StrictDTO

_SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SkillPolicyGetInput(StrictDTO):
    pass


class SkillPolicyUpdateInput(StrictDTO):
    disabled_skills: list[str] = Field(max_length=128)
    expected_revision: int = Field(ge=0)

    @field_validator("disabled_skills")
    @classmethod
    def _valid(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not _SKILL_ID.fullmatch(item) for item in value):
            raise ValueError("invalid skill ids")
        return value


class SkillPolicyOutput(StrictDTO):
    disabled_skills: list[str]
    revision: int = Field(ge=0)


__all__ = ["SkillPolicyGetInput", "SkillPolicyOutput", "SkillPolicyUpdateInput"]
