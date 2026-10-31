"""DTOs for blob and mutable document Storage MCP tools."""
from __future__ import annotations

from pydantic import Field

from .base import DTO, JsonObject


class BlobPutInput(DTO):
    key: str
    data: str
    content_type: str = "text/plain"


class BlobPutOutput(DTO):
    key: str
    size: int
    etag: str


class BlobGetInput(DTO):
    key: str


class BlobGetOutput(DTO):
    key: str
    size: int
    content_type: str
    data: str


class BlobDeleteInput(DTO):
    key: str


class BlobDeleteOutput(DTO):
    deleted: bool
    key: str


class BlobListInput(DTO):
    prefix: str = ""
    limit: int = 100


class BlobSummary(DTO):
    key: str
    size: int


class BlobListOutput(DTO):
    blobs: list[BlobSummary]


class DocInsertInput(DTO):
    collection: str
    data: JsonObject
    doc_id: str | None = None


class DocInsertOutput(DTO):
    id: str
    collection: str


class DocGetInput(DTO):
    collection: str
    doc_id: str


class DocGetOutput(DTO):
    found: bool
    collection: str
    id: str
    data: JsonObject | None = None


class DocFindInput(DTO):
    collection: str
    query: JsonObject
    limit: int = 100


class DocumentData(DTO):
    id: str
    data: JsonObject


class DocFindOutput(DTO):
    documents: list[DocumentData] = Field(default_factory=list)


class DocDeleteInput(DTO):
    collection: str
    doc_id: str


class DocDeleteOutput(DTO):
    deleted: bool
    collection: str
    id: str
