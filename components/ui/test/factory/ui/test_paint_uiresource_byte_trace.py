"""Byte-trace canary — the native MCP-v2 ``ToolCatalog`` wraps
``ui_paint_uiresource`` result as ``TextContent`` carrying a
JSON-stringified ``ToolResult`` envelope (typed egress), not a raw MCP
``EmbeddedResource``.

bd:python-factory-v2dko under EPIC bd:python-factory-lo1g9. Verdict
``26d6cd24`` Q3 — this is the wire-shape gate that proves Flow A
end-to-end through Strands ``MCPClient`` (then through
``FactoryMCPClient`` for uri+mimeType preservation under bd-nmzlk).

The typed egress boundary always emits ``TextContent`` with the v1
envelope, so this canary pins that exact shape on the native transport.
"""

from __future__ import annotations

import json

import pytest

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.ui.mcp.paint_uiresource import register


def _catalog() -> ToolCatalog:
    mcp = ToolCatalog("test")
    register(mcp, lambda: None)
    return mcp


@pytest.mark.asyncio
async def test_uiresource_wraps_as_embedded_resource_or_text_with_uri():
    """Result dict shapes as native TextContent carrying the typed envelope.

    Diagnostics are emitted via ``print`` so CI logs reveal the exact
    content block type on the native MCP-v2 transport.
    """
    mcp = _catalog()

    result = await mcp.call_tool("ui_paint_uiresource", {
        "body": "<h1>Hi</h1>",
        "mode": "inline_html",
    })

    # The native composer returns a list of content blocks.
    assert len(result.content) >= 1, (
        "expected at least one content block")
    block = result.content[0]

    # Print for debugging (helpful in CI logs).
    print(f"DEBUG: content block type = {type(block).__name__}")
    print(f"DEBUG: content block = {block!r}")

    from mcp.types import TextContent as MCPTextContent

    # Typed egress keeps the carrier under its v1 envelope, so the native
    # composer must emit JSON text rather than bypassing the declared output DTO.
    assert isinstance(block, MCPTextContent)
    envelope = json.loads(block.text)
    assert envelope["schema_version"] == "v1"
    assert envelope["ok"] is True and envelope["error"] is None
    data = envelope["data"]
    assert data["type"] == "resource"
    assert data["resource"]["uri"].startswith("ui://factory/")
    assert data["resource"]["mimeType"] == "text/html;profile=mcp-app"
    assert data["resource"]["text"] == "<h1>Hi</h1>"


@pytest.mark.asyncio
async def test_uiresource_remote_dom_mime_preserved_through_fastmcp():
    """RemoteDOM JS mime survives the native composer wrap regardless of branch."""
    mcp = _catalog()

    result = await mcp.call_tool("ui_paint_uiresource", {
        "body": "root.appendChild(document.createElement('p'));",
        "mode": "remote_dom",
    })

    assert len(result.content) >= 1
    block = result.content[0]
    expected_mime = "application/vnd.mcp-ui.remote-dom+javascript"
    from mcp.types import TextContent as MCPTextContent

    assert isinstance(block, MCPTextContent)
    envelope = json.loads(block.text)
    assert envelope["schema_version"] == "v1" and envelope["ok"] is True
    assert envelope["data"]["resource"]["mimeType"] == expected_mime
