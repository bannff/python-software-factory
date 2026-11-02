"""Session tests bind arbitrary crew ids; keep a leaked global tool invoker
(set by another brick's test in the same process) from turning them into real
cross-brick crew lookups. Tests that want the agent brick install their own."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import get_service, set_service


@pytest.fixture(autouse=True)
def _no_ambient_tool_invoker():
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", None)
    yield
    set_service("tool_invoker_for_caller", previous)
