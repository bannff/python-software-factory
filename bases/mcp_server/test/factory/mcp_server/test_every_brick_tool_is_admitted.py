"""Every tool a brick registers must be callable through the gateway.

A tool declared without concrete input/output models is silently refused by
public admission: it shows up in ``get_brick_tools`` yet answers
``tool_not_found`` when called. This guard walks every brick so the next such
tool fails CI instead of failing a user.
"""
from __future__ import annotations

import pathlib

from factory.mcp_server.runtime.lazy_loader import LazyBrickLoader
from factory.mcp_server.runtime.tool_catalog import build_tool_catalog

_COMPONENTS = pathlib.Path(__file__).resolve().parents[5] / "components"
# Directories carrying a BRICK.yaml that are not importable gateway bricks.
_NOT_GATEWAY_BRICKS = {
    "arcade_config", "curator", "http_client", "launch", "library", "mcp_utils", "state",
}


class _Agg:
    def __init__(self, lazy: object) -> None:
        self._lazy = lazy


def test_no_brick_tool_is_listed_but_rejected_by_public_admission() -> None:
    bricks = sorted(
        p.name for p in _COMPONENTS.iterdir()
        if (p / "BRICK.yaml").exists() and p.name not in _NOT_GATEWAY_BRICKS
    )
    loader = LazyBrickLoader()
    loader.set_available(bricks)
    catalog = build_tool_catalog(_Agg(loader), None)
    assert not catalog["bricks_failed"], catalog["bricks_failed"]
    assert catalog["invalid_tools"] == [], catalog["invalid_tools"]
