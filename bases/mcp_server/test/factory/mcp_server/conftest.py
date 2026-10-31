"""MCP-server test-tree lifecycle ownership."""
from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _drain_runtime_pools() -> Generator[None, None, None]:
    """Prevent executor workers from surviving past the test session."""
    yield
    from factory.mcp_server.runtime.pools import shutdown_pools
    shutdown_pools()
