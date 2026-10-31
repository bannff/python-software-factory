"""Pydantic boundary models for remaining kb operational tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KbSearchRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=1000)
    filters: dict[str, Any] | None = None
    tenant_id: str | None = None
    principal_id: str | None = None
    idempotency_key: str | None = None


class KbSearchHit(BaseModel):
    document_id: str
    content: str
    score: float
    source: str = ""


class KbSearchResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    results: list[KbSearchHit] = Field(default_factory=list)
    total: int = 0
    backend: str | None = None
    error: str | None = None


class KbDocumentIdRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    document_id: str = Field(..., min_length=1)
    idempotency_key: str | None = None


class KbGetDocumentResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    found: bool
    document: dict[str, Any] | None = None
    error: str | None = None


class KbDeleteDocumentResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    ok: bool
    document_id: str


class KbListDocumentsRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    limit: int = Field(default=100, ge=1, le=10_000)
    idempotency_key: str | None = None


class KbListDocumentsResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    documents: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class KbBackfillRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    limit: int = Field(default=100, ge=1, le=10_000)
    idempotency_key: str | None = None


class KbBackfillResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    backfilled: int | None = None
    limit: int | None = None
    error: str | None = None


__all__ = [
    "KbBackfillRequest",
    "KbBackfillResult",
    "KbDeleteDocumentResult",
    "KbDocumentIdRequest",
    "KbGetDocumentResult",
    "KbListDocumentsRequest",
    "KbListDocumentsResult",
    "KbSearchHit",
    "KbSearchRequest",
    "KbSearchResult",
]
