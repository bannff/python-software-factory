"""Keycloak backend implementation.

This module implements the AuthBackend protocol for Keycloak.
Composed from focused mixin classes for maintainability.
"""
from __future__ import annotations

from typing import Any

import httpx

from .envelope import Envelope
from .models import KeycloakBackendConfig
from .keycloak_verify import KeycloakVerifyOps, JwksCache
from .keycloak_token import KeycloakTokenOps


class KeycloakBackend(KeycloakVerifyOps, KeycloakTokenOps):
    """Keycloak authentication backend.
    
    Implements all AuthBackend protocol methods for Keycloak IdP.
    Composed from:
    - KeycloakVerifyOps: Token verification, introspection, principal resolution
    - KeycloakTokenOps: Token refresh, revoke, exchange, userinfo
    """
    kind = "keycloak"

    def __init__(self, cfg: KeycloakBackendConfig, *, http: httpx.Client | None = None):
        self.cfg = cfg
        self._http = http or httpx.Client(timeout=10.0)
        self._cache = JwksCache()
