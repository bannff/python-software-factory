"""Terminal completion engine contracts."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from factory.terminal.runtime import command_completion
from factory.terminal.runtime.completion import MAX_ENTRIES, complete_paths
from factory.terminal.runtime.models import TerminalCompletionSpec, TerminalSpawnSpec
from factory.terminal.runtime.process_cwd import process_cwd
from factory.terminal.runtime.session_registry import SessionRegistry


def test_path_completion_ranks_prefix_dirs_and_bounds(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "my-docs").mkdir()
    (tmp_path / "document.txt").write_text("x")
    (tmp_path / ".hidden").write_text("x")
    for index in range(MAX_ENTRIES + 5):
        (tmp_path / f"extra-{index:02d}").write_text("x")

    result = complete_paths(str(tmp_path), "doc", False)
    assert [item.name for item in result.entries[:3]] == [
        "docs", "document.txt", "my-docs",
    ]
    assert result.entries[0].dir is True
    assert all(item.name != ".hidden" for item in result.entries)

    bounded = complete_paths(str(tmp_path), "", False)
    assert len(bounded.entries) == MAX_ENTRIES
    assert bounded.truncated is True


def test_path_completion_decodes_directory_part_and_filters_files(tmp_path: Path) -> None:
    sub = tmp_path / "my dir"
    sub.mkdir()
    (sub / "inside").mkdir()
    (sub / "ignored.txt").write_text("x")
    result = complete_paths(str(tmp_path), "my dir/i", True)
    assert result.prefix == "i"
    assert [item.name for item in result.entries] == ["inside"]


def test_command_completion_uses_native_cobra_protocol(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(command_completion, "_executable", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        command_completion, "_run",
        lambda argv, cwd: "archcreate\tArchive creation\ncreate\tCreate a pull request\n:0\n",
    )
    result = command_completion.complete_commands(["gh", "pr"], "cre", str(tmp_path))
    assert [(item.name, item.kind) for item in result.entries] == [
        ("create", "sub"), ("archcreate", "sub"),
    ]
    assert result.entries[0].description == "Create a pull request"


def test_completion_spec_rejects_control_data() -> None:
    session_id = "term_" + "a" * 32
    with pytest.raises(ValueError):
        TerminalCompletionSpec(session_id=session_id, token="bad\n")
    with pytest.raises(ValueError):
        TerminalCompletionSpec(session_id=session_id, argv=["bad command"])


def test_process_cwd_reads_current_process() -> None:
    assert process_cwd(os.getpid(), "/fallback") == os.getcwd()


@pytest.mark.asyncio
async def test_registry_live_cwd_follows_cd(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    registry = SessionRegistry()
    opened = await registry.open(
        "tenant", "owner", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    try:
        startup = ""
        for _ in range(40):
            startup += (await registry.read(
                "tenant", "owner", opened.session_id, 0.1)).data
            if "EndPrompt" in startup or startup.rstrip().endswith("$"):
                break
        await registry.write(
            "tenant", "owner", opened.session_id,
            "cd child; printf 'CD_DONE\\n'\r",
        )
        output = ""
        for _ in range(30):
            chunk = await registry.read(
                "tenant", "owner", opened.session_id, 0.1)
            output += chunk.data
            if output.count("CD_DONE") >= 2:
                break
        assert output.count("CD_DONE") >= 2
        for _ in range(20):
            if await registry.current_cwd("tenant", "owner", opened.session_id) == str(child):
                break
            await asyncio.sleep(0.05)
        assert await registry.current_cwd("tenant", "owner", opened.session_id) == str(child)
    finally:
        await registry.close("tenant", "owner", opened.session_id)
