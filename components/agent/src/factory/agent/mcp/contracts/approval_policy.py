"""Strict MCP contracts for the owner tool approval list."""
from __future__ import annotations

from pydantic import Field, field_validator

from .discovery import StrictDTO

_TOOL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$"


class ApprovalPolicyGetInput(StrictDTO):
    pass


class ApprovalPolicyUpdateInput(StrictDTO):
    tool_names: list[str] = Field(max_length=128)
    expected_revision: int = Field(ge=0)

    @field_validator("tool_names")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("approval tool names must be unique")
        import re
        if any(not re.fullmatch(_TOOL_PATTERN, name) for name in value):
            raise ValueError("invalid approval tool name")
        return value


class ApprovalPolicyOutput(StrictDTO):
    tool_names: list[str]
    revision: int = Field(ge=0)


__all__ = [
    "ApprovalPolicyGetInput", "ApprovalPolicyOutput", "ApprovalPolicyUpdateInput",
]
