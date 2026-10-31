"""Computer Use = a mounted computer_* MCP server; status is pure detection."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from factory.connections.runtime import computer_use as cu
from factory.connections.server import create_tool_catalog

FAKE_DESKTOP = str(Path(__file__).with_name("fake_desktop_server.py"))


def test_status_reports_not_mounted_and_describes_the_pluggable_preset(stack, monkeypatch) -> None:
    runtime, _aggregator, tools = stack
    monkeypatch.setattr(cu.shutil, "which", lambda cmd: "/usr/local/bin/kirocrew" if cmd == "kirocrew" else None)
    out = tools["connections_computer_use_status"].fn()
    assert out.ok is True
    data = out.data
    assert data.mounted is False and data.server_name is None and data.tool_names == []
    assert (data.preset_command, data.preset_args) == ("kirocrew", ["mcp-computer"])
    assert data.preset_command_found is True and data.preset_command_path == "/usr/local/bin/kirocrew"
    assert "Accessibility" in data.accessibility_hint
    assert isinstance(data.platform_supported, bool)


def test_status_flips_when_a_computer_server_mounts_via_the_real_rails(stack, with_owner) -> None:
    runtime, _aggregator, tools = stack
    # An unrelated server (echo) must not count as desktop automation.
    echo = str(Path(__file__).with_name("echo_server.py"))
    with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(
        name="echo", spec={"command": sys.executable, "args": [echo]},
    )))
    assert tools["connections_computer_use_status"].fn().data.mounted is False

    added = with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(
        name="computer", spec={"command": sys.executable, "args": [FAKE_DESKTOP]},
    )))
    assert added.ok is True, added.error
    status = tools["connections_computer_use_status"].fn().data
    assert status.mounted is True and status.server_name == "computer"
    assert {"computer_list_apps", "computer_get_state", "computer_click"} <= set(status.tool_names)

    with_owner(lambda: asyncio.run(tools["connections_remove_server"].fn(
        name="computer", expected_revision=added.data.server.revision,
    )))
    assert tools["connections_computer_use_status"].fn().data.mounted is False
    assert runtime.tool_names("computer") == ()


def test_preset_command_absent_is_reported_not_raised(monkeypatch, tmp_path) -> None:
    from factory.connections.runtime.adapters.server_store_sqlite import SqliteServerStore
    from factory.connections.runtime.runtime import ConnectionsRuntime
    monkeypatch.setattr(cu.shutil, "which", lambda cmd: None)
    runtime = ConnectionsRuntime(SqliteServerStore(tmp_path / "c.db"))
    tools = {t.name: t for t in asyncio.run(create_tool_catalog(runtime).list_tools())}
    data = tools["connections_computer_use_status"].fn().data
    assert data.preset_command_found is False and data.preset_command_path is None
