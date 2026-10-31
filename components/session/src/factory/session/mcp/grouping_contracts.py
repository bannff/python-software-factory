"""Grouping/generation input DTOs split out of ``lifecycle_contracts.py``
to keep that module under the 200 LOC ceiling. Imports ``SessionRefInput``
from it (never the reverse), so there is no import cycle.
"""
from __future__ import annotations

from pydantic import Field

from .lifecycle_contracts import SessionRefInput


class GenerateSummaryInput(SessionRefInput):
    """Row 18 (feature-map) — the FE supplies a transcript excerpt to
    summarize (larger cap than the title excerpt: a rolling summary reads
    more of the conversation)."""
    excerpt: str = Field(min_length=1, max_length=24_000)
    expected_revision: int = Field(ge=1)


class SetFolderInput(SessionRefInput):
    """Row 6 (feature-map) — file a session under a folder name
    ("" = unfiled). Single value, no control chars."""
    folder: str = Field(default="", max_length=64, pattern=r"^[^\x00-\x1f\x7f]*$")
    expected_revision: int = Field(ge=1)


__all__ = ["GenerateSummaryInput", "SetFolderInput"]
