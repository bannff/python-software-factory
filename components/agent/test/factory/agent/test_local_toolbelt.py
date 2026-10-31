"""Tests for the squad's local toolbelt (LangChain framework tools)."""
from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.local_toolbelt import (
    available_local_tools, build_local_toolbelt,
)


def test_available_local_tools_are_framework_names():
    tools = set(available_local_tools())
    assert {"read_file", "write_file", "list_directory", "shell", "web_search"} <= tools


def test_build_file_tools_root_confined(tmp_path):
    belt = build_local_toolbelt(["read_file", "write_file", "list_directory"], tmp_path)
    names = {t.name for t in belt}
    assert names == {"read_file", "write_file", "list_directory"}
    # write goes into the workspace root, and escaping it is refused by the toolkit
    write = next(t for t in belt if t.name == "write_file")
    write.invoke({"file_path": "hello.txt", "text": "hi"})
    assert (tmp_path / "hello.txt").read_text() == "hi"
    escaped = write.invoke({"file_path": "../escape.txt", "text": "x"})
    assert "outside" in str(escaped).lower() or "error" in str(escaped).lower()
    assert not (tmp_path.parent / "escape.txt").exists()


def test_build_selects_shell_and_web_search(tmp_path):
    belt = build_local_toolbelt(["shell", "web_search"], tmp_path)
    names = {t.name for t in belt}
    assert "terminal" in names           # ShellTool
    assert any("duckduckgo" in n or "search" in n for n in names)  # DDG search


def test_unknown_names_ignored(tmp_path):
    assert build_local_toolbelt(["bogus"], tmp_path) == []


def test_mixed_selection(tmp_path):
    belt = build_local_toolbelt(["read_file", "shell"], tmp_path)
    names = {t.name for t in belt}
    assert "read_file" in names and "terminal" in names
