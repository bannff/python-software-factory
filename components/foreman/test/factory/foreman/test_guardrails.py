"""Guardrail and project-base behavior tests."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from factory.foreman.guardian import check_projects_have_base
from factory.foreman.server import create_server


def test_foreman_guardrails_tool_is_typed() -> None:
    tool = asyncio.run(create_server().get_tool("foreman_get_repo_guardrails"))
    payload = tool.fn()
    assert payload.ok and payload.data is not None
    assert payload.data.schema_version == 1
    assert payload.data.control_plane.system == "github"
    assert payload.data.execution_plane.foreman
    assert isinstance(payload.data.workflow_example, list)


def test_project_has_base_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        proj = ws / "projects" / "myproject"
        proj.mkdir(parents=True)
        (proj / "pyproject.toml").write_text(
            '[tool.polylith.bricks]\n'
            '"../../bases/mcp_server/src/factory/mcp_server" = "factory/mcp_server"\n'
            '"../../components/cache/src/factory/cache" = "factory/cache"\n'
        )
        result = check_projects_have_base(ws)
        assert result["passed"] is True
        assert result["projects_checked"] == 1


def test_project_has_base_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        proj = ws / "projects" / "myproject"
        proj.mkdir(parents=True)
        (proj / "pyproject.toml").write_text(
            '[tool.polylith.bricks]\n'
            '"../../components/cache/src/factory/cache" = "factory/cache"\n'
        )
        result = check_projects_have_base(ws)
        assert result["passed"] is False
        assert result["violations"][0]["project"] == "myproject"


def test_project_has_base_no_projects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = check_projects_have_base(Path(tmp))
        assert result["passed"] is True
        assert result["projects_checked"] == 0
