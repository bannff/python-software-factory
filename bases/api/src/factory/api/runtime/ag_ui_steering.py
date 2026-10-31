"""Concurrent AG-UI message offer without owning steering state."""
from __future__ import annotations

from typing import Any

import logging

logger = logging.getLogger(__name__)


def delivery_event(value: Any) -> dict[str, Any]:
    """Project a persisted delivery without message content or principal data."""
    return {
        "type": "CUSTOM", "name": "session.steer",
        "value": {
            "session_id": value.session_id,
            "delivery_id": value.delivery_id,
            "send_id": value.send_id,
            "state": "written",
            "revision": value.revision,
        },
    }


async def offer_busy_steer(
    thread_id: str, messages: list[dict[str, Any]], user_message: str,
    agent_id: str | None, identity: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Persist guidance only when its verified Agent thread is active."""
    if identity is None:
        return None
    from .ag_ui_helpers import extract_user_message_id
    send_id = extract_user_message_id(messages)
    if send_id is None:
        return None
    from factory.agent.interface import get_chat_agent

    # A steer that cannot be persisted must not 500 the whole chat run (#86):
    # binding/session errors at this seam degrade to "no steer" and the
    # message is processed as a fresh turn instead.
    try:
        delivery = await get_chat_agent().steer(
            thread_id, send_id, user_message, agent_id=agent_id,
            tenant_id=identity["tenant_id"], owner_id=identity["principal_id"],
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "busy steer offer failed thread_id=%s send_id=%s", thread_id, send_id,
        )
        return None
    return delivery_event(delivery) if delivery is not None else None


__all__ = ["delivery_event", "offer_busy_steer"]
