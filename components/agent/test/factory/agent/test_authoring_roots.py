"""Durable authoring roots: resolution, loud failure at use, and no temp dirs."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from factory.agent.authoring.roots import (
    AuthoringRootUnavailable, ensure_root, packaged_skills_root, resolve_root,
)


@pytest.fixture
def clean_roots(monkeypatch):
    for variable in ("FACTORY_AGENT_CONFIG_DIR", "FACTORY_AGENT_SKILLS_DIR",
                     "FACTORY_AGENT_STEERING_DIR"):
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def test_every_kind_resolves_a_distinct_durable_default(clean_roots, tmp_path) -> None:
    clean_roots.chdir(tmp_path)
    roots = {kind: resolve_root(kind) for kind in ("config", "skills", "steering")}
    assert {root.path for root in roots.values()} == {
        (tmp_path / ".storage" / "agent-config").resolve(),
        (tmp_path / ".storage" / "agent-skills").resolve(),
        (tmp_path / ".storage" / "agent-steering").resolve(),
    }
    assert {root.source for root in roots.values()} == {"default"}
    assert {root.variable for root in roots.values()} == {
        "FACTORY_AGENT_CONFIG_DIR", "FACTORY_AGENT_SKILLS_DIR", "FACTORY_AGENT_STEERING_DIR",
    }


def test_env_value_wins_and_is_expanded(clean_roots, tmp_path) -> None:
    clean_roots.setenv("FACTORY_AGENT_SKILLS_DIR", f"{tmp_path}/my-skills/")
    root = resolve_root("skills")
    assert root.path == (tmp_path / "my-skills").resolve() and root.source == "env"


def test_ensure_root_creates_only_when_used(clean_roots, tmp_path) -> None:
    clean_roots.setenv("FACTORY_AGENT_STEERING_DIR", str(tmp_path / "steering"))
    assert not resolve_root("steering").path.exists()
    assert ensure_root("steering").path.is_dir()


def test_ensure_root_fails_loudly_and_names_variable_and_path(clean_roots, tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    clean_roots.setenv("FACTORY_AGENT_SKILLS_DIR", str(blocker / "skills"))
    with pytest.raises(AuthoringRootUnavailable) as error:
        ensure_root("skills")
    assert error.value.variable == "FACTORY_AGENT_SKILLS_DIR"
    assert str(blocker / "skills") in str(error.value.path)
    assert "FACTORY_AGENT_SKILLS_DIR" in str(error.value)


def test_authoring_write_degrades_to_a_typed_error_and_reads_survive(
    clean_roots, tmp_path,
) -> None:
    """An unusable root must not take the read-only surface down with it."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    clean_roots.setenv("FACTORY_AGENT_SKILLS_DIR", str(blocker / "skills"))
    clean_roots.setenv("FACTORY_AGENT_STEERING_DIR", str(blocker / "steering"))
    clean_roots.setenv("FACTORY_AGENT_CONFIG_DIR", str(tmp_path / "agent-config"))
    clean_roots.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add,delete")
    clean_roots.setenv("FACTORY_AGENT_AUTHORING_STEERING", "all")
    from factory.agent.server import create_tool_catalog

    catalog = create_tool_catalog()

    def call(name: str, arguments: dict | None = None) -> dict:
        return asyncio.run(catalog.call_tool(name, arguments or {})).structured_content

    assert call("agent_add_skill", {
        "skill_id": "x", "name": "X", "description": "", "body": "b",
    })["error"] == "authoring_root_unavailable"
    assert call("agent_delete_skill", {"skill_id": "x"})["error"] == "authoring_root_unavailable"
    assert call("agent_create_steering", {
        "document_id": "x", "content": "# X",
    })["error"] == "authoring_root_unavailable"
    listed = call("agent_list_skills")
    assert listed["data"]["count"] >= 1  # packaged built-ins still served


def test_config_write_reports_an_unusable_root_at_use(clean_roots, tmp_path) -> None:
    """A config root that breaks AFTER registration must not fail generically."""
    import shutil

    root = tmp_path / "agent-config"
    clean_roots.setenv("FACTORY_AGENT_CONFIG_DIR", str(root))
    clean_roots.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "all")
    from factory.agent.server import create_tool_catalog

    catalog = create_tool_catalog()
    shutil.rmtree(root)
    root.write_text("not a directory")

    def call(name: str, arguments: dict) -> dict:
        return asyncio.run(catalog.call_tool(name, arguments)).structured_content

    for name, arguments in (
        ("write_settings", {"settings": {"a": 1}}),
        ("write_config", {"kind": "graph", "config": {
            "id": "g1", "name": "G", "nodes": [{"id": "n1", "type": "agent"}],
            "edges": [], "entry_points": ["n1"],
        }}),
        ("write_tool_module", {"module_name": "helper", "code": "x = 1"}),
    ):
        payload = call(name, arguments)["data"]["result"]
        assert payload["error"] == "authoring_root_unavailable", (name, payload)
        assert "FACTORY_AGENT_CONFIG_DIR" in payload["details"]
    # Reads and the probe keep answering off the same broken root.
    assert call("read_settings", {})["data"]["result"] == {"ok": True, "settings": {}}
    assert call("agent_authoring_capabilities", {})["data"]["config"]["write"] is True


def test_default_agent_reuses_a_durable_root_instead_of_a_temp_dir(
    clean_roots, tmp_path,
) -> None:
    from factory.agent.default_agent import get_default_agent

    clean_roots.chdir(tmp_path)
    first, second = get_default_agent(), get_default_agent()
    expected = (tmp_path / ".storage" / "agent-config").resolve()
    assert Path(first.config_dir) == expected and Path(second.config_dir) == expected
    assert expected.is_dir()
    assert "agent-default-" not in str(first.config_dir)
    assert packaged_skills_root().is_dir()
