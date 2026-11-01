"""Connections MCP tools, gateway pseudo-brick mount, and real stdio round-trip."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ECHO = str(Path(__file__).with_name("echo_server.py"))
OWNER = {"tenant_id": "local", "principal_id": "local-operator"}


def test_list_requires_owner_identity(stack) -> None:
    _, _, tools = stack
    assert tools["connections_list_servers"].fn().error == "connections_identity_required"


def test_import_document_never_egresses_secret_values(stack, with_owner, monkeypatch) -> None:
    runtime, _, tools = stack
    monkeypatch.setenv("EXAMPLE_BEARER_ENV", "super-secret-value")
    document = json.dumps({"mcpServers": {"remote": {
        "transport": "streamable_http", "url": "https://unreachable.invalid/mcp",
        "headers": {"Authorization": "EXAMPLE_BEARER_ENV"}, "enabled": False,
    }}})
    result = with_owner(lambda: asyncio.run(tools["connections_import_servers"].fn(document=document)))
    assert result.ok is True, result.error
    dumped = result.model_dump_json()
    assert "super-secret-value" not in dumped
    assert '"headers":{"Authorization":"EXAMPLE_BEARER_ENV"}' in dumped
    listed = with_owner(lambda: tools["connections_list_servers"].fn())
    assert [item.name for item in listed.data.servers] == ["remote"]
    assert listed.data.servers[0].mounted is False
    assert listed.data.servers[0].unresolved_env == []
    monkeypatch.delenv("EXAMPLE_BEARER_ENV")
    relisted = with_owner(lambda: tools["connections_list_servers"].fn())
    assert relisted.data.servers[0].unresolved_env == ["EXAMPLE_BEARER_ENV"], "a mistyped source env name must be loud"


def test_malformed_document_is_a_typed_failure(stack, with_owner) -> None:
    _, _, tools = stack
    for bad in ("{not json", json.dumps({"mcpServers": {}}), json.dumps({"servers": {}})):
        result = with_owner(lambda: asyncio.run(tools["connections_import_servers"].fn(document=bad)))
        assert result.ok is False and result.error == "connections_document_invalid"


def test_stdio_server_mounts_as_gateway_brick_and_round_trips(stack, with_owner, monkeypatch) -> None:
    runtime, aggregator, tools = stack
    monkeypatch.setenv("FIXTURE_SOURCE_TOKEN", "from-api-env")
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN", "must-not-leak-into-child")
    spec = {"command": sys.executable, "args": [ECHO], "env": {"CHILD_TOKEN": "FIXTURE_SOURCE_TOKEN"}}
    added = with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(name="echo", spec=spec)))
    assert added.ok is True, added.error
    assert added.data.server.mounted is True and added.data.server.tools_count == 2
    assert added.data.server.env == {"CHILD_TOKEN": "FIXTURE_SOURCE_TOKEN"}

    listed = aggregator.list_bricks()["bricks"]
    brick = next(item for item in listed if item["name"] == "mcp-echo")
    assert brick["loaded"] is True and brick["tools_count"] == 2
    names = aggregator.get_brick_tool_names("mcp-echo")
    assert {"mcp_echo_echo", "mcp_echo_read_env"} <= set(names) or {"mcp-echo_echo", "mcp-echo_read_env"} <= set(names)

    async def call(tool: str, **arguments):
        return await aggregator.call_brick_tool("mcp-echo", tool, arguments)

    echoed = asyncio.run(call("echo", text="hi"))
    assert echoed["ok"] is True, echoed
    payload = echoed["result"]["structured_content"]["data"]
    assert any("echo:hi" in json.dumps(item) for item in payload["content"])
    child = asyncio.run(call("read_env", name="CHILD_TOKEN"))["result"]["structured_content"]["data"]
    assert any("from-api-env" in json.dumps(item) for item in child["content"])
    leaked = asyncio.run(call("read_env", name="MCP_LOCAL_AUTH_TOKEN"))["result"]["structured_content"]["data"]
    assert any("<unset>" in json.dumps(item) for item in leaked["content"])

    removed = with_owner(lambda: asyncio.run(tools["connections_remove_server"].fn(
        name="echo", expected_revision=added.data.server.revision,
    )))
    assert removed.ok is True and removed.data.removed is True
    assert all(item["name"] != "mcp-echo" for item in aggregator.list_bricks()["bricks"])
    assert runtime.mounted() == ()


def test_unreachable_server_reports_why_it_did_not_mount(stack, with_owner) -> None:
    _, _, tools = stack
    spec = {"transport": "stdio", "command": "definitely-not-a-command", "args": [], "env": {}, "enabled": True}
    added = with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(name="broken", spec=spec)))
    assert added.ok is True, "registration succeeds even when the mount fails"
    assert added.data.server.mounted is False
    assert added.data.server.mount_error.startswith("FileNotFoundError"), "an unreachable server must say why"
    listed = with_owner(lambda: tools["connections_list_servers"].fn())
    assert listed.data.servers[0].mount_error == added.data.server.mount_error


def _add(stack, with_owner, monkeypatch, failure: BaseException):
    import factory.connections.runtime.runtime as runtime_module

    async def boom(_record):
        raise failure
    monkeypatch.setattr(runtime_module, "open_source", boom)
    _, _, tools = stack
    spec = {"transport": "streamable_http", "url": "https://x.invalid/mcp", "headers": {}, "enabled": True}
    return with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(name="remote", spec=spec)))


def test_mount_error_never_echoes_exception_text(stack, with_owner, monkeypatch) -> None:
    added = _add(stack, with_owner, monkeypatch, RuntimeError("401 Authorization: Bearer super-secret-value"))
    assert added.data.server.mount_error == "RuntimeError"
    assert "super-secret-value" not in added.model_dump_json()


def test_mount_error_unwraps_exception_groups(stack, with_owner, monkeypatch) -> None:
    group = ExceptionGroup("unhandled errors in a TaskGroup", [ConnectionRefusedError(61, "Connection refused")])
    added = _add(stack, with_owner, monkeypatch, group)
    assert added.data.server.mount_error == "ConnectionRefusedError: Connection refused"


def test_mount_error_is_scoped_to_its_owner(stack, monkeypatch) -> None:
    runtime, _, _ = stack
    from factory.connections.runtime.models import ServerSpec
    import factory.connections.runtime.runtime as runtime_module

    async def boom(_record):
        raise ConnectionRefusedError(61, "Connection refused")
    monkeypatch.setattr(runtime_module, "open_source", boom)
    spec = ServerSpec(transport="streamable_http", url="https://x.invalid/mcp", enabled=True)
    mine = runtime.add("local", "alice", "same", spec)
    theirs = runtime.add("local", "bob", "same", spec)
    try:
        asyncio.run(runtime.mount(mine))
    except ConnectionRefusedError:
        pass
    assert runtime.mount_error("local", "alice", "same") is not None
    assert runtime.mount_error(theirs.tenant_id, theirs.owner_id, "same") is None


def test_failed_catalog_build_is_reported_and_rolled_back(stack, with_owner, monkeypatch) -> None:
    import factory.connections.runtime.runtime as runtime_module
    runtime, _, tools = stack
    closed: list[bool] = []

    class Source:
        async def close(self) -> None:
            closed.append(True)

    async def opened(_record):
        return Source(), ()

    def bad_catalog(*_args):
        raise ValueError("duplicate tool name")
    monkeypatch.setattr(runtime_module, "open_source", opened)
    monkeypatch.setattr(runtime_module, "build_catalog", bad_catalog)
    spec = {"transport": "stdio", "command": "x", "args": [], "env": {}, "enabled": True}
    added = with_owner(lambda: asyncio.run(tools["connections_add_server"].fn(name="dup", spec=spec)))
    assert added.data.server.mounted is False and added.data.server.mount_error == "ValueError"
    assert closed == [True] and runtime.mounted() == ()
