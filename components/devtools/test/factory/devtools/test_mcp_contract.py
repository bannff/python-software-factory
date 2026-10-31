from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest

from factory.devtools.mcp.contracts import RunCommandInput, RunCommandOutput
from factory.devtools.runtime.models import CommandResult
from factory.devtools.server import create_tool_catalog
from factory.mcp_utils.interface import ToolResult


def _result() -> CommandResult:
    return CommandResult(
        run_id="cmd_" + "a" * 32, argv=("pytest", "-q"), cwd=".",
        stdout="ok", stderr="", exit_code=0, duration_ms=1,
        timed_out=False, cancelled=False, truncated=False,
        output_sha256="b" * 64,
    )


def test_run_command_is_strict_typed_operational_shell_tool(
    tmp_path, monkeypatch,
) -> None:
    from factory.devtools.mcp import binding, operational

    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setattr(operational, "get_run_id", lambda: "chat-run")
    monkeypatch.setattr(binding, "get_envelope", lambda: {})
    seen = []

    def factory(caller):
        assert caller == "devtools"
        def invoke(target, **kwargs):
            assert target == {"brick_name": "session", "tool_name": "resolve_thread"}
            return {"result": {"structured_content": {"ok": True, "data": {
                "session": {
                    "tenant_id": "tenant", "owner_id": "owner",
                    "session_id": "session", "thread_id": "thread",
                    "project": str(project), "archived_at": None,
                },
            }}}}
        return invoke
    monkeypatch.setattr(binding, "get_service", lambda name: factory)

    class Runtime:
        def run_command(self, binding, argv, cwd, **kwargs):
            seen.append((binding, argv, cwd, kwargs))
            return _result()

    catalog = create_tool_catalog(Runtime())
    tools = asyncio.run(catalog.list_tools())
    assert [item.name for item in tools] == [
        "devtools_list_allowed_project_roots",
        "devtools_read_file", "devtools_list_dir", "devtools_search",
        "devtools_git_status", "devtools_git_diff", "devtools_git_log",
        "devtools_write_file", "devtools_edit_file", "devtools_run_command",
        "devtools_cancel_command", "devtools_git_stage", "devtools_git_commit", "devtools_git_push",
    ]
    fn = asyncio.run(catalog.get_tool("devtools_run_command")).fn
    assert getattr(fn, "_mcp_category") == "operational"
    assert getattr(fn, "_mcp_op_kind") == "shell"
    assert getattr(fn, "_mcp_input_model") is RunCommandInput
    assert getattr(fn, "_mcp_output_model") is RunCommandOutput
    assert RunCommandInput.model_config["extra"] == "forbid"
    assert get_type_hints(fn)["return"] == ToolResult[RunCommandOutput]
    result = asyncio.run(fn(
        argv=["pytest", "-q"], envelope={"thread_id": "thread"},
    ))
    assert result.ok and result.data.result.exit_code == 0
    assert seen[0][3]["correlation_id"] == "chat-run"
    assert seen[0][0].root == str(project.resolve())
    with pytest.raises(Exception):
        asyncio.run(fn(
            argv=["pytest"], envelope={"thread_id": "thread"}, unexpected=True,
        ))


def test_archived_or_unbound_session_is_refused(tmp_path, monkeypatch) -> None:
    from factory.devtools.mcp import binding
    monkeypatch.setattr(binding, "get_envelope", lambda: {})
    monkeypatch.setattr(binding, "get_service", lambda name: (
        lambda caller: lambda target, **kwargs: {"result": {"structured_content": {
            "ok": True, "data": {"session": {
                "archived_at": "2026-09-11T00:00:00Z", "project": "",
            }},
        }}}
    ))
    fn = asyncio.run(create_tool_catalog().get_tool("devtools_run_command")).fn
    result = asyncio.run(fn(
        argv=["pytest"], envelope={"thread_id": "thread"},
    ))
    assert result.ok is False and result.error == "tool_execution_failed"


def test_git_tools_have_exact_modalities_and_authoring_is_disabled(monkeypatch) -> None:
    from factory.devtools.mcp import authoring

    monkeypatch.delenv("DEVTOOLS_ENABLE_AUTHORING_TOOLS", raising=False)
    catalog = create_tool_catalog()
    expected = {
        "devtools_git_status": ("deterministic", "read"),
        "devtools_git_diff": ("deterministic", "read"),
        "devtools_git_log": ("deterministic", "read"),
        "devtools_git_stage": ("authoring", "authoring"),
        "devtools_git_commit": ("authoring", "authoring"),
        "devtools_git_push": ("authoring", "authoring"),
    }
    for name, (category, kind) in expected.items():
        fn = asyncio.run(catalog.get_tool(name)).fn
        assert getattr(fn, "_mcp_category") == category
        assert getattr(fn, "_mcp_op_kind") == kind
        input_model = getattr(fn, "_mcp_input_model")
        output_model = getattr(fn, "_mcp_output_model")
        assert input_model.model_config["extra"] == "forbid"
        assert get_type_hints(fn)["return"] == ToolResult[output_model]
    stage = asyncio.run(catalog.get_tool("devtools_git_stage")).fn
    refused = asyncio.run(stage(paths=["tracked.txt"]))
    assert refused.ok is False and refused.error == "authoring_disabled"
    assert authoring.authoring_enabled() is False
