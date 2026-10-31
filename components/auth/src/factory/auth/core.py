"""Auth core - high-level convenience functions.

Provides simple API for common authentication operations without
needing to manage the full AuthRuntime lifecycle.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Lazy import to avoid circular dependencies
_runtime: "AuthRuntime | None" = None


def get_runtime(config_dir: str | Path | None = None) -> "AuthRuntime":
    """Get or create the default AuthRuntime instance.
    
    Args:
        config_dir: Path to configuration directory. Defaults to AUTH_CONFIG_DIR env var.
        
    Returns:
        Initialized AuthRuntime instance.
    """
    global _runtime
    if _runtime is None:
        from .runtime.runtime import AuthRuntime
        if config_dir is None:
            config_dir = Path(os.environ.get("AUTH_CONFIG_DIR", "./config"))
        _runtime = AuthRuntime(Path(config_dir))
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime instance (for testing)."""
    global _runtime
    _runtime = None


def verify_token(
    token: str,
    *,
    required_audience: str | None = None,
    required_scopes: list[str] | None = None,
) -> dict[str, Any]:
    """Verify an access token and extract claims.
    
    Args:
        token: The access token to verify.
        required_audience: Optional audience to validate.
        required_scopes: Optional scopes to require.
        
    Returns:
        Token claims if valid.
        
    Raises:
        ValueError: If token is invalid.
    """
    runtime = get_runtime()
    return runtime.verify_access_token(
        token=token,
        required_audience=required_audience,
        required_scopes=required_scopes,
        envelope=None,
    )


def refresh_token(refresh_token: str, scope: str | None = None) -> dict[str, Any]:
    """Refresh an access token using a refresh token.
    
    Args:
        refresh_token: The refresh token.
        scope: Optional scope for the new token.
        
    Returns:
        New token response.
    """
    runtime = get_runtime()
    return runtime.refresh_token(
        refresh_token=refresh_token,
        scope=scope,
        envelope=None,
    )


def get_user_info(access_token: str) -> dict[str, Any]:
    """Get user information from an access token.
    
    Args:
        access_token: Valid access token.
        
    Returns:
        User information dictionary.
    """
    runtime = get_runtime()
    return runtime.get_user_info(access_token=access_token, envelope=None)


def introspect(token: str) -> dict[str, Any]:
    """Introspect a token to check if it's active.
    
    Args:
        token: The token to introspect.
        
    Returns:
        Introspection response with 'active' field.
    """
    runtime = get_runtime()
    return runtime.introspect_token(token=token, envelope=None)


def health_check() -> dict[str, Any]:
    """Check auth service health.
    
    Returns:
        Health status dictionary.
    """
    runtime = get_runtime()
    return runtime.health_check()


def get_capabilities() -> dict[str, Any]:
    """Get auth module capabilities.
    
    Returns:
        Capabilities dictionary.
    """
    runtime = get_runtime()
    return runtime.get_capabilities()
