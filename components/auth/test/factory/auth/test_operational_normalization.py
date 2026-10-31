"""Focused safety tests for Auth operational typed response normalization."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server

_SECRET = "qa-access-token"
_TOOL_ARGS = {
    "auth.verify_access_token": {"token": _SECRET},
    "auth.introspect_token": {"token": _SECRET},
    "auth.resolve_principal": {},
    "auth.refresh_token": {"refresh_token": _SECRET},
    "auth.revoke_token": {"token": _SECRET},
    "auth.get_user_info": {"access_token": _SECRET},
    "auth.exchange_token": {
        "subject_token": _SECRET, "subject_token_type": "access_token",
    },
}
_EXPECTED_ERRORS = [
    ("auth.verify_access_token", code)
    for code in (
        "backend_not_configured", "invalid_token", "token_revoked", "expired",
        "audience_mismatch", "missing_scopes", "user_not_found", "tenant_mismatch",
        "missing_kid", "unknown_kid", "invalid_claims", "issuer_mismatch",
        "invalid_token_use",
    )
] + [
    ("auth.introspect_token", "invalid_or_expired"),
    ("auth.refresh_token", "invalid_refresh_token"),
    ("auth.refresh_token", "refresh_failed"),
    ("auth.refresh_token", "configuration_error"),
    ("auth.refresh_token", "token_refresh_failed"),
    ("auth.revoke_token", "revocation_failed"),
    ("auth.exchange_token", "invalid_subject_token"),
    ("auth.exchange_token", "not_supported"),
    ("auth.exchange_token", "token_exchange_failed"),
    ("auth.get_user_info", "userinfo_failed"),
]


class _ResponseBackend:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def __getattr__(self, _: str):
        return lambda *args, **kwargs: dict(self._response)


class _ExplodingBackend:
    def __getattr__(self, _: str):
        def raise_secret(*args, **kwargs):
            raise RuntimeError(f"Bearer {_SECRET}")
        return raise_secret


def _tool(server, name: str):
    return asyncio.run(server.get_tool(name)).fn


def _server(tmp_path: Path):
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(
        yaml.safe_dump({"service_name": "auth-normalization-test", "backend": "memory"})
    )
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = AuthRuntime(tmp_path)
    return create_mcp_server(runtime), runtime


@pytest.mark.parametrize(("tool_name", "error"), _EXPECTED_ERRORS)
def test_every_expected_operational_error_is_safe_success_data(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, tool_name: str, error: str,
) -> None:
    server, runtime = _server(tmp_path)
    runtime._backend = _ResponseBackend({"ok": False, "error": error, "details": f"Bearer {_SECRET}"})

    with caplog.at_level(logging.ERROR):
        result = _tool(server, tool_name)(**_TOOL_ARGS[tool_name])

    assert result.ok is True
    assert result.data is not None and result.data.ok is False
    assert result.data.error == error
    assert _SECRET not in result.model_dump_json()
    assert _SECRET not in caplog.text


@pytest.mark.parametrize("tool_name", list(_TOOL_ARGS))
def test_empty_provider_errors_use_operation_safe_fallback(
    tmp_path: Path, tool_name: str,
) -> None:
    server, runtime = _server(tmp_path)
    runtime._backend = _ResponseBackend({"ok": False, "error": "", "details": f"Bearer {_SECRET}"})

    result = _tool(server, tool_name)(**_TOOL_ARGS[tool_name])

    assert result.ok is True and result.data is not None and result.data.ok is False
    assert result.data.error is not None
    assert _SECRET not in result.model_dump_json()


@pytest.mark.parametrize("tool_name", list(_TOOL_ARGS))
def test_every_operational_exception_path_is_secret_safe(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, tool_name: str,
) -> None:
    server, runtime = _server(tmp_path)
    runtime._backend = _ExplodingBackend()

    with caplog.at_level(logging.ERROR):
        result = _tool(server, tool_name)(**_TOOL_ARGS[tool_name])

    assert result.ok is False and result.data is None
    assert result.error == "tool_execution_failed"
    assert _SECRET not in result.model_dump_json()
    assert _SECRET not in caplog.text
    assert "typed_mcp_tool_execution_failed tool=factory.auth.mcp.operational" in caplog.text
