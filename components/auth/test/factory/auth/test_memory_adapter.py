"""Tests for the in-memory authentication backend adapter."""
from __future__ import annotations

import pytest

from factory.auth.runtime.adapters import MemoryBackend, create_backend
from factory.auth.runtime.envelope import parse_envelope


class TestMemoryBackendFactory:
    """Tests for the backend factory function."""

    def test_create_memory_backend_default(self) -> None:
        backend = create_backend()
        assert isinstance(backend, MemoryBackend)
        assert backend.kind == "memory"

    def test_create_memory_backend_explicit(self) -> None:
        backend = create_backend("memory")
        assert isinstance(backend, MemoryBackend)

    def test_create_unsupported_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported backend type"):
            create_backend("unknown")


class TestMemoryBackendHealthCheck:
    """Tests for health check functionality."""

    def test_health_check_returns_ok(self) -> None:
        backend = MemoryBackend()
        result = backend.health_check()
        assert result["ok"] is True
        assert result["backend"] == "memory"
        assert result["users_count"] == 0
        assert result["tokens_count"] == 0


class TestMemoryBackendTokenVerification:
    """Tests for token verification."""

    def test_verify_valid_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", email="test@example.com", scopes=["read", "write"])
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.verify_access_token(token, required_audience=None, required_scopes=None, envelope=env)

        assert result["ok"] is True
        assert result["principal"]["subject"] == "user-1"
        assert result["principal"]["username"] == "testuser"
        assert result["claims"]["sub"] == "user-1"

    def test_verify_token_with_required_scopes(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", scopes=["read", "write"])
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.verify_access_token(token, required_audience=None, required_scopes=["read"], envelope=env)
        assert result["ok"] is True

        result = backend.verify_access_token(token, required_audience=None, required_scopes=["admin"], envelope=env)
        assert result["ok"] is False
        assert result["error"] == "missing_scopes"
        assert "admin" in result["missing"]

    def test_verify_invalid_token(self) -> None:
        backend = MemoryBackend()
        env = parse_envelope(None)
        result = backend.verify_access_token("invalid-token", required_audience=None, required_scopes=None, envelope=env)
        assert result["ok"] is False
        assert result["error"] == "invalid_token"

    def test_verify_expired_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser")
        token, _ = backend.create_token("user-1", ttl=-1)

        env = parse_envelope(None)
        result = backend.verify_access_token(token, required_audience=None, required_scopes=None, envelope=env)
        assert result["ok"] is False
        assert result["error"] == "expired"

    def test_verify_token_tenant_mismatch(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", tenant_id="tenant-a")
        token, _ = backend.create_token("user-1")

        env = parse_envelope({"tenant_id": "tenant-b"})
        result = backend.verify_access_token(token, required_audience=None, required_scopes=None, envelope=env)
        assert result["ok"] is False
        assert result["error"] == "tenant_mismatch"


class TestMemoryBackendIntrospection:
    """Tests for token introspection."""

    def test_introspect_valid_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", tenant_id="tenant-a")
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.introspect_token(token, envelope=env)

        assert result["active"] is True
        assert result["sub"] == "user-1"
        assert result["tenant_id"] == "tenant-a"

    def test_introspect_invalid_token(self) -> None:
        backend = MemoryBackend()
        env = parse_envelope(None)
        result = backend.introspect_token("invalid-token", envelope=env)
        assert result["active"] is False


class TestMemoryBackendResolvePrincipal:
    """Tests for principal resolution."""

    def test_resolve_principal_from_envelope(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", email="test@example.com", roles=["admin"])

        env = parse_envelope({"principal_id": "user-1", "tenant_id": "tenant-a"})
        result = backend.resolve_principal(envelope=env)

        assert result["ok"] is True
        assert result["principal"]["subject"] == "user-1"
        assert result["principal"]["username"] == "testuser"
        assert result["source"] == "memory"

    def test_resolve_principal_unknown(self) -> None:
        backend = MemoryBackend()
        env = parse_envelope(None)
        result = backend.resolve_principal(envelope=env)

        assert result["ok"] is True
        assert result["principal"] is None
        assert result["source"] == "unknown"
