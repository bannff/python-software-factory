"""Durable session transcript -> AG-UI row projection.

The session_history MCP consumer (``factory.agent.mcp.session_history``)
validates each row against ``HistoryMessage`` (extra=forbid): exactly
``id``/``role``/``content``/``tool_calls``/``tool_call_id``. This mirrors
``langchain_history.messages_to_agui`` against strands ``SessionMessage``
rows instead of LangChain message objects.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .strands_session_repository import SqlSessionRepository

_ROLE = {"user": "user", "assistant": "assistant", "system": "system", "tool": "tool"}


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = next((part.get("text") for part in content
                     if isinstance(part, dict) and part.get("type") == "text"), None)
        if isinstance(text, str):
            return text
    return json.dumps(content, separators=(",", ":"), default=str)


def session_messages_to_agui(
    repo: "SqlSessionRepository", session_id: str,
) -> list[dict[str, Any]]:
    """Project the session's durable messages into AG-UI rows.

    Session keys are ``{agent_id}-{thread_id}`` and each session stores
    one agent row keyed by the persona id — its transcript IS the thread.
    """
    agent_ids = repo.agent_ids_for(session_id)
    if not agent_ids:
        return []
    projected: list[dict[str, Any]] = []
    for msg in repo.list_messages(session_id, agent_ids[0]):
        message = msg.to_message()
        role = _ROLE.get(str(message.get("role", "")))
        if role is None:
            continue
        item: dict[str, Any] = {
            "id": str(msg.message_id), "role": role,
            "content": _text(message.get("content")), "tool_calls": [],
            "tool_call_id": None,
        }
        if role == "assistant":
            item["tool_calls"] = [
                {
                    "id": str(call.get("toolUseId", "")), "type": "function",
                    "function": {
                        "name": str(call.get("name", "")),
                        "arguments": json.dumps(
                            call.get("input", {}), separators=(",", ":"),
                        ),
                    },
                }
                for call in message.get("toolUses", ())
                if isinstance(call, dict)
            ]
        elif role == "tool":
            item["tool_call_id"] = str(message.get("toolUseId", ""))
        projected.append(item)
    return projected


__all__ = ["session_messages_to_agui"]
