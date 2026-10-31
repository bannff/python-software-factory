"""Prompt templates for auth MCP prompts."""

from __future__ import annotations

CONFIGURE_KEYCLOAK_TEMPLATE = """# Configure Keycloak Backend: {name}

## Prerequisites
- Keycloak server running at {base_url}
- Realm "{realm}" created
- Client credentials (if using token operations)

## Steps

1. **Create Backend Config**
   ```
   auth.authoring.upsert_backend_config(
       name="{name}",
       yaml_or_object={{
           "schema_version": 1,
           "kind": "keycloak",
           "base_url": "{base_url}",
           "realm": "{realm}",
           "client_id": "<your_client_id>",
           "client_secret": "<your_client_secret>"
       }}
   )
   ```

2. **Validate Configuration**
   ```
   auth.authoring.validate_backend_config(dry_run=False)
   ```

3. **Test Token Verification**
   ```
   auth.verify_access_token(token="<test_token>")
   ```

## Keycloak Setup Tips
- Create a confidential client for backend operations
- Enable "Service Accounts" for client credentials flow
- Configure appropriate audience mappers
"""

DEBUG_TOKEN_TEMPLATE = """# Debug Token Issue

## Token Info
- Token Type: {token_type}
- Error: {error}

## Diagnostic Steps

1. **Check Token Format**
   - JWT should have 3 parts: header.payload.signature
   - Decode at jwt.io (don't use production tokens!)

2. **Verify Backend Health**
   ```
   auth.health_check()
   ```

3. **Introspect Token**
   ```
   auth.introspect_token(token="<token>")
   ```

4. **Check JWKS**
   - Verify JWKS URL is accessible
   - Check key ID (kid) matches token header

## Common Issues

- **expired**: Token past expiration time
- **invalid_signature**: JWKS mismatch or wrong algorithm
- **invalid_audience**: Token not for this service
- **invalid_issuer**: Token from wrong Keycloak realm

## Next: {next_steps}
"""

SETUP_MULTITENANCY_TEMPLATE = """# Setup Multi-Tenancy

## Overview
Multi-tenancy isolates data by tenant_id claim in tokens.

## Configuration

1. **Configure Tenant Claim**
   ```yaml
   tenant_claim: tenant_id  # or organization_id, etc.
   ```

2. **Keycloak Mapper**
   - Add "User Attribute" mapper to client
   - Map user attribute to token claim

3. **Verify Tenant Extraction**
   ```
   result = auth.verify_access_token(token="<token>")
   # Check result["principal"]["tenant_id"]
   ```

## Envelope Usage
```python
envelope = {{"tenant_id": "acme-corp"}}
auth.verify_access_token(token="...", envelope=envelope)
```

The envelope tenant_id can be used for additional validation.
"""


def get_configure_keycloak_prompt(
    name: str = "default",
    base_url: str = "http://localhost:8180",
    realm: str = "master",
) -> str:
    """Generate Keycloak configuration prompt."""
    return CONFIGURE_KEYCLOAK_TEMPLATE.format(
        name=name, base_url=base_url, realm=realm
    )


def get_debug_token_prompt(
    token_type: str = "access_token",
    error: str = "unknown",
) -> str:
    """Generate token debugging prompt."""
    next_steps = {
        "expired": "Request new token via refresh_token",
        "invalid_signature": "Check JWKS URL and key rotation",
        "invalid_audience": "Verify audience claim matches config",
        "invalid_issuer": "Check issuer URL and realm",
    }.get(error, "Review error details and backend logs")

    return DEBUG_TOKEN_TEMPLATE.format(
        token_type=token_type, error=error, next_steps=next_steps
    )


def get_setup_multitenancy_prompt() -> str:
    """Generate multi-tenancy setup prompt."""
    return SETUP_MULTITENANCY_TEMPLATE
