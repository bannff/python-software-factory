from __future__ import annotations

from pathlib import Path

import yaml

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.runtime import PermissionsRuntime


def _write_min_config(cfg: Path) -> None:
    (cfg / "policies").mkdir(parents=True, exist_ok=True)
    (cfg / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "service_name": "svc",
                "backend": "filesystem",
                "authoring": {"enabled": False},
                "policy_store": {"policies_subdir": "policies"},
            }
        )
    )


def test_default_deny_without_policies(tmp_path: Path) -> None:
    _write_min_config(tmp_path)
    runtime = PermissionsRuntime.from_config_dir(tmp_path)

    out = runtime.evaluate(
        action="read",
        resource={"type": "document", "id": "doc-1", "visibility": "private"},
        context={},
        envelope=Envelope(),
    )
    assert out["decision"] == "deny"


def test_allow_rule_matches(tmp_path: Path) -> None:
    _write_min_config(tmp_path)
    (tmp_path / "policies" / "p.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "id": "p",
                "name": "P",
                "version": "0.1",
                "rules": [
                    {
                        "id": "allow_public",
                        "effect": "allow",
                        "actions": ["read"],
                        "resource_types": ["document"],
                        "conditions": [
                            {"key": "resource.visibility", "op": "eq", "value": "public"}
                        ],
                    }
                ],
            }
        )
    )

    runtime = PermissionsRuntime.from_config_dir(tmp_path)

    out = runtime.evaluate(
        action="read",
        resource={"type": "document", "id": "doc-1", "visibility": "public"},
        context={},
        envelope=Envelope(),
    )
    assert out["decision"] == "allow"
