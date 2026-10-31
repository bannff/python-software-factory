"""Operational Session pinned-message mutation MCP tool (row 9, feature-map)."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import SessionOutput
from .lifecycle_support import identity, result
from .pinned_messages_contracts import SetPinnedMessagesInput


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SetPinnedMessagesInput, output_model=SessionOutput)
    def session_set_pinned_messages(
        session_id: str, pinned_message_ids: tuple[str, ...], expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_pinned_messages(
            *identity(runtime, envelope), session_id, pinned_message_ids, expected_revision,
        )))


__all__ = ["register"]
