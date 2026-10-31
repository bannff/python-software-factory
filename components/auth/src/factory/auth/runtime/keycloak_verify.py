"""Keycloak token verification and introspection."""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any, TYPE_CHECKING

import jwt

from .models import Principal, TokenIntrospection, roles_from_claims, scope_list_from_claims

if TYPE_CHECKING:
    import httpx
    from .models import KeycloakBackendConfig
    from .envelope import Envelope


@dataclass
class JwksCache:
    """JWKS cache with TTL."""
    jwks: dict[str, Any] | None = None
    fetched_at: float | None = None


class KeycloakVerifyOps:
    """Token verification mixin for KeycloakBackend."""

    cfg: "KeycloakBackendConfig"
    _http: "httpx.Client"
    _cache: JwksCache

    def _get_jwks(self) -> dict[str, Any]:
        """Fetch JWKS with caching based on TTL."""
        ttl = int(self.cfg.jwks_cache_ttl_seconds)
        now = time()
        if self._cache.jwks is not None and self._cache.fetched_at is not None:
            if ttl > 0 and (now - self._cache.fetched_at) < ttl:
                return self._cache.jwks

        resp = self._http.get(self.cfg.effective_jwks_url())
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "keys" not in data:
            raise ValueError("invalid_jwks")

        self._cache = JwksCache(jwks=data, fetched_at=now)
        return data

    def health_check(self) -> dict[str, Any]:
        """Check backend connectivity by fetching JWKS."""
        try:
            _ = self._get_jwks()
            return {"attempted": True, "ok": True, "jwks_url": self.cfg.effective_jwks_url()}
        except Exception as e:
            return {
                "attempted": True,
                "ok": False,
                "jwks_url": self.cfg.effective_jwks_url(),
                "error": f"{type(e).__name__}: {e}",
            }

    def verify_access_token(
        self,
        token: str,
        *,
        required_audience: str | None,
        required_scopes: list[str] | None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Verify JWT access token and extract claims."""
        try:
            jwks = self._get_jwks()
            unverified = jwt.get_unverified_header(token)
            kid = unverified.get("kid")
            if not kid:
                return {"ok": False, "error": "missing_kid"}

            jwk_set = jwt.PyJWKSet.from_dict(jwks)
            matches = [k for k in jwk_set.keys if k.key_id == kid]
            if not matches:
                return {"ok": False, "error": "unknown_kid"}
            key = matches[0].key

            audience = required_audience or self.cfg.default_audience
            options = {"verify_aud": audience is not None}

            claims = jwt.decode(
                token,
                key,
                algorithms=list(self.cfg.allowed_algs),
                audience=audience,
                issuer=self.cfg.effective_issuer(),
                options=options,
            )

            if not isinstance(claims, dict):
                return {"ok": False, "error": "invalid_claims"}

            scopes = scope_list_from_claims(claims)
            if required_scopes:
                missing = sorted(set(required_scopes) - set(scopes))
                if missing:
                    return {"ok": False, "error": "missing_scopes", "missing": missing}

            tenant_id = None
            if self.cfg.tenant_claim in claims and isinstance(claims.get(self.cfg.tenant_claim), str):
                tenant_id = claims.get(self.cfg.tenant_claim)

            if envelope.tenant_id and tenant_id and envelope.tenant_id != tenant_id:
                return {"ok": False, "error": "tenant_mismatch"}

            principal = Principal(
                subject=str(claims.get("sub")),
                tenant_id=tenant_id or envelope.tenant_id,
                username=claims.get("preferred_username") if isinstance(claims.get("preferred_username"), str) else None,
                email=claims.get("email") if isinstance(claims.get("email"), str) else None,
                scopes=scopes,
                roles=roles_from_claims(claims),
            )

            return {"ok": True, "principal": principal.model_dump(), "claims": claims}
        except jwt.ExpiredSignatureError:
            return {"ok": False, "error": "expired"}
        except jwt.InvalidAudienceError:
            return {"ok": False, "error": "audience_mismatch"}
        except jwt.InvalidIssuerError:
            return {"ok": False, "error": "issuer_mismatch"}
        except jwt.PyJWTError as e:
            return {"ok": False, "error": "invalid_token", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def introspect_token(self, token: str, *, envelope: "Envelope") -> dict[str, Any]:
        """Introspect token to check if active (local verification)."""
        verified = self.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=envelope
        )
        if not verified.get("ok"):
            return TokenIntrospection(active=False, error=str(verified.get("error"))).model_dump()

        claims = verified.get("claims")
        exp = claims.get("exp") if isinstance(claims, dict) else None
        sub = claims.get("sub") if isinstance(claims, dict) else None
        tenant_id = None
        if isinstance(claims, dict) and isinstance(claims.get(self.cfg.tenant_claim), str):
            tenant_id = claims.get(self.cfg.tenant_claim)

        return TokenIntrospection(
            active=True,
            exp=int(exp) if isinstance(exp, (int, float)) else None,
            sub=str(sub) if isinstance(sub, str) else None,
            tenant_id=tenant_id or envelope.tenant_id,
        ).model_dump()

    def resolve_principal(self, *, envelope: "Envelope") -> dict[str, Any]:
        """Resolve principal from envelope context."""
        principal_id = envelope.principal_id
        if principal_id:
            return {
                "ok": True,
                "principal": {
                    "subject": principal_id,
                    "tenant_id": envelope.tenant_id,
                    "username": None,
                    "email": None,
                    "scopes": [],
                    "roles": [],
                },
                "source": "envelope",
            }
        return {"ok": True, "principal": None, "source": "unknown"}
