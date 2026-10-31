"""Canonical gateway identity tests for AG-UI."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.mcp_utils.interface import get_service, set_service


class _Request:
    headers = {"authorization": "Bearer local-token"}


@pytest.mark.asyncio
async def test_gateway_verifier_identity_wins_without_auth_tool_fallback() -> None:
    from factory.api.runtime.ag_ui_identity import extract_identity

    class Verifier:
        async def verify_token(self, token: str):
            assert token == "local-token"
            return SimpleNamespace(
                subject="local-operator", claims={"tenant_id": "local"},
            )

    async def fallback(*_args):
        raise AssertionError("canonical verifier must win")

    previous = get_service("mcp_token_verifier")
    set_service("mcp_token_verifier", Verifier())
    try:
        assert await extract_identity(_Request(), fallback) == {
            "principal_id": "local-operator", "tenant_id": "local",
        }
    finally:
        set_service("mcp_token_verifier", previous)


@pytest.mark.asyncio
async def test_gateway_verifier_rejection_does_not_fall_back() -> None:
    from factory.api.runtime.ag_ui_identity import extract_identity

    class Verifier:
        async def verify_token(self, _token: str):
            return None

    async def fallback(*_args):
        raise AssertionError("rejected gateway tokens must stay rejected")

    previous = get_service("mcp_token_verifier")
    set_service("mcp_token_verifier", Verifier())
    try:
        assert await extract_identity(_Request(), fallback) is None
    finally:
        set_service("mcp_token_verifier", previous)
