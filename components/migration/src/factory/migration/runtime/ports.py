"""Migration durable-receipt port.

A small Protocol over a relational store: it binds immutable import plans,
records terminal per-record receipts with source-identity idempotency and
target-digest conflict detection, lists/counts receipts for reporting, and
persists a per-kind resume cursor. It is receipt *state* only — never a
parallel Workflow progression engine.
"""
from __future__ import annotations

from typing import Protocol

from .plan_records import PlanRecord, PlanRecordCommit
from .receipt_models import (
    ImportReceipt, PageCursor, PlanCommit, PlanIdentity, ReceiptCommit,
)
from .source_models import SourceKind


class ReceiptStore(Protocol):
    """Port: durable, owner-scoped migration receipts over public Storage SQL."""

    def initialize(self) -> None:
        """Create the backing tables if absent (idempotent)."""
        ...

    def bind_plan(self, plan: PlanIdentity) -> PlanCommit:
        """Immutably bind a plan; replay/conflict on an existing fingerprint."""
        ...

    def get_plan(
        self, tenant_id: str, owner_id: str, adapter: str,
        source_fingerprint: str, plan_digest: str,
    ) -> PlanIdentity | None:
        """Return one exact owner-scoped immutable plan, or None."""
        ...

    def find_plan(
        self, tenant_id: str, owner_id: str, adapter: str, plan_digest: str,
    ) -> PlanIdentity | None:
        """Return one owner-scoped plan by public digest, failing on ambiguity."""
        ...

    def save_plan_records(
        self, plan: PlanIdentity, records: tuple[PlanRecord, ...],
    ) -> tuple[PlanRecordCommit, ...]:
        """Insert immutable approved plan records; replay or conflict exactly."""
        ...

    def list_plan_records(
        self, tenant_id: str, owner_id: str, adapter: str,
        source_fingerprint: str, plan_digest: str, kind: SourceKind,
        offset: int, limit: int,
    ) -> list[PlanRecord]:
        """Read one bounded, owner-scoped deterministic execution page."""
        ...

    def record_receipt(self, receipt: ImportReceipt) -> ReceiptCommit:
        """Commit a receipt after a terminal outcome; idempotent under the key."""
        ...

    def find_receipt(
        self, tenant_id: str, owner_id: str, adapter: str,
        source_fingerprint: str, kind: str, source_record_id: str,
    ) -> ImportReceipt | None:
        """Return the owner-scoped receipt for a source record, or None."""
        ...

    def list_receipts(
        self, tenant_id: str, owner_id: str, adapter: str,
        source_fingerprint: str, kind: str | None = None,
    ) -> list[ImportReceipt]:
        """Return owner-scoped receipts for a run, optionally filtered by kind."""
        ...

    def outcome_counts(
        self, tenant_id: str, owner_id: str, adapter: str, source_fingerprint: str,
    ) -> dict[str, int]:
        """Return per-outcome receipt counts for reporting."""
        ...

    def load_cursor(
        self, tenant_id: str, owner_id: str, adapter: str,
        source_fingerprint: str, plan_digest: str, kind: str,
    ) -> PageCursor | None:
        """Return the persisted resume cursor for a kind, or None."""
        ...

    def save_cursor(
        self, cursor: PageCursor, expected_revision: int | None = None,
    ) -> PageCursor:
        """CAS-save the resume cursor; None expects create, else revision fence."""
        ...


__all__ = ["ReceiptStore"]
