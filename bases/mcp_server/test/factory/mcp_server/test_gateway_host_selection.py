"""Gateway-host selection contract tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from factory.mcp_server.core import _resolve_brick_names
from factory.mcp_server.runtime.discovery import BrickDiscovery


_INDEX = """
bricks:
  components:
    - name: graph
      namespace: factory.graph
      mcp_enabled: true
  bases:
    - name: mcp_server
      namespace: factory.mcp_server
      mcp_enabled: true
      mcp_gateway_host: true
"""


def test_gateway_host_is_inventory_but_not_aggregation_candidate(tmp_path: Path):
    (tmp_path / "BRICKS_INDEX.yaml").write_text(_INDEX)
    discovery = BrickDiscovery(workspace_root=tmp_path)

    assert discovery.get_brick_names() == ["graph", "mcp_server"]
    assert discovery.get_brick_names(aggregation_only=True) == ["graph"]


def _resolve_with_gateway(config: dict[str, str]) -> list[str]:
    def names(*, mcp_only: bool = True, aggregation_only: bool = False):
        assert mcp_only
        return ["graph"] if aggregation_only else ["graph", "mcp_server"]

    with patch("factory.mcp_server.runtime.brick_selection.BrickDiscovery") as cls:
        cls.return_value.get_brick_names.side_effect = names
        return _resolve_brick_names(config)


def test_custom_exclude_cannot_readmit_gateway_host():
    assert _resolve_with_gateway({
        "include_bricks": "", "exclude_bricks": "graph",
    }) == []


def test_explicit_gateway_host_include_is_rejected():
    with pytest.raises(ValueError, match="gateway host.*mcp_server"):
        _resolve_with_gateway({
            "include_bricks": "graph,mcp_server", "exclude_bricks": "",
        })
