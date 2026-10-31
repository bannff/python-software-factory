"""Shared helpers for the AG-UI bridge plugins (bd:python-factory-ntyz7).

Extracted from ``ag_ui_bridge.py`` so both ``AGUIBridgePlugin`` (parent
chat agent) and ``SubAgentToolBridgePlugin`` (spawned specialist) can
reuse the same payload normalisation and thread-safe push logic without
duplication.

In-brick import (same ``plugins/`` directory) — NOT a cross-brick
violation per the architecture tenets.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def normalize_payload(result: Any) -> tuple[Any, bool]:
    """Extract a JSON-friendly payload + error flag from a Strands result.

    Strands wraps non-({status,content}) dict tool returns via
    ``json.dumps(result)`` into a ``{"text": <json>}`` content block
    (``strands/tools/decorator.py:_wrap_tool_result``). We unwrap such
    blocks here so downstream renderers see the original data structure
    rather than a JSON-encoded string. Plain text remains untouched;
    numeric/boolean/null literals also remain strings (we only unwrap
    dict/list shapes — the cases where the SDK round-tripped a Python
    data structure). bd:python-factory-qev3 + memory ``fda47a44``.
    """
    if result is None:
        return None, False
    # Strands ``ToolResult`` is a TypedDict:
    # {"content": [...], "status": ..., "toolUseId": ...}
    if isinstance(result, dict) and "content" in result:
        status = str(result.get("status", "success"))
        is_error = status == "error"
        content = result.get("content", [])
        # Prefer text/json when available; fall back to the raw content list.
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if "json" in block:
                    return block["json"], is_error
                if "text" in block:
                    text = block["text"]
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, (dict, list)):
                                return parsed, is_error
                        except (json.JSONDecodeError, ValueError):
                            pass
                    return text, is_error
        return content, is_error
    if isinstance(result, Exception):
        return str(result), True
    return result, False


def push_threadsafe(queue: Any, loop: Any, event: Any) -> None:
    """Push ``event`` onto ``queue`` without reordering same-loop events.

    Hook callbacks normally execute on the queue's running event loop, where
    direct ``put_nowait`` preserves their order relative to terminal stream
    events. A foreign thread uses ``call_soon_threadsafe`` as a fallback.
    Late events after loop shutdown remain harmless no-ops.
    """
    if queue is None or loop is None:
        return
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    try:
        if current_loop is loop:
            queue.put_nowait(event)
        else:
            loop.call_soon_threadsafe(queue.put_nowait, event)
    except RuntimeError:
        # Loop closed mid-flight — invocation has unwound.
        pass
    except Exception:  # noqa: BLE001 — defence in depth
        logger.debug("push_threadsafe failed", exc_info=True)
