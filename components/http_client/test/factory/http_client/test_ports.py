"""Tests for HTTP ports (data classes)."""

from factory.http.runtime.ports import (
    HTTPHealth,
    HTTPResponse,
    RetryConfig,
    RateLimitConfig,
    AuthConfig,
)


class TestHTTPHealth:
    """Tests for HTTPHealth dataclass."""

    def test_healthy_status(self) -> None:
        """Should create healthy status."""
        health = HTTPHealth(healthy=True, backend="httpx", latency_ms=5.0)
        assert health.healthy is True
        assert health.backend == "httpx"
        assert health.latency_ms == 5.0

    def test_unhealthy_status(self) -> None:
        """Should create unhealthy status with message."""
        health = HTTPHealth(healthy=False, backend="aiohttp", message="Connection refused")
        assert health.healthy is False
        assert health.message == "Connection refused"


class TestHTTPResponse:
    """Tests for HTTPResponse dataclass."""

    def test_basic_response(self) -> None:
        """Should create basic response."""
        response = HTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b'{"key": "value"}',
        )
        assert response.status_code == 200
        assert response.ok is True

    def test_text_property(self) -> None:
        """Should decode body as text."""
        response = HTTPResponse(status_code=200, headers={}, body=b"Hello World")
        assert response.text == "Hello World"

    def test_json_method(self) -> None:
        """Should parse body as JSON."""
        response = HTTPResponse(status_code=200, headers={}, body=b'{"name": "test"}')
        data = response.json()
        assert data["name"] == "test"

    def test_ok_property_success(self) -> None:
        """Should return True for 2xx status codes."""
        for code in [200, 201, 204, 299]:
            response = HTTPResponse(status_code=code, headers={}, body=b"")
            assert response.ok is True

    def test_ok_property_failure(self) -> None:
        """Should return False for non-2xx status codes."""
        for code in [400, 401, 404, 500, 503]:
            response = HTTPResponse(status_code=code, headers={}, body=b"")
            assert response.ok is False

    def test_elapsed_ms(self) -> None:
        """Should track elapsed time."""
        response = HTTPResponse(status_code=200, headers={}, body=b"", elapsed_ms=123.45)
        assert response.elapsed_ms == 123.45


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff_factor == 0.5
        assert 429 in config.retry_statuses
        assert 500 in config.retry_statuses

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = RetryConfig(max_retries=5, backoff_factor=1.0)
        assert config.max_retries == 5
        assert config.backoff_factor == 1.0


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        config = RateLimitConfig()
        assert config.requests_per_second == 10.0
        assert config.burst_size == 20

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = RateLimitConfig(requests_per_second=5.0, burst_size=10)
        assert config.requests_per_second == 5.0
        assert config.burst_size == 10


class TestAuthConfig:
    """Tests for AuthConfig dataclass."""

    def test_no_auth_default(self) -> None:
        """Should default to no auth."""
        config = AuthConfig()
        assert config.auth_type == "none"

    def test_bearer_auth(self) -> None:
        """Should configure bearer auth."""
        config = AuthConfig(auth_type="bearer", token="my-token")
        assert config.auth_type == "bearer"
        assert config.token == "my-token"

    def test_api_key_auth(self) -> None:
        """Should configure API key auth."""
        config = AuthConfig(
            auth_type="api_key",
            api_key_header="X-Custom-Key",
            api_key_value="secret123",
        )
        assert config.auth_type == "api_key"
        assert config.api_key_header == "X-Custom-Key"
        assert config.api_key_value == "secret123"
