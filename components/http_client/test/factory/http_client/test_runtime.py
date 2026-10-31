"""Tests for HTTP runtime."""

import pytest

from factory.http.runtime.runtime import (
    HTTPRuntime,
    get_runtime,
    reset_runtime,
)
from factory.http.runtime.ports import RetryConfig, AuthConfig


class TestHTTPRuntime:
    """Tests for HTTPRuntime factory."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_available_backends(self) -> None:
        """Should list available backends."""
        backends = HTTPRuntime.available_backends()
        assert "httpx" in backends
        assert "aiohttp" in backends

    def test_get_runtime_singleton(self) -> None:
        """Should return same runtime instance."""
        r1 = get_runtime()
        r2 = get_runtime()
        assert r1 is r2

    def test_reset_runtime(self) -> None:
        """Should reset runtime instance."""
        r1 = get_runtime()
        reset_runtime()
        r2 = get_runtime()
        assert r1 is not r2

    def test_unknown_backend_raises(self) -> None:
        """Should raise for unknown backend."""
        runtime = HTTPRuntime()
        with pytest.raises(ValueError, match="Unknown HTTP backend"):
            runtime.get_client("unknown")

    def test_get_client_httpx(self) -> None:
        """Should create httpx client."""
        runtime = HTTPRuntime()
        client = runtime.get_client("httpx")
        assert client is not None

    def test_get_client_aiohttp(self) -> None:
        """Should create aiohttp client."""
        runtime = HTTPRuntime()
        client = runtime.get_client("aiohttp")
        assert client is not None

    def test_client_with_retry_config(self) -> None:
        """Should create client with retry config."""
        runtime = HTTPRuntime()
        retry = RetryConfig(max_retries=5)
        client = runtime.get_client("httpx", retry=retry)
        assert client is not None
        assert client._retry.max_retries == 5

    def test_client_with_auth_config(self) -> None:
        """Should create client with auth config."""
        runtime = HTTPRuntime()
        auth = AuthConfig(auth_type="bearer", token="test-token")
        client = runtime.get_client("httpx", auth=auth)
        assert client is not None
        assert client._auth.token == "test-token"

    def test_health_check_empty(self) -> None:
        """Should return empty health when no clients active."""
        runtime = HTTPRuntime()
        health = runtime.health_check()
        assert health == {}


class TestHTTPXClient:
    """Tests for HTTPX client adapter."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_health_check(self) -> None:
        """Should return healthy status."""
        runtime = HTTPRuntime()
        client = runtime.get_client("httpx")
        health = client.health_check()
        assert health.healthy is True
        assert health.backend == "httpx"

    def test_apply_bearer_auth(self) -> None:
        """Should apply bearer auth to headers."""
        runtime = HTTPRuntime()
        auth = AuthConfig(auth_type="bearer", token="my-token")
        client = runtime.get_client("httpx", auth=auth)
        headers = client._apply_auth({})
        assert headers["Authorization"] == "Bearer my-token"

    def test_apply_api_key_auth(self) -> None:
        """Should apply API key auth to headers."""
        runtime = HTTPRuntime()
        auth = AuthConfig(auth_type="api_key", api_key_header="X-Key", api_key_value="secret")
        client = runtime.get_client("httpx", auth=auth)
        headers = client._apply_auth({})
        assert headers["X-Key"] == "secret"


class TestAIOHTTPClient:
    """Tests for AIOHTTP client adapter."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_health_check(self) -> None:
        """Should return healthy status."""
        runtime = HTTPRuntime()
        client = runtime.get_client("aiohttp")
        health = client.health_check()
        assert health.healthy is True
        assert health.backend == "aiohttp"

    def test_build_url_absolute(self) -> None:
        """Should return absolute URLs unchanged."""
        runtime = HTTPRuntime()
        client = runtime.get_client("aiohttp")
        url = client._build_url("https://example.com/api")
        assert url == "https://example.com/api"

    def test_build_url_relative(self) -> None:
        """Should prepend base URL to relative paths."""
        runtime = HTTPRuntime()
        client = runtime.get_client("aiohttp", base_url="https://api.example.com")
        url = client._build_url("/users")
        assert url == "https://api.example.com/users"
