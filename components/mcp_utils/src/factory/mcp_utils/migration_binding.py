"""Closed binding for one Migration-to-target import write."""
from __future__ import annotations

import re
from dataclasses import dataclass

_SHA256 = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
_RECORD = re.compile(r"[0-9a-f]{64}")


def _text(name: str, value: str, limit: int = 256) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be a bounded non-empty string")


def _digest(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class MigrationImportBinding:
    tenant_id: str
    owner_id: str
    source_adapter: str
    source_fingerprint: str
    plan_digest: str
    kind: str
    source_record_id: str
    target_digest: str

    def __post_init__(self) -> None:
        _text("tenant_id", self.tenant_id)
        _text("owner_id", self.owner_id)
        if _NAME.fullmatch(self.source_adapter) is None:
            raise ValueError("source_adapter is invalid")
        if _NAME.fullmatch(self.kind) is None:
            raise ValueError("kind is invalid")
        if _RECORD.fullmatch(self.source_record_id) is None:
            raise ValueError("source_record_id is invalid")
        for name in ("source_fingerprint", "plan_digest", "target_digest"):
            _digest(name, getattr(self, name))


__all__ = ["MigrationImportBinding"]
