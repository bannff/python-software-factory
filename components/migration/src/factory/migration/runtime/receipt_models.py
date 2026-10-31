"""Strict frozen import-plan, receipt, and plan-scoped cursor models.

Receipts are owner-scoped and source-record idempotent: equal target material
replays, changed target material conflicts without overwrite.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Ambient authority — mirrors Session/Crew ``Identity`` so the owner-scoped
# stores agree on what a principal looks like. Never accepted from raw input.
Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")]

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")              # adapter, kind, reason
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:=+/-]{0,255}$")  # fingerprint, record id
_DIGEST_RE = re.compile(r"^[a-z0-9]+:[0-9a-f]{16,128}$")           # algo:hex material digest

# Known credential shapes the identifier alphabet could otherwise accept.
_CREDENTIALS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj_)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
)


def credential_clean(value: str) -> bool:
    """Reject values shaped like a known credential."""
    return not any(pattern.fullmatch(value) for pattern in _CREDENTIALS)


def _checked(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not pattern.fullmatch(value) or not credential_clean(value):
        raise ValueError(f"{label} is invalid")
    return value


class CursorConflictError(RuntimeError):
    """Optimistic-concurrency failure saving a page cursor."""


class ImportOutcome(str, Enum):
    """Terminal outcome of importing one source record. No pending state."""

    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"

    @property
    def is_settled(self) -> bool:
        """Settled outcomes are immutable; a FAILED receipt may be retried."""
        return self is not ImportOutcome.FAILED


class CommitStatus(str, Enum):
    """Result of an idempotent plan/receipt write."""

    COMMITTED = "committed"    # first write of this identity
    REPLAYED = "replayed"      # exact replay of a settled row (skip)
    SUPERSEDED = "superseded"  # a prior FAILED receipt was retried
    CONFLICT = "conflict"      # settled row exists with different material


class PlanIdentity(BaseModel):
    """Frozen immutable binding of a staged snapshot to a resolved plan."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: Identity
    owner_id: Identity
    adapter: str
    source_fingerprint: str
    plan_digest: str
    kinds: Annotated[tuple[str, ...], Field(max_length=32)] = ()

    @field_validator("adapter")
    @classmethod
    def _v_adapter(cls, v: str) -> str:
        return _checked(v, _NAME_RE, "PlanIdentity.adapter")

    @field_validator("source_fingerprint")
    @classmethod
    def _v_fp(cls, v: str) -> str:
        return _checked(v, _TOKEN_RE, "PlanIdentity.source_fingerprint")

    @field_validator("plan_digest")
    @classmethod
    def _v_digest(cls, v: str) -> str:
        return _checked(v, _DIGEST_RE, "PlanIdentity.plan_digest")

    @field_validator("kinds")
    @classmethod
    def _v_kinds(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for kind in v:
            _checked(kind, _NAME_RE, "PlanIdentity.kinds")
        return v


class ImportReceipt(BaseModel):
    """Frozen terminal receipt for importing a single source record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: Identity
    owner_id: Identity
    adapter: str
    source_fingerprint: str
    kind: str
    source_record_id: str
    target_digest: str
    outcome: ImportOutcome
    reason_code: str = ""
    revision: Annotated[int, Field(ge=1)] = 1

    @field_validator("adapter", "kind")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _checked(v, _NAME_RE, "ImportReceipt name field")

    @field_validator("source_fingerprint", "source_record_id")
    @classmethod
    def _v_token(cls, v: str) -> str:
        return _checked(v, _TOKEN_RE, "ImportReceipt token field")

    @field_validator("target_digest")
    @classmethod
    def _v_digest(cls, v: str) -> str:
        return _checked(v, _DIGEST_RE, "ImportReceipt.target_digest")

    @field_validator("reason_code")
    @classmethod
    def _v_reason(cls, v: str) -> str:
        if v and (not _NAME_RE.fullmatch(v) or not credential_clean(v)):
            raise ValueError("ImportReceipt.reason_code is invalid")
        return v


class ReceiptCommit(BaseModel):
    """Outcome of an idempotent ``record_receipt`` call."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: CommitStatus
    receipt: ImportReceipt


class PlanCommit(BaseModel):
    """Outcome of an idempotent ``bind_plan`` call."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: CommitStatus
    plan: PlanIdentity


class PageCursor(BaseModel):
    """Per-kind resume marker — receipt state only, not a progression engine."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: Identity
    owner_id: Identity
    adapter: str
    source_fingerprint: str
    plan_digest: str
    kind: str
    page_index: Annotated[int, Field(ge=0)]
    revision: Annotated[int, Field(ge=1)] = 1

    @field_validator("adapter", "kind")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _checked(v, _NAME_RE, "PageCursor name field")

    @field_validator("source_fingerprint")
    @classmethod
    def _v_fp(cls, v: str) -> str:
        return _checked(v, _TOKEN_RE, "PageCursor.source_fingerprint")

    @field_validator("plan_digest")
    @classmethod
    def _v_digest(cls, v: str) -> str:
        return _checked(v, _DIGEST_RE, "PageCursor.plan_digest")


__all__ = [
    "CommitStatus", "CursorConflictError", "Identity", "ImportOutcome",
    "ImportReceipt", "PageCursor", "PlanCommit", "PlanIdentity", "ReceiptCommit",
    "credential_clean",
]
