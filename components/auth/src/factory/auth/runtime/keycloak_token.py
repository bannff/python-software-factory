"""Keycloak token operations (refresh, revoke, exchange)."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
    from .models import KeycloakBackendConfig
    from .envelope import Envelope


class KeycloakTokenOps:
    """Token operations mixin for KeycloakBackend."""

    cfg: "KeycloakBackendConfig"
    _http: "httpx.Client"

    def _get_client_auth(self) -> dict[str, str]:
        """Get client credentials for token endpoint requests."""
        if not self.cfg.client_id:
            raise ValueError("client_id not configured")
        auth = {"client_id": self.cfg.client_id}
        if self.cfg.client_secret:
            auth["client_secret"] = self.cfg.client_secret
        return auth

    def _post_token_endpoint(self, data: dict[str, str]) -> "httpx.Response":
        """POST to token endpoint with form data."""
        return self._http.post(
            self.cfg.effective_token_url(),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def refresh_token(
        self,
        refresh_token: str,
        *,
        scope: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Exchange refresh token for new access token."""
        try:
            auth = self._get_client_auth()
            data = {**auth, "grant_type": "refresh_token", "refresh_token": refresh_token}
            if scope:
                data["scope"] = scope

            resp = self._post_token_endpoint(data)

            if resp.status_code >= 400:
                error_data = resp.json() if resp.content else {}
                return {
                    "ok": False,
                    "error": error_data.get("error", "token_refresh_failed"),
                    "error_description": error_data.get("error_description"),
                }

            token_data = resp.json()
            return {
                "ok": True,
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in"),
                "scope": token_data.get("scope"),
            }
        except ValueError as e:
            return {"ok": False, "error": "configuration_error", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def revoke_token(
        self,
        token: str,
        *,
        token_type_hint: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Revoke an access or refresh token."""
        try:
            auth = self._get_client_auth()
            data = {**auth, "token": token}
            if token_type_hint:
                data["token_type_hint"] = token_type_hint

            resp = self._http.post(
                self.cfg.effective_revoke_url(),
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if resp.status_code == 200:
                return {"ok": True, "revoked": True}

            error_data = resp.json() if resp.content else {}
            return {
                "ok": False,
                "error": error_data.get("error", "revocation_failed"),
                "error_description": error_data.get("error_description"),
            }
        except ValueError as e:
            return {"ok": False, "error": "configuration_error", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def exchange_token(
        self,
        subject_token: str,
        *,
        subject_token_type: str,
        requested_token_type: str | None = None,
        audience: str | None = None,
        scope: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Exchange one token for another (RFC 8693)."""
        try:
            auth = self._get_client_auth()
            data = {
                **auth,
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": subject_token,
                "subject_token_type": subject_token_type,
            }
            if requested_token_type:
                data["requested_token_type"] = requested_token_type
            if audience:
                data["audience"] = audience
            if scope:
                data["scope"] = scope

            resp = self._post_token_endpoint(data)

            if resp.status_code >= 400:
                error_data = resp.json() if resp.content else {}
                return {
                    "ok": False,
                    "error": error_data.get("error", "token_exchange_failed"),
                    "error_description": error_data.get("error_description"),
                }

            token_data = resp.json()
            return {
                "ok": True,
                "access_token": token_data.get("access_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in"),
                "scope": token_data.get("scope"),
                "issued_token_type": token_data.get("issued_token_type"),
            }
        except ValueError as e:
            return {"ok": False, "error": "configuration_error", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def get_user_info(self, access_token: str, *, envelope: "Envelope") -> dict[str, Any]:
        """Get user info from IdP userinfo endpoint."""
        try:
            resp = self._http.get(
                self.cfg.effective_userinfo_url(),
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if resp.status_code == 401:
                return {"ok": False, "error": "invalid_token"}

            if resp.status_code >= 400:
                error_data = resp.json() if resp.content else {}
                return {
                    "ok": False,
                    "error": error_data.get("error", "userinfo_failed"),
                    "error_description": error_data.get("error_description"),
                }

            return {"ok": True, "user_info": resp.json()}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}
