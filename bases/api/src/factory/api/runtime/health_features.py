"""Product features whose availability depends on optional installs (#388).

A feature that is advertised but cannot run is worse than a missing one, so
``/api/health`` states it. Sources are the owning bricks' own capability tools.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable


def _unwrap(result: Any) -> dict[str, Any]:
    while isinstance(result, dict) and isinstance(result.get("data"), dict):
        result = result["data"]
    return result if isinstance(result, dict) else {}


async def feature_availability(
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]], side_chat: dict[str, Any],
) -> dict[str, Any]:
    caps = _unwrap(await call_tool("ml_get_capabilities", {}))
    ml: dict[str, Any] = {"available": caps.get("training_available")}
    if caps.get("training_available") is False:
        ml["missing"] = caps.get("training_missing", [])
        ml["fix"] = caps.get("training_install_hint", "")
    return {
        "ml_training": ml,
        "side_chat_tools": {
            "available": side_chat.get("status") == "ready",
            **({"reason": side_chat["reason"]} if side_chat.get("reason") else {}),
        },
    }


__all__ = ["feature_availability"]
