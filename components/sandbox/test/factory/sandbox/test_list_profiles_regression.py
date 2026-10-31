"""Regression: sandbox.list_profiles must not fail on string ports (#785).

ProfileInfo.ports diverged to dict[str, int] while every built-in profile (and
SandboxProfile.ports) uses dict[str, str] host:container maps. Under StrictModel
that raised ValidationError -> tool_execution_failed on every call. This locks
the egress model to the source shape.
"""

from __future__ import annotations

import asyncio

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from unittest.mock import MagicMock

from factory.sandbox.mcp.deterministic import ProfileInfo, ProfilesResult, register
from factory.sandbox.runtime.profiles import BUILTIN_PROFILES


def test_profile_info_ports_match_source_type() -> None:
    """Every built-in profile builds a ProfileInfo without coercion errors."""
    result = ProfilesResult(profiles={
        name: ProfileInfo(
            image=p.image, ports=p.ports, health_check_url=p.health_check_url,
        )
        for name, p in BUILTIN_PROFILES.items()
    })
    assert set(result.profiles) == set(BUILTIN_PROFILES)
    # ports round-trip as string host:container maps, no data loss
    assert result.profiles["vampi"].ports == {"5050": "5000"}


def test_list_profiles_tool_succeeds_over_boundary() -> None:
    """The registered tool returns ok and includes every built-in (was failing)."""
    mcp = ToolCatalog("sandbox-list-profiles")
    register(mcp, MagicMock())
    tool = asyncio.run(mcp.get_tool("sandbox.list_profiles"))
    result = tool.fn()
    assert result.ok is True
    assert set(BUILTIN_PROFILES) <= set(result.data.profiles)


def test_list_profiles_includes_user_yaml_profiles(tmp_path, monkeypatch) -> None:
    """User YAML profiles under SANDBOX_PROFILES_DIR are discoverable (#789)."""
    (tmp_path / "acme-sdk.yaml").write_text(
        "name: acme-sdk\nimage: acme:1-slim\nports:\n  '8080': '80'\n"
        "health_check_url: http://localhost:8080/\n",
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    mcp = ToolCatalog("sandbox-list-profiles-yaml")
    register(mcp, MagicMock())
    tool = asyncio.run(mcp.get_tool("sandbox.list_profiles"))
    result = tool.fn()
    assert result.ok is True
    # both a code built-in AND the on-disk user profile are present
    assert "vampi" in result.data.profiles
    assert "acme-sdk" in result.data.profiles
    assert result.data.profiles["acme-sdk"].image == "acme:1-slim"
    assert result.data.profiles["acme-sdk"].ports == {"8080": "80"}
