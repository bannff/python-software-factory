"""Strict contracts for listing background subagent/loop-cycle Workflow runs."""
from __future__ import annotations

from pydantic import Field

from .discovery import StrictDTO


class ListBackgroundRunsInput(StrictDTO):
    origin_thread_id: str | None = Field(default=None, min_length=1, max_length=256)
    active_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)


class BackgroundRunView(StrictDTO):
    run_id: str
    persona_id: str
    status: str
    kind: str
    origin_thread_id: str
    started_at: str


class ListBackgroundRunsOutput(StrictDTO):
    runs: list[BackgroundRunView]


__all__ = ["ListBackgroundRunsInput", "BackgroundRunView", "ListBackgroundRunsOutput"]
