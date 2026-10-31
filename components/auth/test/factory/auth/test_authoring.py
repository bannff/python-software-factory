from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from factory.auth.authoring import AuthoringError, AuthoringManager, authoring_enabled


def test_authoring_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_ENABLE_AUTHORING_TOOLS", raising=False)
    assert authoring_enabled({"authoring": {"enabled": False}}) is False


def test_authoring_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLE_AUTHORING_TOOLS", "1")
    assert authoring_enabled({"authoring": {"enabled": False}}) is True


def test_authoring_scoped_to_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLE_AUTHORING_TOOLS", "1")

    (tmp_path / "backends").mkdir(parents=True, exist_ok=True)
    mgr = AuthoringManager(tmp_path)

    with pytest.raises(AuthoringError):
        mgr.upsert_backend_config("../escape", {"kind": "keycloak"}, dry_run=True)

    ok = mgr.upsert_backend_config(
        "keycloak",
        yaml.safe_dump({"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"}),
        dry_run=True,
    )
    assert ok["ok"] is True

    # real write
    out = mgr.upsert_backend_config(
        "keycloak",
        {"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"},
        dry_run=False,
    )
    assert (tmp_path / "backends" / "keycloak.yaml").exists()
    assert out["ok"] is True

    deleted = mgr.delete_backend_config("keycloak")
    assert deleted["ok"] is True
    assert deleted["deleted"] is True


def test_authoring_validate_all_backends(tmp_path: Path) -> None:
    (tmp_path / "backends").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backends" / "keycloak.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"})
    )
    mgr = AuthoringManager(tmp_path)
    res = mgr.validate_all_backends(best_effort_network=False)
    assert res["ok"] is True
    assert res["count"] == 1
