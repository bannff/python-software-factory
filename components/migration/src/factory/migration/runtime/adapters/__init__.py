"""Migration runtime storage adapters."""
from __future__ import annotations

from .receipt_store_sql import SqlReceiptStore

__all__ = ["SqlReceiptStore"]
