from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = 1


class AuthoringSettings(BaseModel):
    enabled: bool = False


class Settings(BaseModel):
    service_name: str = Field(min_length=1)
    schema_version: int = Field(default=SCHEMA_VERSION)
    backend: str = Field(default="keycloak", min_length=1)
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)


class KeycloakBackendConfig(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION)
    kind: Literal["keycloak"]

    base_url: str = Field(min_length=1, description="Base URL, e.g. http://localhost:8180")
    realm: str = Field(min_length=1)

    issuer: str | None = None
    jwks_url: str | None = None

    # Client credentials for token operations (refresh, revoke, exchange)
    client_id: str | None = Field(default=None, description="OAuth2 client ID for token operations")
    client_secret: str | None = Field(default=None, description="OAuth2 client secret for token operations")

    default_audience: str | None = None
    tenant_claim: str = Field(default="tenant_id", min_length=1)

    allowed_algs: list[str] = Field(default_factory=lambda: ["RS256"])
    jwks_cache_ttl_seconds: int = Field(default=300, ge=0, le=3600)

    def effective_issuer(self) -> str:
        if self.issuer:
            return self.issuer.rstrip("/")
        return f"{self.base_url.rstrip('/')}/realms/{self.realm}"

    def effective_jwks_url(self) -> str:
        if self.jwks_url:
            return self.jwks_url
        return f"{self.effective_issuer()}/protocol/openid-connect/certs"

    def effective_token_url(self) -> str:
        """Token endpoint for refresh/exchange operations."""
        return f"{self.effective_issuer()}/protocol/openid-connect/token"

    def effective_revoke_url(self) -> str:
        """Revocation endpoint."""
        return f"{self.effective_issuer()}/protocol/openid-connect/revoke"

    def effective_userinfo_url(self) -> str:
        """UserInfo endpoint."""
        return f"{self.effective_issuer()}/protocol/openid-connect/userinfo"


class Principal(BaseModel):
    subject: str
    tenant_id: str | None = None
    username: str | None = None
    email: str | None = None
    scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


class TokenIntrospection(BaseModel):
    active: bool
    exp: int | None = None
    sub: str | None = None
    tenant_id: str | None = None
    error: str | None = None


class TokenResponse(BaseModel):
    """Response from token refresh/exchange operations."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None


class UserInfo(BaseModel):
    """User info from IdP userinfo endpoint."""
    sub: str
    preferred_username: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None


def scope_list_from_claims(claims: dict[str, Any]) -> list[str]:
    raw = claims.get("scope")
    if isinstance(raw, str):
        return [s for s in raw.split() if s]
    scp = claims.get("scp")
    if isinstance(scp, list) and all(isinstance(x, str) for x in scp):
        return list(scp)
    return []


def roles_from_claims(claims: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        rr = realm_access.get("roles")
        if isinstance(rr, list):
            roles.extend([r for r in rr if isinstance(r, str)])

    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        for _client, v in resource_access.items():
            if isinstance(v, dict):
                rr = v.get("roles")
                if isinstance(rr, list):
                    roles.extend([r for r in rr if isinstance(r, str)])

    # de-dupe stable
    return sorted(set(roles))
