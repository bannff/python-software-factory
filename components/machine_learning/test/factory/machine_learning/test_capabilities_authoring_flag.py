"""ml_get_capabilities tells clients whether authoring is on, up front (#261)."""
from __future__ import annotations

import asyncio

import pytest

from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_tool_catalog


@pytest.mark.parametrize("value,expected", [("1", True), ("", False)])
def test_capabilities_expose_authoring_enabled(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", value)
    catalog = create_tool_catalog(TrackingRuntime())
    tools = {t.name: t.fn for t in asyncio.run(catalog.list_tools())}
    assert tools["ml_get_capabilities"]().data.authoring_enabled is expected
