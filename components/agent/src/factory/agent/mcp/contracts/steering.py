"""Strict contracts for Agent steering document management."""
from __future__ import annotations

from pydantic import Field, field_validator

from .discovery import StrictDTO


class SteeringSummary(StrictDTO):
    id: str
    title: str
    sha256: str


class SteeringListOutput(StrictDTO):
    count: int
    documents: list[SteeringSummary]


class SteeringRefInput(StrictDTO):
    document_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")


class SteeringDetailOutput(SteeringSummary):
    content: str


class SteeringCreateInput(SteeringRefInput):
    content: str = Field(min_length=1, max_length=262_144)

    @field_validator("content")
    @classmethod
    def nonblank_safe(cls, value: str) -> str:
        if "\x00" in value or not value.strip():
            raise ValueError("steering content must be nonblank and cannot contain NUL")
        return value


class SteeringUpdateInput(SteeringCreateInput):
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SteeringDeleteInput(SteeringRefInput):
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SteeringMutationOutput(StrictDTO):
    created: bool
    document: SteeringDetailOutput


class SteeringDeleteOutput(StrictDTO):
    deleted: bool
    document_id: str
