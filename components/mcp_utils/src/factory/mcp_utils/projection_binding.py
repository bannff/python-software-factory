"""Closed binding for one trusted relationship-projection operation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ProjectionBinding:
    tenant_id: str
    owner_id: str
    event_type: str
    subject_id: str
    revision: int
    payload_digest: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "event_type", "subject_id"):
            value: Any = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must be a bounded non-empty string")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) \
                or self.revision < 0:
            raise ValueError("revision must be a non-negative integer")
        if not isinstance(self.payload_digest, str) \
                or _SHA256.fullmatch(self.payload_digest) is None:
            raise ValueError("payload_digest must be a lowercase SHA-256 digest")


__all__ = ["ProjectionBinding"]
