"""Typed MCP boundary for Portability's export tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ExportPreviewInput(DTO):
    kinds: list[str] | None = Field(default=None, max_length=8)


class KindSummary(DTO):
    kind: str
    count: int = Field(ge=0)
    excluded: int = Field(ge=0)
    digest: str


class ExportPreviewOutput(DTO):
    bundle_version: int
    adapter: str
    content_digest: str
    kinds: list[KindSummary]


class ExportInput(DTO):
    kinds: list[str] | None = Field(default=None, max_length=8)
    destination_name: str = Field(min_length=1, max_length=200)


class ExportOutput(DTO):
    path: str
    bundle_version: int
    adapter: str
    content_digest: str
    bytes_written: int
    kinds: list[KindSummary]


__all__ = ["ExportInput", "ExportOutput", "ExportPreviewInput", "ExportPreviewOutput", "KindSummary"]
