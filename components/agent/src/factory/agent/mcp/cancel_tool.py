"""Cancel a running chat turn from outside the session (row 61)."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, ok, operational

from .contracts.cancel_turn import CancelTurnInput, CancelTurnOutput

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    @mcp.tool(name="agent.cancel_turn")
    @operational(input_model=CancelTurnInput, output_model=CancelTurnOutput, idempotent=False)
    async def agent_cancel_turn(thread_id: str) -> ToolResult[CancelTurnOutput]:
        """Cooperatively cancel the currently streaming/running turn for a thread."""
        from ..runtime.chat import cancel_chat_turn
        cancelled = await cancel_chat_turn(thread_id)
        return ok(CancelTurnOutput(thread_id=thread_id, cancelled=cancelled))


__all__ = ["register"]
