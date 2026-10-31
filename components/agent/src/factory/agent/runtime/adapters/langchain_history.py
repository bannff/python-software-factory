"""Lossless LangChain-to-AG-UI checkpoint message projection."""
from __future__ import annotations

import json
from typing import Any


def messages_to_agui(messages: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for message in messages:
        role = {
            "human": "user", "ai": "assistant",
            "system": "system", "tool": "tool",
        }.get(getattr(message, "type", ""))
        if role is None:
            continue
        item: dict[str, Any] = {
            "id": str(message.id), "role": role,
            "content": _content(message.content), "tool_calls": [],
            "tool_call_id": None,
        }
        if role == "assistant":
            item["tool_calls"] = [{
                "id": str(call["id"]), "type": "function",
                "function": {
                    "name": str(call["name"]),
                    "arguments": json.dumps(call.get("args", {}), separators=(",", ":")),
                },
            } for call in getattr(message, "tool_calls", ())]
        elif role == "tool":
            item["tool_call_id"] = str(message.tool_call_id)
        projected.append(item)
    return projected


def _content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = next((part.get("text") for part in content
                     if isinstance(part, dict) and part.get("type") == "text"), None)
        if isinstance(text, str):
            return text
    return json.dumps(content, separators=(",", ":"), default=str)


__all__ = ["messages_to_agui"]
