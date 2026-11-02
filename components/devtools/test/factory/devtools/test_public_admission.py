from __future__ import annotations

import asyncio

from factory.devtools.server import create_tool_catalog
from factory.mcp_server.runtime.public_admission import _validate


def test_every_devtools_tool_is_admitted_to_the_public_surface() -> None:
    catalog = create_tool_catalog()
    tools = asyncio.run(catalog.list_tools())
    rejected = {tool.name: _validate(tool)[0] for tool in tools if _validate(tool)[0]}
    assert rejected == {}, "tools advertised but not callable through call_brick_tool"
    assert "devtools_list_allowed_project_roots" in {tool.name for tool in tools}
