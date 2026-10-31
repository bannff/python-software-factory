"""Base models, validation helpers, and reference types for dataset contracts."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _normalize_digest(value: str, label: str) -> str:
    digest = value.strip().lower()
    if not _DIGEST_RE.fullmatch(digest):
        raise ValueError(f"Invalid {label} digest")
    return digest


def _require_non_empty(value: str, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} is required")
    return stripped


class DatasetInputRef(BaseModel):
    """An immutable source artifact with an optional domain-neutral routing role."""

    uri: str
    digest: str
    artifact_role: str | None = Field(
        default=None,
        description="Optional domain-neutral role used to route this artifact to recipe inputs.",
    )

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        return _require_non_empty(value, "Dataset input URI")

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _normalize_digest(value, "dataset input")

    @field_validator("artifact_role")
    @classmethod
    def _validate_artifact_role(cls, value: str | None) -> str | None:
        return _require_non_empty(value, "Dataset artifact role") if value is not None else None


class DatasetSnapshotRef(BaseModel):
    """Immutable content-addressed snapshot used during materialization."""

    uri: str
    digest: str

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        return _require_non_empty(value, "Snapshot URI")

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _normalize_digest(value, "snapshot")


class DatasetToolSchemaSnapshotRef(DatasetSnapshotRef):
    """Immutable allowlisted APIGenMT tool schema snapshot reference."""

    allowed_tools: list[str] = Field(default_factory=list)

    @field_validator("allowed_tools")
    @classmethod
    def _validate_allowed_tools(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tool_name in value:
            name = tool_name.strip()
            if not name:
                raise ValueError("Allowed tool names must be non-empty")
            if name not in cleaned:
                cleaned.append(name)
        return cleaned


class DatasetExecutionPolicy(BaseModel):
    """Explicit execution policy for durable dataset materialization."""

    fail_closed: bool = True
    allowed_fallbacks: list[str] = Field(default_factory=list)
    retry_from_checkpoint_only: bool = True

    @field_validator("allowed_fallbacks")
    @classmethod
    def _validate_allowed_fallbacks(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for backend in value:
            name = backend.strip()
            if not name:
                raise ValueError("Allowed fallback backends must be non-empty")
            if name not in cleaned:
                cleaned.append(name)
        return cleaned


class DatasetFallbackRecord(BaseModel):
    """Typed lineage for an authorized fallback execution."""

    requested_backend: str
    actual_backend: str
    reason: str
    degraded_quality: bool
    authorized: bool

    @field_validator("requested_backend", "actual_backend", "reason")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _require_non_empty(value, "Dataset fallback field")


class DatasetProvenanceRecord(BaseModel):
    """Typed provenance for a completed dataset bundle or stage checkpoint."""

    materializer: str
    job_id: str

    @field_validator("materializer", "job_id")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _require_non_empty(value, "Dataset provenance field")


class DatasetQualityResults(BaseModel):
    """Typed quality results attached to a completed dataset bundle."""

    checks: dict[str, str] = Field(default_factory=dict)

    @computed_field(return_type=bool)
    @property
    def passed(self) -> bool:
        """True only if every check value is not a failure."""
        return all(
            v == "passed" or v.startswith("passed:") or v.startswith("warn:")
            for v in self.checks.values()
        )
