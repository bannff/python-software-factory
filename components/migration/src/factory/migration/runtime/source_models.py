"""Strict immutable models for KiroCrew source discovery and preview.

Slice-1 source boundary (see ``m7-product-integration-design.md``): typed,
frozen records for the trusted snapshot, per-kind parse reports, bounded
diagnostics, and credential/PII-redacted preview samples. No model ever
carries a secret, an embedding, a raw runtime field, or unbounded content.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Caps apply to the enumerated allowlist only (design "KiroCrew source adapter").
MAX_FILES = 500
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DB_BYTES = 64 * 1024 * 1024
MAX_TEXT_CHARS = 1_048_576
MAX_SAMPLE_CHARS = 240
MAX_RECORDS_PER_KIND = 50_000
MAX_DIAGNOSTICS = 200
_HEX64 = r"^[0-9a-f]{64}$"

SUPPORTED_MEMORY_VERSIONS: frozenset[int] = frozenset({1, 2, 3})
SUPPORTED_CRON_VERSIONS: frozenset[int] = frozenset({1, 2})


class SourceKind(StrEnum):
    MEMORY = "memory"
    LESSONS = "lessons"
    SCHEDULES = "schedules"
    MARKDOWN = "markdown"


class ReasonCode(StrEnum):
    """Bounded, content-free diagnostic codes (no raw source text ever)."""

    SYMLINK = "symlink_rejected"
    HARDLINK = "hardlink_rejected"
    NOT_REGULAR = "not_regular_file"
    OWNER_MISMATCH = "owner_mismatch"
    SIZE_EXCEEDED = "size_exceeded"
    COUNT_EXCEEDED = "count_exceeded"
    MUTATED = "mutated_during_read"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    CORRUPT_DB = "corrupt_db"
    INTEGRITY_FAILED = "integrity_failed"
    UNKNOWN_VERSION = "unknown_version"
    MALFORMED = "malformed_record"
    DELETED = "deleted_row"
    SECRET_FIELD = "secret_field_excluded"
    UNSUPPORTED = "unsupported_kind"
    DUPLICATE = "duplicate"
    EMPTY = "empty"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def identity_of(namespace: str, key: str) -> str:
    """Deterministic 64-hex source-record identity for idempotent import."""
    return sha256_hex(f"{namespace}\x00{key}")


# Credential/secret shapes scrubbed from preview samples (defense in depth;
# import records already exclude secret files/fields at parse time).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*KEY-----", re.S),
    re.compile(r"(?i)\b(?:bearer|token|secret|password|passwd|api[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
)


def redact(text: str, limit: int = MAX_SAMPLE_CHARS) -> str:
    """Strip credential shapes and bound length for a preview sample."""
    scrubbed = text
    for pat in _SECRET_PATTERNS:
        scrubbed = pat.sub("[redacted]", scrubbed)
    scrubbed = " ".join(scrubbed.split())
    if len(scrubbed) > limit:
        scrubbed = scrubbed[:limit] + "…"
    return scrubbed


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class StagedFile(_Frozen):
    rel_path: str = Field(min_length=1, max_length=512)
    size: int = Field(ge=0, le=MAX_DB_BYTES)
    sha256: str = Field(pattern=_HEX64)


class SnapshotManifest(_Frozen):
    files: tuple[StagedFile, ...] = Field(default=(), max_length=MAX_FILES)
    digest: str = Field(pattern=_HEX64)
    created_at: datetime


class Diagnostic(_Frozen):
    kind: SourceKind
    reason: ReasonCode
    identity: str = Field(default="", max_length=64)
    detail: str = Field(default="", max_length=200)


class SafeMemory(_Frozen):
    kind: Literal["semantic", "episodic"]
    identity: str = Field(pattern=_HEX64)
    key: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    tags: tuple[str, ...] = Field(default=(), max_length=64)


class SafeLesson(_Frozen):
    identity: str = Field(pattern=_HEX64)
    rule: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    category: str = Field(default="", max_length=64)
    negative: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    repo_scope: str = Field(default="", max_length=256)
    origin: Literal["jsonl", "legacy_semantic"]


class SafeSchedule(_Frozen):
    identity: str = Field(pattern=_HEX64)
    name: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=MAX_TEXT_CHARS)
    schedule_kind: Literal["every", "at", "cron"]
    every_secs: int | None = Field(default=None, ge=60)
    at_ts: float | None = None
    cron_expr: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="", max_length=64)
    skip_dates: tuple[str, ...] = Field(default=(), max_length=366)
    strict_schedule: bool = False
    approval_mode: Literal["", "auto"] = ""
    agent_id: str = Field(default="", max_length=128)
    model: str = Field(default="", max_length=128)
    paused: Literal[True] = True  # imported schedules are always paused


class SafeMarkdown(_Frozen):
    identity: str = Field(pattern=_HEX64)
    doc: Literal["preferences", "projects", "history"]
    rel_path: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class PreviewSample(_Frozen):
    kind: SourceKind
    identity: str = Field(pattern=_HEX64)
    sample: str = Field(default="", max_length=MAX_SAMPLE_CHARS + 1)


class KindReport(_Frozen):
    kind: SourceKind
    found: int = Field(default=0, ge=0)
    eligible: int = Field(default=0, ge=0)
    excluded: int = Field(default=0, ge=0)
    digest: str = Field(pattern=_HEX64)
    diagnostics: tuple[Diagnostic, ...] = Field(default=(), max_length=MAX_DIAGNOSTICS)


__all__ = [
    "MAX_FILES", "MAX_FILE_BYTES", "MAX_DB_BYTES", "MAX_TEXT_CHARS",
    "MAX_SAMPLE_CHARS", "MAX_RECORDS_PER_KIND", "MAX_DIAGNOSTICS",
    "SUPPORTED_MEMORY_VERSIONS",
    "SUPPORTED_CRON_VERSIONS", "SourceKind", "ReasonCode", "Diagnostic",
    "StagedFile", "SnapshotManifest", "SafeMemory", "SafeLesson",
    "SafeSchedule", "SafeMarkdown", "PreviewSample", "KindReport",
    "identity_of", "redact", "sha256_hex",
]
