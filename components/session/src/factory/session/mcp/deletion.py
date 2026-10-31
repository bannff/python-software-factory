"""Operational typed MCP tools for session deletion (row 8, feature-map).

Split out of ``operational.py`` to keep that file under the 200 LOC ceiling
— deletion (single + bulk) is a genuinely separate concern from the rest of
session lifecycle mutation (create/rename/rebind/archive).
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import (
    ClearArchivedOutput, DeleteOutput, EnvelopeOnlyInput, RevisionSessionInput,
)
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=RevisionSessionInput, output_model=DeleteOutput)
    def session_delete(
        session_id: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[DeleteOutput]:
        """Row 8 — "Older sessions" per-session delete, the upstream
        control this view was missing. Hard delete, distinct from
        archive/reopen; revision-fenced the same way."""
        runtime = get_runtime().lifecycle
        return result(lambda: DeleteOutput(session_id=session_id, deleted=runtime.delete(
            *identity(runtime, envelope), session_id, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=EnvelopeOnlyInput, output_model=ClearArchivedOutput,
                 idempotent=False)
    def session_clear_archived(
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[ClearArchivedOutput]:
        """Row 8 bulk "Delete all" — upstream's ``DELETE /api/sessions``.
        Clears every archived session for the caller; no revision fencing,
        matching upstream's own blanket-delete shape (not a targeted CAS
        mutation)."""
        runtime = get_runtime().lifecycle
        return result(lambda: ClearArchivedOutput(
            deleted_count=runtime.delete_archived(*identity(runtime, envelope)),
        ))


__all__ = ["register"]
