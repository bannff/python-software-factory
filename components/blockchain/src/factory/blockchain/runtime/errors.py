"""Ledger refusals with a stable public ``code`` (the tools surface it as the error)."""
from __future__ import annotations


class LedgerError(ValueError):
    """A ValueError so existing ``except ValueError`` callers keep working."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
