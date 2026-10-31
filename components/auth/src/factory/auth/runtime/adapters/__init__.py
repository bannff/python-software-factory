"""Auth backend adapters.

This module provides pluggable authentication backends:
- MemoryBackend: In-memory mock for testing (default)
- KeycloakBackend: Production Keycloak integration
- AuthlibKeycloakBackend: Keycloak via Authlib (alternative client)
- CognitoAuthBackend: AWS Cognito integration

Usage:
    from factory.auth.runtime.adapters import create_backend, MemoryBackend
    
    # For testing (default)
    backend = create_backend()
    
    # For production (Keycloak)
    backend = create_backend("keycloak", config=keycloak_config)
    
    # For AWS (Cognito)
    backend = create_backend("aws", config={"user_pool_id": "...", "region": "us-east-1"})
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .base import AuthBackend
from .memory import MemoryBackend

if TYPE_CHECKING:
    from factory.auth.runtime.models import KeycloakBackendConfig

__all__ = ["AuthBackend", "MemoryBackend", "create_backend"]


def create_backend(
    backend_type: str = "memory",
    *,
    config: "KeycloakBackendConfig | dict[str, Any] | None" = None,
) -> AuthBackend:
    """Factory function to create authentication backends.
    
    Args:
        backend_type: Type of backend ("memory", "keycloak", "authlib_keycloak", or "aws")
        config: Backend configuration. Required for keycloak/authlib_keycloak
            (KeycloakBackendConfig) and aws (dict with Cognito settings).
    
    Returns:
        An AuthBackend implementation
    
    Raises:
        ValueError: If backend_type is unsupported or config is missing when required
    """
    if backend_type == "memory":
        return MemoryBackend()
    
    if backend_type == "keycloak":
        if config is None:
            raise ValueError("KeycloakBackendConfig required for keycloak backend")
        # Lazy import to avoid loading keycloak dependencies when not needed
        from .keycloak import KeycloakBackend
        return KeycloakBackend(config)
    
    if backend_type == "authlib_keycloak":
        if config is None:
            raise ValueError("KeycloakBackendConfig required for authlib_keycloak backend")
        from .authlib_keycloak import AuthlibKeycloakBackend
        return AuthlibKeycloakBackend(config)

    if backend_type == "aws":
        from .aws import CognitoAuthBackend
        if isinstance(config, dict):
            kwargs = {k: v for k, v in config.items() if k != "kind"}
            return CognitoAuthBackend(**kwargs)
        return CognitoAuthBackend(**(config.model_dump() if config else {}))

    raise ValueError(f"Unsupported backend type: {backend_type}")
