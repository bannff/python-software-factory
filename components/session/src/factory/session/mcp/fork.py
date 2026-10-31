"""Operational typed MCP tool for forking a session (row 14, feature-map).

Split into its own module for the same reason ``deletion.py`` is split
from ``operational.py`` — a genuinely separate lifecycle-mutation concern,
kept out of the already-busy ``operational.py`` to respect the 200 LOC
ceiling.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import SessionOutput, SessionRefInput
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SessionRefInput, output_model=SessionOutput,
                 idempotent=False)
    def session_fork(
        session_id: str, envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        """Row 14 — branch a new session from an existing transcript.

        Upstream: "an incognito or temporary session forks into a child
        of the same memory mode" — the child session carries the exact
        same mode/crew/memory_scope/agent/model/project as its source; a
        fresh session+thread identity is the only new thing. The caller
        (the agent-brick chat adapter) is responsible for copying the
        actual transcript (LangGraph checkpoint history) onto the new
        thread once this returns — this tool only creates the durable
        session ROW, matching the same division of labor
        ``session_ensure_thread`` already has with the checkpoint store.
        """
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.fork(
            *identity(runtime, envelope), session_id,
        )))


__all__ = ["register"]
