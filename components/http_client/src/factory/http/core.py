"""Core convenience functions for http brick.

Provides simple top-level functions for common HTTP operations.
"""

from __future__ import annotations

from typing import Any

from .runtime.ports import HTTPResponse
from .runtime.runtime import get_runtime


def get(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make a GET request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return client.get(url, headers=headers, params=params, timeout=timeout)


def post(
    url: str,
    body: bytes | str | dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make a POST request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return client.post(url, body=body, headers=headers, timeout=timeout)


def put(
    url: str,
    body: bytes | str | dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make a PUT request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return client.put(url, body=body, headers=headers, timeout=timeout)


def delete(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make a DELETE request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return client.delete(url, headers=headers, timeout=timeout)


def request(
    method: str,
    url: str,
    body: bytes | str | dict | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make an HTTP request with any method."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return client.request(method, url, headers=headers, params=params, body=body, timeout=timeout)


async def get_async(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make an async GET request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return await client.request_async("GET", url, headers=headers, params=params, timeout=timeout)


async def post_async(
    url: str,
    body: bytes | str | dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    backend: str = "httpx",
    **kwargs: Any,
) -> HTTPResponse:
    """Make an async POST request."""
    runtime = get_runtime()
    client = runtime.get_client(backend, **kwargs)
    return await client.request_async("POST", url, headers=headers, body=body, timeout=timeout)
