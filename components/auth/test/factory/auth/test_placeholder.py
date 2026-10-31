from __future__ import annotations

from pathlib import Path

import yaml

from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server


def test_server_creates(tmp_path: Path) -> None:
    (tmp_path / "backends").mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.yaml").write_text(
        yaml.safe_dump({"service_name": "test", "schema_version": 1, "backend": "keycloak"})
    )
    (tmp_path / "backends" / "keycloak.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"})
    )

    runtime = AuthRuntime(config_dir=tmp_path)
    mcp = create_mcp_server(runtime)
    assert mcp is not None
