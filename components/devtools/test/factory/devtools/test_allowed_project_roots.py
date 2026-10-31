"""Tests for the allowed-project-roots read path (interface + MCP tool)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from factory.devtools.interface import list_allowed_project_roots
from factory.devtools.server import create_tool_catalog


def test_list_allowed_project_roots_reads_the_configured_env_var(
    tmp_path: Path, monkeypatch,
) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv(
        "COMPANION_X_PROJECT_ALLOWED_ROOTS", f"{first}{__import__('os').pathsep}{second}",
    )

    roots = list_allowed_project_roots()

    assert roots == [str(first.resolve()), str(second.resolve())]


def test_list_allowed_project_roots_falls_back_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", raising=False)

    roots = list_allowed_project_roots()

    assert roots == [str(Path.cwd().resolve().parent)]


def test_the_mcp_tool_returns_the_same_roots_as_the_interface_function(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "only"
    root.mkdir()
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(root))

    class Runtime:
        pass

    catalog = create_tool_catalog(Runtime())
    tool = asyncio.run(catalog.get_tool("devtools_list_allowed_project_roots"))
    result = tool.fn()

    assert result.ok is True
    assert result.data.roots == [str(root.resolve())]
