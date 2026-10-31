"""Public interface for http brick.

Other bricks should import from here, not from runtime internals.
"""

from .runtime.ports import (
    HTTPClient,
    HTTPResponse,
    HTTPHealth,
    RetryConfig,
    RateLimitConfig,
    AuthConfig,
)
from .runtime.runtime import HTTPRuntime, get_runtime, reset_runtime

__all__ = [
    # Ports (protocols)
    "HTTPClient",
    # Data classes
    "HTTPResponse",
    "HTTPHealth",
    "RetryConfig",
    "RateLimitConfig",
    "AuthConfig",
    # Runtime
    "HTTPRuntime",
    "get_runtime",
    "reset_runtime",
]
