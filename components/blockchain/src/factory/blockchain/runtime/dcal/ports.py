"""Independent ports for the isolated DCAL provenance profile.

These protocols intentionally do not inherit from the economy ``LedgerPort``.
"""
from __future__ import annotations

from typing import Protocol

from factory.blockchain.mcp.contracts.dcal.models import (
    AnchorDecision,
    AppendDecision,
    DcalLogRecord,
    DurableIdentity,
    DcalScope,
    RecordPage,
    SourceSnapshot,
)


class DcalLedgerPort(Protocol):
    """Durable append-only storage contract for dcal/v1 records."""

    def append_or_match(
        self,
        *,
        identity: DurableIdentity,
        request_digest: str,
        record: DcalLogRecord,
    ) -> AppendDecision:
        """Append once or return the prior decision for an equal request."""
        ...

    def get_record(self, *, scope: DcalScope, record_id: str) -> DcalLogRecord | None:
        """Read one record only within its bound DCAL scope."""
        ...

    def page_snapshot(
        self,
        *,
        snapshot: SourceSnapshot,
        cursor: str | None,
    ) -> RecordPage:
        """Read an immutable, bounded source snapshot page."""
        ...


ProvenanceLedgerPort = DcalLedgerPort


class DcalAnchorPort(Protocol):
    """Future one-way anchor seam for finalized checkpoint digests only."""

    def anchor_finalized_checkpoint(self, *, checkpoint_digest: str) -> AnchorDecision:
        """Return bounded evidence only; anchoring cannot alter ledger finality."""
        ...


__all__ = ["DcalAnchorPort", "DcalLedgerPort", "ProvenanceLedgerPort"]
