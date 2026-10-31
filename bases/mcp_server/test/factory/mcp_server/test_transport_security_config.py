"""Tests for env-driven DNS-rebinding allowlist resolution."""

from __future__ import annotations

from factory.mcp_server.runtime.transport_security_config import resolve_transport_security


def test_unset_defers_to_sdk_default() -> None:
    """No env var ⇒ None ⇒ byte-identical SDK localhost auto-protection."""
    assert resolve_transport_security({}) is None
    assert resolve_transport_security({"MCP_ALLOWED_HOSTS": "   "}) is None


def test_star_disables_protection() -> None:
    settings = resolve_transport_security({"MCP_ALLOWED_HOSTS": "*"})
    assert settings is not None
    assert settings.enable_dns_rebinding_protection is False


def test_extends_allowlist_without_dropping_localhost() -> None:
    settings = resolve_transport_security(
        {"MCP_ALLOWED_HOSTS": "companionx:*, host.docker.internal:8000"},
    )
    assert settings.enable_dns_rebinding_protection is True
    # localhost defaults preserved (no local-dev regression)
    assert "127.0.0.1:*" in settings.allowed_hosts
    assert "localhost:*" in settings.allowed_hosts
    # operator-supplied hosts appended
    assert "companionx:*" in settings.allowed_hosts
    assert "host.docker.internal:8000" in settings.allowed_hosts
    # origins carry http + https forms of each extra host
    assert "http://companionx:*" in settings.allowed_origins
    assert "https://companionx:*" in settings.allowed_origins


def test_allowlist_is_deduped() -> None:
    settings = resolve_transport_security({"MCP_ALLOWED_HOSTS": "localhost:*, companionx:*, companionx:*"})
    assert settings.allowed_hosts.count("companionx:*") == 1
    assert settings.allowed_hosts.count("localhost:*") == 1
