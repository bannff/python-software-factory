"""AWS Cognito adapter — AuthBackend port via Cognito User Pools."""
from __future__ import annotations

import base64, hashlib, hmac, json, re, time, urllib.error
from typing import Any
from factory.auth.runtime.envelope import Envelope

def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        raise ImportError("pip install boto3 — required for AWS Cognito adapter")

_POOL_ID_RE = re.compile(r"^[\w-]+_[A-Za-z0-9]+$")
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
_JWKS_CACHE_TTL = 300

class CognitoAuthBackend:
    kind = "cognito"

    def __init__(self, user_pool_id: str, client_id: str, region: str = "us-east-1",
                 client_secret: str | None = None, domain: str | None = None,
                 redirect_uri: str | None = None, **kwargs: Any) -> None:
        _require_boto3()
        if not _POOL_ID_RE.match(user_pool_id):
            raise ValueError(f"Invalid user_pool_id: {user_pool_id!r}")
        if not _CLIENT_ID_RE.match(client_id):
            raise ValueError(f"Invalid client_id: {client_id!r}")
        import boto3
        self._client = boto3.client("cognito-idp", region_name=region)
        self._pool_id, self._client_id = user_pool_id, client_id
        self._client_secret, self._region = client_secret, region
        self._domain, self._redirect_uri = domain, redirect_uri
        self._issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    def _get_jwks(self) -> dict[str, Any]:
        now = time.time()
        if self._jwks_cache and (now - self._jwks_fetched_at) < _JWKS_CACHE_TTL:
            return self._jwks_cache
        import urllib.request
        with urllib.request.urlopen(self._jwks_url, timeout=10) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, dict) or "keys" not in data:
            raise ValueError("Invalid JWKS response")
        self._jwks_cache, self._jwks_fetched_at = data, now
        return data

    @property
    def _token_endpoint_url(self) -> str | None:
        if not self._domain:
            return None
        return f"https://{self._domain}.auth.{self._region}.amazoncognito.com/oauth2/token"

    def _secret_hash(self, username: str) -> str | None:
        if not self._client_secret:
            return None
        msg = username + self._client_id
        dig = hmac.new(self._client_secret.encode(), msg.encode(), hashlib.sha256).digest()
        return base64.b64encode(dig).decode()

    def health_check(self) -> dict[str, Any]:
        try:
            resp = self._client.describe_user_pool(UserPoolId=self._pool_id)
            return {"ok": True, "backend": "cognito",
                    "pool_name": resp.get("UserPool", {}).get("Name", "unknown")}
        except Exception as e:
            return {"ok": False, "backend": "cognito", "error": type(e).__name__}

    def verify_access_token(self, token: str, *, required_audience: str | None,
                            required_scopes: list[str] | None, envelope: Envelope) -> dict[str, Any]:
        try:
            import jwt as pyjwt
            header = pyjwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                return {"ok": False, "error": "missing_kid"}
            jwks = self._get_jwks()
            jwk_set = pyjwt.PyJWKSet.from_dict(jwks)
            matches = [k for k in jwk_set.keys if k.key_id == kid]
            if not matches:
                return {"ok": False, "error": "unknown_kid"}
            claims = pyjwt.decode(token, matches[0].key, algorithms=["RS256"],
                                  issuer=self._issuer, options={"verify_aud": False})
            if claims.get("token_use") != "access":
                return {"ok": False, "error": "invalid_token_use"}
            token_audience = claims.get("client_id") or claims.get("aud")
            if required_audience and token_audience != required_audience:
                return {"ok": False, "error": "audience_mismatch"}
            if required_scopes:
                missing = sorted(set(required_scopes) - set(claims.get("scope", "").split()))
                if missing:
                    return {"ok": False, "error": "missing_scopes", "missing": missing}
            return {"ok": True, "claims": claims, "principal": {
                "subject": claims.get("sub"),
                "tenant_id": (claims.get("cognito:groups") or [None])[0],
                "username": claims.get("username"),
                "scopes": claims.get("scope", "").split(),
                "roles": claims.get("cognito:groups", [])}}
        except Exception:
            return {"ok": False, "error": "invalid_token"}

    def introspect_token(self, token: str, *, envelope: Envelope) -> dict[str, Any]:
        v = self.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=envelope)
        if not v.get("ok"):
            return {"active": False, "error": str(v.get("error"))}
        c = v.get("claims", {})
        return {"active": True, "sub": c.get("sub"), "exp": c.get("exp"), "scope": c.get("scope")}

    def resolve_principal(self, *, envelope: Envelope) -> dict[str, Any]:
        if envelope.principal_id:
            return {"ok": True, "source": "envelope", "principal": {
                "subject": envelope.principal_id, "tenant_id": envelope.tenant_id}}
        return {"ok": True, "principal": None, "source": "unknown"}

    def refresh_token(self, refresh_token: str, *, scope: str | None = None,
                      envelope: Envelope) -> dict[str, Any]:
        try:
            params: dict[str, Any] = {
                "UserPoolId": self._pool_id, "ClientId": self._client_id,
                "AuthFlow": "REFRESH_TOKEN_AUTH",
                "AuthParameters": {"REFRESH_TOKEN": refresh_token}}
            sh = self._secret_hash(envelope.principal_id or "")
            if sh:
                params["AuthParameters"]["SECRET_HASH"] = sh
            resp = self._client.admin_initiate_auth(**params)
            r = resp.get("AuthenticationResult", {})
            return {"ok": True, "access_token": r.get("AccessToken"),
                    "token_type": r.get("TokenType", "Bearer"), "expires_in": r.get("ExpiresIn")}
        except Exception as e:
            return {"ok": False, "error": "refresh_failed", "details": type(e).__name__}

    def revoke_token(self, token: str, *, token_type_hint: str | None = None,
                     envelope: Envelope) -> dict[str, Any]:
        try:
            self._client.revoke_token(Token=token, ClientId=self._client_id)
            return {"ok": True, "revoked": True}
        except Exception as e:
            return {"ok": False, "error": "revocation_failed", "details": type(e).__name__}

    def get_user_info(self, access_token: str, *, envelope: Envelope) -> dict[str, Any]:
        try:
            resp = self._client.get_user(AccessToken=access_token)
            attrs = {a["Name"]: a["Value"] for a in resp.get("UserAttributes", [])}
            return {"ok": True, "user_info": {
                "username": resp.get("Username"), "attributes": attrs}}
        except Exception as e:
            return {"ok": False, "error": "userinfo_failed", "details": type(e).__name__}

    def exchange_token(self, subject_token: str, *, subject_token_type: str,
                       requested_token_type: str | None = None, audience: str | None = None,
                       scope: str | None = None, envelope: Envelope) -> dict[str, Any]:
        # For authorization_code flow, `audience` is repurposed as redirect_uri.
        if subject_token_type == "authorization_code":
            return self._exchange_auth_code(subject_token, redirect_uri=audience, scope=scope)
        return {"ok": False, "error": "not_supported",
                "details": f"Cognito does not support token exchange for type: {subject_token_type}"}

    def _exchange_auth_code(self, code: str, *, redirect_uri: str | None = None,
                            scope: str | None = None) -> dict[str, Any]:
        url = self._token_endpoint_url
        if not url:
            return {"ok": False, "error": "configuration_error",
                    "details": "domain not configured — required for authorization_code exchange"}
        ruri = redirect_uri or self._redirect_uri
        if not ruri:
            return {"ok": False, "error": "configuration_error",
                    "details": "redirect_uri required for authorization_code exchange"}
        body = (f"grant_type=authorization_code&code={code}"
                f"&client_id={self._client_id}&redirect_uri={ruri}")
        if self._client_secret:
            body += f"&client_secret={self._client_secret}"
        if scope:
            body += f"&scope={scope}"
        try:
            import urllib.request
            req = urllib.request.Request(url, data=body.encode(), method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                td = json.loads(resp.read())
            return {"ok": True, "access_token": td.get("access_token"),
                    "id_token": td.get("id_token"), "refresh_token": td.get("refresh_token"),
                    "token_type": td.get("token_type", "Bearer"), "expires_in": td.get("expires_in")}
        except urllib.error.HTTPError as e:
            err = json.loads(e.read()) if e.readable() else {}
            return {"ok": False, "error": err.get("error", "token_exchange_failed"),
                    "error_description": err.get("error_description", str(e))}
        except Exception as e:
            return {"ok": False, "error": "backend_error", "details": f"{type(e).__name__}: {e}"}

    def infrastructure_spec(self) -> dict[str, Any]:
        return {"provider": "aws", "service": "cognito-idp", "resources": [
            {"type": "AWS::Cognito::UserPool",
             "properties": {"UserPoolId": self._pool_id, "Region": self._region}},
            {"type": "AWS::Cognito::UserPoolClient",
             "properties": {"ClientId": self._client_id}}]}