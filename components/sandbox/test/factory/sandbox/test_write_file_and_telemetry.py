"""Tests for inline write_file, output-tail telemetry, and agnostic diff.

Covers the pure helpers (encoding, bounded tail, porcelain parsing) and the
typed MCP boundary envelopes for sandbox.write_file / sandbox.diff.
"""

from __future__ import annotations

import asyncio
import base64

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.tool_result import ToolResult
from unittest.mock import AsyncMock, MagicMock

from factory.sandbox.mcp.operational_extended import register as register_operational
from factory.sandbox.runtime import diff_ops, file_ops, output_capture


def _tool(runtime: MagicMock, name: str):
    mcp = ToolCatalog("sandbox-write-telemetry")
    register_operational(mcp, runtime)
    return asyncio.run(mcp.get_tool(name))


# ---- pure helpers -----------------------------------------------------------

def test_decode_content_utf8_and_base64() -> None:
    assert file_ops.decode_content("hello", "utf8") == b"hello"
    encoded = base64.b64encode(b"\x00\x01binary").decode()
    assert file_ops.decode_content(encoded, "base64") == b"\x00\x01binary"


def test_decode_content_rejects_bad_base64() -> None:
    with pytest.raises(ValueError):
        file_ops.decode_content("not valid base64!!!", "base64")


def test_capture_output_bounds_tail_and_flags_truncation(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_OUTPUT_TAIL_CHARS", "5")
    captured = output_capture.capture_output("0123456789", "ok")
    assert captured["stdout_tail"] == "56789"
    assert captured["stdout_chars"] == 10
    assert captured["stderr_tail"] == "ok"
    assert captured["output_truncated"] is True


def test_capture_output_disabled_when_zero(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_OUTPUT_TAIL_CHARS", "0")
    captured = output_capture.capture_output("noisy output", "err")
    assert captured["stdout_tail"] == ""
    assert captured["stderr_tail"] == ""
    assert captured["output_truncated"] is False
    assert captured["stdout_chars"] == 12


def test_capture_output_malformed_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_OUTPUT_TAIL_CHARS", "abc")
    assert output_capture.tail_limit() == 2000


def test_parse_porcelain_extracts_status_and_path() -> None:
    text = " M src/main.rs\n?? new_file.txt\nA  added.py\n\n"
    files = diff_ops._parse_porcelain(text)
    assert files == [
        {"status": "M", "path": "src/main.rs"},
        {"status": "??", "path": "new_file.txt"},
        {"status": "A", "path": "added.py"},
    ]


def test_git_diff_graceful_when_not_a_repo() -> None:
    execute = AsyncMock(return_value={"exit_code": 128, "stdout": "", "stderr": "not a repo"})
    result = asyncio.run(diff_ops.git_diff(execute, "env", "."))
    assert result == {"is_git_repo": False, "path": ".", "files": [], "stat": ""}
    execute.assert_awaited_once()  # short-circuits after the probe


def test_git_diff_collects_changes_for_repo() -> None:
    execute = AsyncMock(side_effect=[
        {"exit_code": 0, "stdout": "true\n"},
        {"exit_code": 0, "stdout": " M a.txt\n?? b.txt\n"},
        {"exit_code": 0, "stdout": " 2 files changed"},
    ])
    result = asyncio.run(diff_ops.git_diff(execute, "env", "/repo"))
    assert result["is_git_repo"] is True
    assert [f["path"] for f in result["files"]] == ["a.txt", "b.txt"]
    assert result["stat"] == " 2 files changed"


# ---- MCP boundary envelopes -------------------------------------------------

def test_write_file_success_envelope() -> None:
    runtime = MagicMock()
    runtime.write_file = AsyncMock(
        return_value={"success": True, "remote_path": "/app/x.rs", "bytes_written": 12},
    )
    tool = _tool(runtime, "sandbox.write_file")
    result = asyncio.run(tool.fn(env_id="env", remote_path="/app/x.rs", content="hello world!"))
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data.bytes_written == 12
    assert result.data.remote_path == "/app/x.rs"


def test_write_file_failure_envelope() -> None:
    runtime = MagicMock()
    runtime.write_file = AsyncMock(return_value={"success": False, "error": "bad base64"})
    tool = _tool(runtime, "sandbox.write_file")
    result = asyncio.run(tool.fn(env_id="env", remote_path="/app/x", content="?", encoding="base64"))
    assert result.ok is False
    assert result.data is None
    assert result.error == "bad base64"


def test_diff_maps_runtime_result_to_typed_files() -> None:
    runtime = MagicMock()
    runtime.diff = AsyncMock(return_value={
        "is_git_repo": True, "path": ".",
        "files": [{"status": "M", "path": "a.txt"}],
        "stat": " 1 file changed",
    })
    tool = _tool(runtime, "sandbox.diff")
    result = asyncio.run(tool.fn(env_id="env", path="."))
    assert result.ok is True
    assert result.data.is_git_repo is True
    assert result.data.files[0].path == "a.txt"
    assert result.data.stat == " 1 file changed"
