from __future__ import annotations

from pathlib import Path

import yaml

from factory.auth.runtime.runtime import AuthRuntime


def test_runtime_config_and_schema(tmp_path: Path) -> None:
    (tmp_path / "backends").mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.yaml").write_text(
        yaml.safe_dump({"service_name": "svc", "schema_version": 1, "backend": "keycloak"})
    )
    (tmp_path / "backends" / "keycloak.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"})
    )

    runtime = AuthRuntime(config_dir=tmp_path)
    caps = runtime.get_capabilities()
    assert "supported_backends" in caps

    schema = runtime.describe_config_schema()
    assert schema["schema_version"] == 1
