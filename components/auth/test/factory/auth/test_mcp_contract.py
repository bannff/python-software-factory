from __future__ import annotations

from pathlib import Path

import yaml

from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server


def test_mcp_tool_names_stable(tmp_path: Path) -> None:
    (tmp_path / "backends").mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.yaml").write_text(
        yaml.safe_dump({"service_name": "svc", "schema_version": 1, "backend": "keycloak"})
    )
    (tmp_path / "backends" / "keycloak.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "kind": "keycloak", "base_url": "http://kc", "realm": "r"})
    )

    runtime = AuthRuntime(config_dir=tmp_path)
    mcp = create_mcp_server(runtime)

    # Best-effort: ensure deterministic tool names are present in capabilities
    caps = runtime.get_capabilities()
    assert "auth.get_capabilities" in caps["tools"]["deterministic"]
    assert "auth.verify_access_token" in caps["tools"]["operational"]
    assert mcp is not None
