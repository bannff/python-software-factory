"""Strict contracts for cancelling a running chat turn from outside it."""
from __future__ import annotations

from pydantic import Field

from .discovery import StrictDTO


class CancelTurnInput(StrictDTO):
    thread_id: str = Field(min_length=1, max_length=256)


class CancelTurnOutput(StrictDTO):
    thread_id: str
    cancelled: bool


__all__ = ["CancelTurnInput", "CancelTurnOutput"]
