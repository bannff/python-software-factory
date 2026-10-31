"""Strict, immutable, secret-free bundle record models.

No model ever carries a secret, an embedding, a raw runtime field, or
unbounded content. Deliberately does NOT import ``factory.migration`` — a
brick-local ``identity_of``/``sha256_hex`` twin (same shape as ``kb``'s
``LocalKBEmbedder`` twin of memory's embedder) avoids a cross-brick runtime
import while keeping identities computed identically on both sides.
"""
from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT_CHARS = 1_048_576
_HEX64 = r"^[0-9a-f]{64}$"

BUNDLE_VERSION = 1
BUNDLE_ADAPTER = "companion-x-v1"

EXPORT_KINDS: tuple[str, ...] = ("memory", "kb", "lessons", "schedules", "preferences")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def identity_of(namespace: str, key: str) -> str:
    """Deterministic 64-hex record identity — matches migration's own
    ``identity_of`` byte-for-byte so a companion-x-v1 bundle's records land
    on the exact same ``source_record_id`` migration would compute, making
    re-import idempotent through the existing receipt store with no new
    logic on the import side."""
    return sha256_hex(f"{namespace}\x00{key}")


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SafeMemoryRecord(_Frozen):
    kind: Literal["semantic", "episodic"]
    identity: str = Field(pattern=_HEX64)
    key: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    tags: tuple[str, ...] = Field(default=(), max_length=64)


class SafeKbRecord(_Frozen):
    identity: str = Field(pattern=_HEX64)
    source: str = Field(default="", max_length=512)
    content: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class SafeLessonRecord(_Frozen):
    identity: str = Field(pattern=_HEX64)
    rule: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    category: str = Field(default="", max_length=64)
    negative: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    repo_scope: str = Field(default="", max_length=256)


class SafeScheduleRecord(_Frozen):
    identity: str = Field(pattern=_HEX64)
    name: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=MAX_TEXT_CHARS)
    schedule_kind: Literal["every", "at", "cron"]
    every_secs: int | None = Field(default=None, ge=60)
    at_ts: float | None = None
    cron_expr: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="", max_length=64)
    agent_id: str = Field(default="", max_length=128)
    model: str = Field(default="", max_length=128)
    paused: Literal[True] = True  # exported schedules always resume paused


class SafePreferencesRecord(_Frozen):
    identity: str = Field(pattern=_HEX64)
    theme: str = Field(default="system", max_length=16)
    density: str = Field(default="comfortable", max_length=16)
    language: str = Field(default="en", max_length=35)
    terminal_font_size: int = Field(default=11, ge=10, le=18)


_KIND_MODELS: dict[str, type[_Frozen]] = {
    "memory": SafeMemoryRecord, "kb": SafeKbRecord, "lessons": SafeLessonRecord,
    "schedules": SafeScheduleRecord, "preferences": SafePreferencesRecord,
}


def model_for_kind(kind: str) -> type[_Frozen]:
    return _KIND_MODELS[kind]


__all__ = [
    "BUNDLE_ADAPTER", "BUNDLE_VERSION", "EXPORT_KINDS", "SafeKbRecord",
    "SafeLessonRecord", "SafeMemoryRecord", "SafePreferencesRecord",
    "SafeScheduleRecord", "identity_of", "model_for_kind", "sha256_hex",
]
