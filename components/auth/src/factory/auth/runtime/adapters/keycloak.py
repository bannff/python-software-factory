"""Keycloak backend adapter.

Re-exports the KeycloakBackend from the runtime module.
This adapter connects to a real Keycloak server for production use.
"""
from __future__ import annotations

from factory.auth.runtime.keycloak import KeycloakBackend

__all__ = ["KeycloakBackend"]
