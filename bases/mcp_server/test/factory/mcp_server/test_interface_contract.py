"""Pin the canonical native MCP-v2 public API."""
from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path

from factory.mcp_server import (
    create_mcp_server as package_create_mcp_server,
    create_server as package_create_server,
)
from factory.mcp_server import core
from factory.mcp_server import interface as mcp_iface

_PUBLIC_EXPORTS = {
    "create_server", "create_mcp_server", "create_app", "get_server",
    "get_aggregator", "main", "BrickDiscovery", "BrickInfo", "MCPAggregator",
    "set_workflow_run_id", "get_workflow_run_id",
    "get_native_v2_selected_registrations", "get_native_v2_view",
    "get_brick_tool_map", "get_op_kind_lookup", "get_tool_catalog",
    "build_streamable_http_app", "resolve_public_mcp_names",
    "create_exact_flat_native_scope",
}


def test_public_surface_is_exact() -> None:
    assert set(mcp_iface.__all__) == _PUBLIC_EXPORTS


def test_canonical_factory_and_compatibility_name_are_exact_identities() -> None:
    assert mcp_iface.create_server is core.create_server
    assert mcp_iface.create_mcp_server is mcp_iface.create_server
    assert package_create_server is mcp_iface.create_server
    assert package_create_mcp_server is mcp_iface.create_server
    assert str(inspect.signature(mcp_iface.create_server)) == "() -> 'Any'"


def test_legacy_server_module_is_removed() -> None:
    assert importlib.util.find_spec("factory.mcp_server.server") is None


def test_repository_has_no_direct_legacy_server_import() -> None:
    root = Path(__file__).parents[5]
    offenders = []
    for source_root in (root / "bases", root / "components", root / "projects", root / "scripts"):
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "factory.mcp_server.server":
                    offenders.append(path.relative_to(root))
                if isinstance(node, ast.Import) and any(
                    alias.name == "factory.mcp_server.server" for alias in node.names
                ):
                    offenders.append(path.relative_to(root))
    assert not offenders


def test_get_brick_tool_map_signature() -> None:
    assert str(inspect.signature(mcp_iface.get_brick_tool_map)) == (
        "(brick: 'str') -> 'dict[str, Any] | None'"
    )


def test_get_native_v2_view_signature() -> None:
    assert str(inspect.signature(mcp_iface.get_native_v2_view)) == (
        "(plan: 'Any', allowlist: 'set[str] | None' = None, "
        "*, rename_dot_to_underscore: 'bool' = True) -> 'Any'"
    )
