"""Operational typed MCP tool for filing a session under a folder
(row 6, feature-map).

Its own module (mirroring ``tagging.py``/``active_checkpoint.py``) — a
distinct grouping-mutation concern kept out of ``operational.py``.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .grouping_contracts import SetFolderInput
from .lifecycle_contracts import SessionOutput
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SetFolderInput, output_model=SessionOutput)
    def session_set_folder(
        session_id: str, folder: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        """Row 6 — file the session under ``folder`` ("" clears it back to
        unfiled), a single owner-typed grouping label applied through the
        SAME revision-fenced write every other mutation uses."""
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_folder(
            *identity(runtime, envelope), session_id, folder, expected_revision,
        )))


__all__ = ["register"]
