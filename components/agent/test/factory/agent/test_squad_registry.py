"""Tests for SquadRegistry + squad authoring (create/delete, disk overlay)."""
from __future__ import annotations

import pytest
import yaml

from factory.agent.authoring.manager import AuthoringManager
from factory.agent.authoring.validation import validate_config
from factory.agent.registry.squads import SquadRegistry


def _squad_dict(squad_id: str = "py-squad") -> dict:
    return {
        "id": squad_id, "kind": "squad", "name": "Py Squad",
        "target_language": "python", "sandbox_profile": "python-sdk",
        "team": {
            "kind": "graph", "id": "py-team", "name": "Py Team",
            "nodes": [{"id": "editor", "type": "agent", "agent_id": "developer"}],
            "entry_points": ["editor"],
        },
        "toolbelt": {"tools": ["shell", "grep"]},
    }


@pytest.mark.asyncio
async def test_builtin_rust_squad_loads(tmp_path):
    reg = SquadRegistry(tmp_path / "squads")
    await reg.load()
    assert reg.get("rust-squad") is not None
    assert reg.get("rust-squad").sandbox_profile == "rust-sdk"
    assert any(s["id"] == "rust-squad" for s in reg.list_squads())


@pytest.mark.asyncio
async def test_disk_squad_overlays_builtins(tmp_path):
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    (squads_dir / "py-squad.yaml").write_text(yaml.safe_dump(_squad_dict()))
    reg = SquadRegistry(squads_dir)
    await reg.load()
    assert reg.get("py-squad") is not None            # user squad loaded
    assert reg.get("rust-squad") is not None            # built-in still present


@pytest.mark.asyncio
async def test_user_squad_cannot_shadow_builtin(tmp_path):
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    shadow = _squad_dict("rust-squad")
    shadow["sandbox_profile"] = "evil-override"
    (squads_dir / "rust-squad.yaml").write_text(yaml.safe_dump(shadow))
    reg = SquadRegistry(squads_dir)
    await reg.load()
    # built-in wins — the override is ignored
    assert reg.get("rust-squad").sandbox_profile == "rust-sdk"


@pytest.mark.asyncio
async def test_bad_squad_file_is_skipped(tmp_path):
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    (squads_dir / "broken.yaml").write_text("id: broken\nkind: squad\n")  # missing required
    reg = SquadRegistry(squads_dir)
    await reg.load()
    assert reg.get("broken") is None
    assert reg.get("rust-squad") is not None  # loading continued


def test_validate_config_accepts_squad_kind():
    assert validate_config("squad", _squad_dict())["ok"] is True
    bad = _squad_dict()
    del bad["sandbox_profile"]
    assert validate_config("squad", bad)["ok"] is False


def test_authoring_manager_writes_squad_subdir(tmp_path):
    mgr = AuthoringManager(tmp_path)
    res = mgr.write_yaml_config("squad", _squad_dict())
    assert res["ok"] is True
    assert res["path"].endswith("squads/py-squad.yaml")
    # round-trips through the registry
    assert (tmp_path / "squads" / "py-squad.yaml").exists()
    got = mgr.read_yaml_config("squad", "py-squad")
    assert got["sandbox_profile"] == "python-sdk"
    assert mgr.delete_yaml_config("squad", "py-squad")["ok"] is True
