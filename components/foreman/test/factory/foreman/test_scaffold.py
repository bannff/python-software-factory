"""Tests for project scaffolding."""

import tempfile
from pathlib import Path

from factory.foreman.scaffold import create_project


def _workspace_root() -> Path:
    return Path(__file__).parents[5]


def _make_brick(ws: Path, name: str, kind: str = "component", code: str = ""):
    """Create a minimal brick in a temp workspace."""
    prefix = "bases" if kind == "base" else "components"
    src = ws / prefix / name / "src" / "factory" / name
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text(code)


def _make_ws():
    """Create a temp workspace with projects dir. Returns (tmpdir, ws_path)."""
    tmp = tempfile.mkdtemp()
    ws = Path(tmp)
    (ws / "projects").mkdir()
    return tmp, ws


def test_create_project_basic():
    tmp, ws = _make_ws()
    _make_brick(ws, "mybrick", code="import pydantic\n")
    _make_brick(ws, "mybase", kind="base")
    result = create_project("myproject", ["mybase", "mybrick"], workspace_root=ws)
    assert result["status"] == "success"
    assert (ws / "projects" / "myproject" / "pyproject.toml").exists()
    assert (ws / "projects" / "myproject" / "README.md").exists()


def test_create_project_pyproject_content():
    tmp, ws = _make_ws()
    _make_brick(ws, "mybrick", code="import pydantic\n")
    _make_brick(ws, "mybase", kind="base")
    create_project("myproject", ["mybase", "mybrick"], workspace_root=ws)
    content = (ws / "projects" / "myproject" / "pyproject.toml").read_text()
    assert 'name = "myproject"' in content
    assert "hatch-polylith-bricks" in content
    assert "factory/mybrick" in content
    assert "pydantic" in content


def test_create_project_already_exists():
    tmp, ws = _make_ws()
    (ws / "projects" / "existing").mkdir(parents=True)
    result = create_project("existing", ["anything"], workspace_root=ws)
    assert result["status"] == "error"
    assert "already exists" in result["error"]


def test_create_project_brick_not_found():
    tmp, ws = _make_ws()
    (ws / "components").mkdir()
    result = create_project("myproject", ["nonexistent"], workspace_root=ws)
    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_create_project_transitive_deps():
    tmp, ws = _make_ws()
    _make_brick(ws, "brick_a", code="from factory.brick_b.interface import x\n")
    _make_brick(ws, "brick_b", code="import json\n")
    _make_brick(ws, "mybase", kind="base")
    result = create_project("myproject", ["mybase", "brick_a"], workspace_root=ws)
    assert result["status"] == "success"
    content = (ws / "projects" / "myproject" / "pyproject.toml").read_text()
    assert "factory/brick_a" in content
    assert "factory/brick_b" in content


def test_create_project_with_real_bricks():
    ws = _workspace_root()
    tmp = tempfile.mkdtemp()
    tmp_ws = Path(tmp)
    (tmp_ws / "components").symlink_to(ws / "components")
    (tmp_ws / "bases").symlink_to(ws / "bases")
    (tmp_ws / "projects").mkdir()
    result = create_project(
        "test_project", ["mcp_server", "cache", "graph"],
        description="Test project", workspace_root=tmp_ws,
    )
    assert result["status"] == "success"
    content = (tmp_ws / "projects" / "test_project" / "pyproject.toml").read_text()
    assert "factory/cache" in content
    assert "factory/graph" in content
    assert "factory/mcp_server" in content


def test_create_project_readme_content():
    tmp, ws = _make_ws()
    _make_brick(ws, "mybrick")
    _make_brick(ws, "mybase", kind="base")
    create_project("myproject", ["mybase", "mybrick"], workspace_root=ws)
    readme = (ws / "projects" / "myproject" / "README.md").read_text()
    assert "mybrick" in readme
    assert "myproject" in readme


def test_create_project_base_brick():
    tmp, ws = _make_ws()
    _make_brick(ws, "mybase", kind="base")
    result = create_project("myproject", ["mybase"], workspace_root=ws)
    assert result["status"] == "success"
    content = (ws / "projects" / "myproject" / "pyproject.toml").read_text()
    assert "../../bases/mybase/src/factory/mybase" in content


def test_create_project_rejects_no_base():
    tmp, ws = _make_ws()
    _make_brick(ws, "mybrick")
    result = create_project("myproject", ["mybrick"], workspace_root=ws)
    assert result["status"] == "error"
    assert "No base brick" in result["error"]
    assert "available_bases" in result


def test_create_project_rejects_no_base_suggests():
    tmp, ws = _make_ws()
    _make_brick(ws, "mycomp")
    _make_brick(ws, "mybase", kind="base", code="from factory.mycomp import core\n")
    result = create_project("myproject", ["mycomp"], workspace_root=ws)
    assert result["status"] == "error"
    assert len(result["suggested_bases"]) > 0
    assert result["suggested_bases"][0]["base"] == "mybase"
    assert "mycomp" in result["suggested_bases"][0]["connects_to"]


def test_create_project_with_base_succeeds():
    tmp, ws = _make_ws()
    _make_brick(ws, "mycomp")
    _make_brick(ws, "mybase", kind="base")
    result = create_project("myproject", ["mybase", "mycomp"], workspace_root=ws)
    assert result["status"] == "success"

def test_create_project_preserves_pydantic_settings():
    """Regression test for #141: pydantic-settings must not be dropped."""
    tmp, ws = _make_ws()
    _make_brick(ws, "mybrick", code="import pydantic_settings\n")
    _make_brick(ws, "mybase", kind="base")
    result = create_project("myproject", ["mybase", "mybrick"], workspace_root=ws)
    assert result["status"] == "success"
    content = (ws / "projects" / "myproject" / "pyproject.toml").read_text()
    assert "pydantic-settings" in content, "pydantic-settings was dropped (issue #141)"
    assert "pydantic>=" in content, "pydantic core dep should still be present"

