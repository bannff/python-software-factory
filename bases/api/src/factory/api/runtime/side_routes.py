"""HTTP routes for the side-chat scratch conversation (feature-map row 19).

Exposes the `side/{open,turn,close}` contract over a
:class:`factory.mcp_utils.runtime.side_chat_service.SideChatService`. The
service is supplied by an injected ``service_provider`` callable, so this
module carries no gateway/LLM knowledge and is unit-testable with a fake
service via a throwaway FastAPI app.

The gateway wiring that constructs the real service (chat-graph LLM planner +
`build_category_lookup` + aggregator dispatch) and calls
``register_side_routes(app, provider)`` at startup — plus the live-proof pass —
is the deferred transport seam this module is built against.
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

_SideChatService = Any  # structural: .open(slot)/.turn(slot, query)/.close(slot)


class SideTurnBody(BaseModel):
    query: str


def _serialize_turn(turn: Any) -> dict[str, str]:
    return {"role": turn.role, "text": turn.text}


def register_side_routes(
    app: Any,
    service_provider: Callable[[], _SideChatService],
) -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/api/chat/slots/{slot}/side/open")
    def open_side(slot: str) -> dict[str, Any]:
        result = service_provider().open(slot)
        return {"slot": result.slot, "turns": [_serialize_turn(t) for t in result.turns]}

    @router.post("/api/chat/slots/{slot}/side/turn")
    def side_turn(slot: str, body: SideTurnBody) -> dict[str, Any]:
        result = service_provider().turn(slot, body.query)
        return {
            "turns": [_serialize_turn(t) for t in result.turns],
            "refused": result.refused,
        }

    @router.post("/api/chat/slots/{slot}/side/close")
    def close_side(slot: str) -> dict[str, bool]:
        return {"closed": service_provider().close(slot)}

    app.include_router(router)


__all__ = ["register_side_routes"]
