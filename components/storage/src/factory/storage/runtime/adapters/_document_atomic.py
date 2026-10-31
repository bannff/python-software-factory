"""Shared atomic create-or-match implementation for lock-backed document stores."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from factory.storage.runtime.ports import DocumentWriteResult


class LockingCreateOrMatchMixin:
    """Provide immutable retries when an adapter serializes access with ``_lock``."""

    def create_or_match(
        self, collection: str, doc_id: str, data: dict[str, Any], content_hash: str,
    ) -> DocumentWriteResult:
        lock = getattr(self, "_lock", nullcontext())
        with lock:
            existing = self.get(collection, doc_id)
            if existing is None:
                return DocumentWriteResult("created", self.insert(collection, data, doc_id))
            existing_hash = str(existing.data.get("content_hash", ""))
            status = "matched" if existing_hash and existing_hash == content_hash else "conflict"
            return DocumentWriteResult(status, existing, existing_hash)
