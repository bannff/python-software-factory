"""Security regression coverage for public Auth MCP payloads."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server


def _server(tmp_path: Path):
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(
        yaml.safe_dump({"service_name": "auth-payload-test", "backend": "memory"})
    )
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = AuthRuntime(tmp_path)
    return create_mcp_server(runtime), runtime


def _tool(server: Any, name: str) -> Any:
    return asyncio.run(server.get_tool(name))


def test_successful_opaque_payloads_omit_nested_secrets_and_diagnostics(
    tmp_path: Path,
) -> None:
    server, runtime = _server(tmp_path)

    class LeakyBackend:
        def verify_access_token(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "ok": True,
                "principal": {"subject": "u1"},
                "claims": {
                    "sub": "u1", "token_use": "access", "accessToken": "secret",
                    "accessTokens": "secret", "secrets": "secret", "diagnostic": "secret",
                    "errorDescriptions": "secret", "tracebacks": "secret",
                    "nested": {"refresh_token": "secret", "exceptions": "secret", "email": "u1@example.test"},
                    "items": [{"traceback": "secret", "name": "safe"}],
                },
            }

        def get_user_info(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "ok": True,
                "user_info": {
                    "email_verified": True,
                    "attributes": {"email": "u1@example.test", "id_token": "secret"},
                    "error-description": "secret", "diagnostics": "secret",
                    "nested": {"exception": "secret", "name": "safe"},
                },
            }

    runtime._backend = LeakyBackend()
    verified = _tool(server, "auth.verify_access_token").fn(token="secret-token")
    info = _tool(server, "auth.get_user_info").fn(access_token="secret-token")

    assert verified.ok and verified.data is not None
    assert verified.data.claims == {
        "sub": "u1", "token_use": "access",
        "nested": {"email": "u1@example.test"}, "items": [{"name": "safe"}],
    }
    assert info.ok and info.data is not None
    assert info.data.user_info == {
        "email_verified": True, "attributes": {"email": "u1@example.test"},
        "nested": {"name": "safe"},
    }
    assert "secret" not in verified.model_dump_json()
    assert "secret" not in info.model_dump_json()
