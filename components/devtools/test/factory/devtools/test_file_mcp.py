from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest

from factory.devtools.runtime.models import ProjectBinding
from factory.devtools.runtime.runtime import DevtoolsRuntime
from factory.devtools.server import create_tool_catalog
from factory.mcp_utils.interface import ToolResult


def _tool(catalog, name):
    return asyncio.run(catalog.get_tool(name)).fn


def test_typed_file_tools_complete_session_bound_lifecycle(tmp_path, monkeypatch) -> None:
    from factory.devtools.mcp import deterministic, operational

    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    binding = ProjectBinding(
        tenant_id="tenant", owner_id="owner", session_id="session",
        root=str(tmp_path.resolve()),
    )

    async def project(_envelope):
        return binding

    monkeypatch.setattr(deterministic, "project_binding", project)
    monkeypatch.setattr(operational, "project_binding", project)
    catalog = create_tool_catalog(DevtoolsRuntime())
    envelope = {"thread_id": "thread"}

    written = asyncio.run(_tool(catalog, "devtools_write_file")(
        path="sample.py", content="VALUE = 1\n", envelope=envelope,
    ))
    assert written.ok and written.data.result.created is True
    read = asyncio.run(_tool(catalog, "devtools_read_file")(
        path="sample.py", envelope=envelope,
    ))
    assert read.ok and read.data.result.content == "VALUE = 1\n"
    edited = asyncio.run(_tool(catalog, "devtools_edit_file")(
        path="sample.py", content="VALUE = 2\n",
        base_sha256=read.data.result.sha256, envelope=envelope,
    ))
    assert edited.ok and edited.data.result.created is False
    found = asyncio.run(_tool(catalog, "devtools_search")(
        query="VALUE", path=".", glob="*.py", envelope=envelope,
    ))
    assert found.ok and found.data.result.matches[0].path == "sample.py"
    listing = asyncio.run(_tool(catalog, "devtools_list_dir")(
        path=".", envelope=envelope,
    ))
    assert listing.ok and any(item.path == "sample.py" for item in listing.data.result.entries)
    refused = asyncio.run(_tool(catalog, "devtools_read_file")(
        path="../outside", envelope=envelope,
    ))
    assert refused.ok is False


def test_file_tools_have_strict_exact_modalities() -> None:
    catalog = create_tool_catalog()
    expected = {
        "devtools_read_file": ("deterministic", "read"),
        "devtools_list_dir": ("deterministic", "read"),
        "devtools_search": ("deterministic", "read"),
        "devtools_write_file": ("operational", "write"),
        "devtools_edit_file": ("operational", "write"),
        "devtools_cancel_command": ("operational", "shell"),
    }
    for name, (category, kind) in expected.items():
        fn = _tool(catalog, name)
        assert getattr(fn, "_mcp_category") == category
        assert getattr(fn, "_mcp_op_kind") == kind
        input_model = getattr(fn, "_mcp_input_model")
        output_model = getattr(fn, "_mcp_output_model")
        assert input_model.model_config["extra"] == "forbid"
        assert get_type_hints(fn)["return"] == ToolResult[output_model]


async def _wait_for_started(events) -> str:
    for _ in range(100):
        for item in list(events):
            if item.get("event_type") == "devtools.command.started":
                return item["payload"]["run_id"]
        await asyncio.sleep(0.02)
    raise AssertionError("command start event was not published")


@pytest.mark.asyncio
async def test_command_can_be_cancelled_through_mcp(tmp_path, monkeypatch) -> None:
    from factory.devtools.mcp import deterministic, operational
    from factory.devtools.runtime import command_runner

    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (tmp_path / "test_wait.py").write_text(
        "import time\ndef test_wait():\n time.sleep(30)\n"
    )
    bound = ProjectBinding(
        tenant_id="tenant", owner_id="owner", session_id="session",
        root=str(tmp_path.resolve()),
    )

    async def project(_envelope):
        return bound

    monkeypatch.setattr(deterministic, "project_binding", project)
    monkeypatch.setattr(operational, "project_binding", project)
    events = []
    monkeypatch.setattr(command_runner.event_bus, "publish", events.append)
    catalog = create_tool_catalog(DevtoolsRuntime())
    run_tool = (await catalog.get_tool("devtools_run_command")).fn
    cancel_tool = (await catalog.get_tool("devtools_cancel_command")).fn
    running = asyncio.create_task(run_tool(
        argv=["python", "-m", "pytest", "-q"], timeout_seconds=30,
    ))
    run_id = await _wait_for_started(events)
    cancelled = await cancel_tool(run_id=run_id)
    result = await running
    assert cancelled.ok and cancelled.data.cancelled is True
    assert result.ok and result.data.result.cancelled is True
