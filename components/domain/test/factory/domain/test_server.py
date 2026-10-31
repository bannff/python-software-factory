"""MCP server round-trip for the domain brick (bd:python-factory-w7i8k).

In-process only — ``create_server()`` builds the FastMCP server with the
default in-memory runtime; we assert the expected tools register. No
network, no live backend.
"""
from __future__ import annotations

import asyncio

import pytest

from factory.domain.interface import create_server
from factory.domain.registry import unified


@pytest.fixture(autouse=True)
def _reset_store():
    unified.reset_default_store()
    yield
    unified.reset_default_store()


def test_server_registers_expected_tools() -> None:
    mcp = create_server()
    tool_names = {t.name for t in asyncio.run(mcp.list_tools())}
    for expected in (
        "domain_get_manifest",
        "domain_open_engagement",
        "domain_create_manifest",
    ):
        assert expected in tool_names, f"{expected} not in {sorted(tool_names)}"


def test_server_name() -> None:
    mcp = create_server()
    assert mcp.name == "domain-module"
