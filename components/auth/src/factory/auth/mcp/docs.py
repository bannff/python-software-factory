"""Documentation content for auth MCP resources."""

from __future__ import annotations

OVERVIEW_DOC = """# Auth Brick

Authentication and authorization via Keycloak (or compatible OIDC providers).

## Key Concepts

### Backends
Auth backends (Keycloak) handle token verification, introspection, and exchange.
Each backend has configuration for issuer, JWKS URL, and client credentials.

### Tokens
- Access tokens: Short-lived JWTs for API authorization
- Refresh tokens: Long-lived tokens to obtain new access tokens
- Token exchange: RFC 8693 for service-to-service auth

### Principals
Resolved from tokens, containing: subject, tenant_id, scopes, roles.

## MCP Tools

### Deterministic
- `auth.get_capabilities` - Module capabilities
- `auth.health_check` - Backend connectivity
- `auth.describe_config_schema` - Configuration schemas

### Operational
- `auth.verify_access_token` - Verify JWT and extract claims
- `auth.introspect_token` - Check token active status
- `auth.resolve_principal` - Get principal from envelope
- `auth.refresh_token` - Exchange refresh for access token
- `auth.revoke_token` - Revoke access/refresh token
- `auth.get_user_info` - Get user profile from IdP
- `auth.exchange_token` - RFC 8693 token exchange

### Authoring
- `auth.authoring.get_status` - Authoring status
- `auth.authoring.validate_backend_config` - Validate configs
- `auth.authoring.upsert_backend_config` - Create/update backend
- `auth.authoring.delete_backend_config` - Remove backend
"""

KEYCLOAK_DOC = """# Keycloak Backend

## Configuration

```yaml
schema_version: 1
kind: keycloak
base_url: http://localhost:8180
realm: my-realm
client_id: my-client
client_secret: secret
default_audience: my-api
tenant_claim: tenant_id
allowed_algs: [RS256]
jwks_cache_ttl_seconds: 300
```

## Endpoints (auto-derived)
- Issuer: `{base_url}/realms/{realm}`
- JWKS: `{issuer}/protocol/openid-connect/certs`
- Token: `{issuer}/protocol/openid-connect/token`
- Revoke: `{issuer}/protocol/openid-connect/revoke`
- UserInfo: `{issuer}/protocol/openid-connect/userinfo`

## Token Verification
1. Fetch JWKS (cached)
2. Validate signature with RS256
3. Check issuer, audience, expiration
4. Extract claims and build Principal
"""

TOKENS_DOC = """# Token Operations

## Verify Access Token
```python
result = auth.verify_access_token(
    token="eyJ...",
    required_audience="my-api",
    required_scopes=["read", "write"]
)
# Returns: {valid, claims, principal, error}
```

## Introspect Token
```python
result = auth.introspect_token(token="eyJ...")
# Returns: {active, exp, sub, tenant_id}
```

## Refresh Token
```python
result = auth.refresh_token(
    refresh_token="eyJ...",
    scope="openid profile"
)
# Returns: {access_token, token_type, expires_in, refresh_token}
```

## Token Exchange (RFC 8693)
```python
result = auth.exchange_token(
    subject_token="eyJ...",
    subject_token_type="urn:ietf:params:oauth:token-type:access_token",
    audience="target-service"
)
```
"""

ENVELOPE_DOC = """# Context Envelope

The envelope carries request context through the auth flow.

## Fields
- `tenant_id`: Multi-tenant isolation
- `principal_id`: Authenticated user/service
- `session_id`: Session tracking
- `request_id`: Request correlation
- `agent_id`: Agent identification

## Usage
```python
envelope = {
    "tenant_id": "acme-corp",
    "principal_id": "user-123",
    "request_id": "req-abc"
}

result = auth.verify_access_token(
    token="eyJ...",
    envelope=envelope
)
```

The envelope is passed through to backends for audit logging.
"""

DOCS = {
    "overview": OVERVIEW_DOC,
    "keycloak": KEYCLOAK_DOC,
    "tokens": TOKENS_DOC,
    "envelope": ENVELOPE_DOC,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
