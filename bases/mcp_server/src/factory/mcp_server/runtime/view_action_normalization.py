"""Rewrite legacy ``props.tool`` to ``props.action`` on ``*_get_views`` results.

bd:python-factory-736 (mechanical consolidation track). This is a
RELOCATION, not new behavior: the retired REST bridge
(``bases/api/.../bridge.py::execute_tool``) used to call
``factory.ui.interface.normalize_view_actions`` on every ``*_get_views``
result on its way back to the frontend (bd:3jcls.3 — the ActionRef
ingestion hook). Real MCP's ``call_brick_tool`` is now the ONE path every
caller (browser via ``tools/call``, in-process ``agg.invoke_tool``, chat)
reaches a brick's ``_get_views`` tool through, so the normalization moves
here rather than getting silently dropped when the bridge route is removed.

Scope is unchanged from the original: only tool names ending in
``_get_views``; only rewrites the SUCCESS raw value; any failure in the
normalizer itself is logged and swallowed — the original, un-normalized
payload survives rather than blanking a working tab.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_VIEWS_SUFFIX = "_get_views"


def _brick_of_view_tool(tool_name: str) -> str | None:
    if not tool_name.endswith(_VIEWS_SUFFIX):
        return None
    from factory.ui.interface import brick_of_view_tool
    return brick_of_view_tool(tool_name)


def normalize_views_envelope(
    brick_name: str, resolved_name: str, envelope: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a successful ``dispatch_tool`` envelope in place-ish.

    ``envelope`` is the ``{"ok": True, "result": {"kind": "tool", "content":
    [...], "structured_content": ..., "meta": ...}}`` shape ``dispatch_tool``
    builds. Non-``_get_views`` tools and any failure pass through untouched.
    """
    if not resolved_name.endswith(_VIEWS_SUFFIX) or not envelope.get("ok"):
        return envelope
    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("kind") != "tool":
        return envelope

    raw = _extract_raw_value(result)
    if not isinstance(raw, list):
        return envelope

    try:
        from factory.ui.interface import build_tool_resolver, normalize_view_actions

        normalized = normalize_view_actions(
            raw,
            brick_hint=_brick_of_view_tool(resolved_name) or brick_name,
            resolver=build_tool_resolver(),
        )
    except Exception as exc:  # noqa: BLE001 — never blank a working tab
        logger.warning("View action normalization failed for %s: %s", resolved_name, exc)
        return envelope
    if normalized is raw:
        return envelope

    return {
        **envelope,
        "result": _repack_raw_value(result, normalized),
    }


def _extract_raw_value(result: dict[str, Any]) -> Any:
    """Mirror ``tool_dispatch._raw_tool_value`` for the ``list`` case only."""
    structured = result.get("structured_content")
    if structured is not None:
        meta = result.get("meta") or {}
        if meta.get("fastmcp", {}).get("wrap_result") and set(structured) == {"result"}:
            return structured["result"]
        return structured
    content = result.get("content") or []
    if len(content) == 1 and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except (ValueError, TypeError):
            return None
    return None


def _repack_raw_value(result: dict[str, Any], value: list[Any]) -> dict[str, Any]:
    """Write the normalized value back into every slot a client might read.

    ``content`` and ``structured_content`` are kept in sync: the browser
    client (and most SDK clients) prefer ``structuredContent`` when present,
    but anything reading the ``content`` text block must see the same
    normalized value rather than a stale pre-normalization copy.
    """
    out = dict(result)
    structured = result.get("structured_content")
    if structured is not None:
        meta = result.get("meta") or {}
        if meta.get("fastmcp", {}).get("wrap_result") and set(structured) == {"result"}:
            out["structured_content"] = {"result": value}
        else:
            out["structured_content"] = value
    content = result.get("content") or []
    if len(content) == 1 and content[0].get("type") == "text":
        out["content"] = [{**content[0], "text": json.dumps(value)}]
    return out
