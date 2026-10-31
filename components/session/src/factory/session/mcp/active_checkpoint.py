"""Operational typed MCP tool for pinning a session's active checkpoint
branch (row 16, feature-map — Regenerate/variants substrate).

Split into its own module for the same reason ``fork.py``/``session_stop.py``
are split from ``operational.py`` — a genuinely separate lifecycle-mutation
concern, kept out of the already-busy ``operational.py`` to respect the
200 LOC ceiling.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import SessionOutput, SetActiveCheckpointInput
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SetActiveCheckpointInput, output_model=SessionOutput)
    def session_set_active_checkpoint(
        session_id: str, checkpoint_id: str | None, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        """Row 16 — pin which checkpoint branch is "current" for this
        thread after a regenerate/variant switch. ``checkpoint_id=None``
        clears the pointer (an ordinary turn resumes from LangGraph's
        own latest checkpoint again, exactly as it did before this row
        existed). See ``SessionRecord.active_checkpoint_id`` for why this
        durable pointer is required rather than trusting the checkpoint
        store's own "latest" ordering once a sibling branch exists."""
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_active_checkpoint(
            *identity(runtime, envelope), session_id, checkpoint_id, expected_revision,
        )))


__all__ = ["register"]
