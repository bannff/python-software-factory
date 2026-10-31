"""Strict contracts for artifact publish/refresh/unpublish (row 67)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.models import PublicationNotice
from .contracts import ArtifactRefInput


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PublishInput(ArtifactRefInput):
    provider: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")


class PublicationOutput(DTO):
    publication: PublicationNotice


class PublishProvidersOutput(DTO):
    providers: list[str]


__all__ = [
    "PublicationOutput", "PublishInput", "PublishProvidersOutput",
]
