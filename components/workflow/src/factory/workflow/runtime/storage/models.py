"""Storage models and utilities for workflow sqlite backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def iso_format(dt: datetime) -> str:
    """Convert datetime to ISO format string in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_datetime(value: str) -> datetime:
    """Parse ISO format string to datetime."""
    return datetime.fromisoformat(value)


@dataclass
class PaginationCursor:
    """Cursor for paginated queries."""
    updated_at: str
    run_id: str

    def encode(self) -> str:
        return f"{self.updated_at}|{self.run_id}"

    @classmethod
    def decode(cls, value: str) -> "PaginationCursor":
        parts = value.split("|", 1)
        if len(parts) != 2:
            raise ValueError("Invalid cursor")
        return cls(updated_at=parts[0], run_id=parts[1])
