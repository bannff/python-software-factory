"""MCP contract tests for the openarcade base.

Verifies every tool, resource, and prompt is registered with the right name
AND that calling the tool returns a well-shaped payload. Mirrors the api
base's contract test pattern.
"""

from __future__ import annotations

import asyncio

import pytest

from factory.openarcade import env as _env  # noqa: F401  (imports module so AST guard sees it)


@pytest.fixture
def mcp_server(tmp_path, monkeypatch):
    """Create the MCP server with HOME and config dir redirected to siblings.

    The base's ``resolve_config_dir`` refuses to write under ``$HOME``. Redirect
    HOME to one tmp subdir and the config dir to a sibling so the parent/child
    guard does not fire.
    """
    home_dir = tmp_path / "home"
    cfg_dir = tmp_path / "cfg"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("OPENARCADE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("OPENARCADE_NCI_HOST", "127.0.0.1")
    monkeypatch.setenv("OPENARCADE_NCI_PORT", "55355")
    from factory.openarcade.server import create_mcp_server

    return create_mcp_server()


def _get_tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))


class TestContractTools:

    def test_get_capabilities_registered(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_get_capabilities")
        assert tool is not None

    def test_get_capabilities_shape(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_get_capabilities")
        result = tool.fn()
        assert result["name"] == "openarcade"
        assert result["type"] == "base"
        assert "curator" in result["bricks_consumed"]

    def test_health_check_registered(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_health_check")
        assert tool is not None

    def test_health_check_shape(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_health_check")
        result = tool.fn()
        assert "status" in result
        assert "config_dir" in result
        assert "nci_target" in result
        assert "config_dir_writable" in result

    def test_describe_config_schema_registered(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_describe_config_schema")
        assert tool is not None

    def test_describe_config_schema_shape(self, mcp_server) -> None:
        tool = _get_tool(mcp_server, "openarcade_describe_config_schema")
        result = tool.fn()
        assert result["type"] == "object"
        assert "nci_host" in result["properties"]


class TestDomainToolsRegistered:

    def test_scan_roms_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_scan_roms") is not None

    def test_launch_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_launch") is not None

    def test_list_tiles_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_list_tiles") is not None

    def test_check_compatibility_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_check_compatibility") is not None

    def test_get_config_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_get_config") is not None

    def test_run_wall_registered(self, mcp_server) -> None:
        assert _get_tool(mcp_server, "openarcade_run_wall") is not None


class TestResources:

    def test_all_resources_registered(self, mcp_server) -> None:
        resources = asyncio.run(mcp_server.list_resources())
        uris = [str(r.uri) for r in resources]
        assert "openarcade://health" in uris
        assert "openarcade://config" in uris
        assert "openarcade://tiles" in uris
        assert "openarcade://factory" in uris


class TestPrompts:

    def test_play_game_prompt_registered(self, mcp_server) -> None:
        prompts = asyncio.run(mcp_server.list_prompts())
        names = [p.name for p in prompts]
        assert "play_game" in names

    def test_scan_rom_directory_prompt_registered(self, mcp_server) -> None:
        prompts = asyncio.run(mcp_server.list_prompts())
        names = [p.name for p in prompts]
        assert "scan_rom_directory" in names

    def test_play_game_payload(self, mcp_server) -> None:
        import json

        result = asyncio.run(
            mcp_server.render_prompt("play_game", {"game_id": "contra"})
        )
        msg = result.messages[0]
        payload = json.loads(msg.content.text)
        assert payload["game_id"] == "contra"
        assert payload["action"] == "launch"
        assert payload["via"] == "openarcade_launch"
        assert payload["args"]["game_id"] == "contra"
        assert payload["expected_state"] == "PLAYING"

    def test_scan_rom_directory_payload(self, mcp_server) -> None:
        import json

        result = asyncio.run(
            mcp_server.render_prompt(
                "scan_rom_directory", {"rom_dir": "/tmp/roms"}
            )
        )
        msg = result.messages[0]
        payload = json.loads(msg.content.text)
        assert payload["rom_dir"] == "/tmp/roms"
        assert payload["via"] == "openarcade_scan_roms"


class TestServerContract:

    def test_server_name(self, mcp_server) -> None:
        assert mcp_server.name == "factory-openarcade"

    def test_lazy_runner_present(self) -> None:
        from factory.openarcade import server

        assert callable(server.get_mcp_server)
        assert callable(server.main)
