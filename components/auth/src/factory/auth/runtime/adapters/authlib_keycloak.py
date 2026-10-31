"""Authlib-backed Keycloak adapter.

Uses `authlib` for JWKS fetching and JWT verification instead of
hand-rolling PyJWT key selection + decode.
"""
from __future__ import annotations

from time import time
from typing import Any

import httpx
from authlib.jose import JsonWebKey, jwt as authlib_jwt
from authlib.jose.errors import JoseError

from factory.auth.runtime.envelope import Envelope
from factory.auth.runtime.models import (
    KeycloakBackendConfig, Principal, TokenIntrospection,
    roles_from_claims, scope_list_from_claims,
)


class AuthlibKeycloakBackend:
    """Keycloak backend using authlib for JWKS/JWT handling."""

    kind = "authlib_keycloak"

    def __init__(self, cfg: KeycloakBackendConfig, *, http: httpx.Client | None = None) -> None:
        self.cfg = cfg
        self._http = http or httpx.Client(timeout=10.0)
        self._jwks: Any = None
        self._jwks_at: float | None = None

    def _get_jwks(self) -> Any:
        ttl = int(self.cfg.jwks_cache_ttl_seconds)
        now = time()
        if self._jwks and self._jwks_at and ttl > 0 and (now - self._jwks_at) < ttl:
            return self._jwks
        resp = self._http.get(self.cfg.effective_jwks_url())
        resp.raise_for_status()
        self._jwks = JsonWebKey.import_key_set(resp.json())
        self._jwks_at = now
        return self._jwks

    def health_check(self) -> dict[str, Any]:
        try:
            self._get_jwks()
            return {"attempted": True, "ok": True, "jwks_url": self.cfg.effective_jwks_url()}
        except Exception as e:
            return {"attempted": True, "ok": False, "jwks_url": self.cfg.effective_jwks_url(),
                    "error": f"{type(e).__name__}: {e}"}

    def verify_access_token(self, token: str, *, required_audience: str | None,
                            required_scopes: list[str] | None, envelope: Envelope) -> dict[str, Any]:
        try:
            claims = authlib_jwt.decode(token, self._get_jwks())
            opts: dict[str, Any] = {}
            aud = required_audience or self.cfg.default_audience
            if aud:
                opts["aud"] = {"essential": True, "value": aud}
            iss = self.cfg.effective_issuer()
            if iss:
                opts["iss"] = {"essential": True, "value": iss}
            claims.validate(opts)
            scopes = scope_list_from_claims(dict(claims))
            if required_scopes:
                missing = sorted(set(required_scopes) - set(scopes))
                if missing:
                    return {"ok": False, "error": "missing_scopes", "missing": missing}
            tc = self.cfg.tenant_claim
            tenant_id = claims.get(tc) if tc in claims and isinstance(claims.get(tc), str) else None
            if envelope.tenant_id and tenant_id and envelope.tenant_id != tenant_id:
                return {"ok": False, "error": "tenant_mismatch"}
            principal = Principal(
                subject=str(claims.get("sub")), tenant_id=tenant_id or envelope.tenant_id,
                username=claims.get("preferred_username") if isinstance(claims.get("preferred_username"), str) else None,
                email=claims.get("email") if isinstance(claims.get("email"), str) else None,
                scopes=scopes, roles=roles_from_claims(dict(claims)),
            )
            return {"ok": True, "principal": principal.model_dump(), "claims": dict(claims)}
        except JoseError as e:
            return {"ok": False, "error": "invalid_token", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def introspect_token(self, token: str, *, envelope: Envelope) -> dict[str, Any]:
        v = self.verify_access_token(token, required_audience=None, required_scopes=None, envelope=envelope)
        if not v.get("ok"):
            return TokenIntrospection(active=False, error=str(v.get("error"))).model_dump()
        c = v.get("claims", {})
        return TokenIntrospection(
            active=True, exp=int(c["exp"]) if isinstance(c.get("exp"), (int, float)) else None,
            sub=str(c["sub"]) if isinstance(c.get("sub"), str) else None,
            tenant_id=c.get(self.cfg.tenant_claim) or envelope.tenant_id,
        ).model_dump()

    def resolve_principal(self, *, envelope: Envelope) -> dict[str, Any]:
        if envelope.principal_id:
            return {"ok": True, "source": "envelope", "principal": {
                "subject": envelope.principal_id, "tenant_id": envelope.tenant_id,
                "username": None, "email": None, "scopes": [], "roles": []}}
        return {"ok": True, "principal": None, "source": "unknown"}

    def _client_auth(self) -> dict[str, str]:
        if not self.cfg.client_id:
            raise ValueError("client_id not configured")
        auth: dict[str, str] = {"client_id": self.cfg.client_id}
        if self.cfg.client_secret:
            auth["client_secret"] = self.cfg.client_secret
        return auth

    def _post_token(self, data: dict[str, str]) -> httpx.Response:
        return self._http.post(self.cfg.effective_token_url(), data=data,
                               headers={"Content-Type": "application/x-www-form-urlencoded"})

    def _token_error(self, resp: httpx.Response, fallback: str) -> dict[str, Any]:
        err = resp.json() if resp.content else {}
        return {"ok": False, "error": err.get("error", fallback),
                "error_description": err.get("error_description")}

    def refresh_token(self, refresh_token: str, *, scope: str | None = None,
                      envelope: Envelope) -> dict[str, Any]:
        try:
            data = {**self._client_auth(), "grant_type": "refresh_token", "refresh_token": refresh_token}
            if scope:
                data["scope"] = scope
            resp = self._post_token(data)
            if resp.status_code >= 400:
                return self._token_error(resp, "token_refresh_failed")
            td = resp.json()
            return {"ok": True, "access_token": td.get("access_token"),
                    "refresh_token": td.get("refresh_token"), "token_type": td.get("token_type", "Bearer"),
                    "expires_in": td.get("expires_in"), "scope": td.get("scope")}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def revoke_token(self, token: str, *, token_type_hint: str | None = None,
                     envelope: Envelope) -> dict[str, Any]:
        try:
            data = {**self._client_auth(), "token": token}
            if token_type_hint:
                data["token_type_hint"] = token_type_hint
            resp = self._http.post(self.cfg.effective_revoke_url(), data=data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded"})
            if resp.status_code == 200:
                return {"ok": True, "revoked": True}
            return self._token_error(resp, "revocation_failed")
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def exchange_token(self, subject_token: str, *, subject_token_type: str,
                       requested_token_type: str | None = None, audience: str | None = None,
                       scope: str | None = None, envelope: Envelope) -> dict[str, Any]:
        try:
            data = {**self._client_auth(),
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "subject_token": subject_token, "subject_token_type": subject_token_type}
            for k, v in [("requested_token_type", requested_token_type),
                         ("audience", audience), ("scope", scope)]:
                if v:
                    data[k] = v
            resp = self._post_token(data)
            if resp.status_code >= 400:
                return self._token_error(resp, "token_exchange_failed")
            td = resp.json()
            return {"ok": True, "access_token": td.get("access_token"),
                    "token_type": td.get("token_type", "Bearer"), "expires_in": td.get("expires_in"),
                    "scope": td.get("scope"), "issued_token_type": td.get("issued_token_type")}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def get_user_info(self, access_token: str, *, envelope: Envelope) -> dict[str, Any]:
        try:
            resp = self._http.get(self.cfg.effective_userinfo_url(),
                                  headers={"Authorization": f"Bearer {access_token}"})
            if resp.status_code == 401:
                return {"ok": False, "error": "invalid_token"}
            if resp.status_code >= 400:
                return self._token_error(resp, "userinfo_failed")
            return {"ok": True, "user_info": resp.json()}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}
