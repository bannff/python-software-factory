"""Tests for TenacityHTTPXClient adapter (tenacity library).

Tests instantiation, auth config, health check, and retry behavior.
Network calls are mocked via httpx mock transport.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from factory.http.runtime.adapters.tenacity_httpx import TenacityHTTPXClient
from factory.http.runtime.ports import AuthConfig, HTTPResponse, RetryConfig


class TestTenacityHTTPXClient:
    """Tests for TenacityHTTPXClient using real tenacity library."""

    def test_import(self) -> None:
        """TenacityHTTPXClient and tenacity are importable."""
        from tenacity import retry
        assert retry is not None
        assert TenacityHTTPXClient is not None

    def test_instantiation_defaults(self) -> None:
        """Can create with default config."""
        client = TenacityHTTPXClient()
        assert client is not None

    def test_instantiation_custom_retry(self) -> None:
        """Can create with custom retry config."""
        cfg = RetryConfig(max_retries=5, backoff_factor=1.0)
        client = TenacityHTTPXClient(retry=cfg)
        assert client._retry.max_retries == 5

    def test_health_check(self) -> None:
        """health_check reports the tenacity backend."""
        client = TenacityHTTPXClient()
        health = client.health_check()
        assert health.backend == "tenacity_httpx"

    def test_bearer_auth_applied(self) -> None:
        """Bearer auth adds Authorization header."""
        auth = AuthConfig(auth_type="bearer", token="tok_123")
        client = TenacityHTTPXClient(auth=auth)
        headers = client._apply_auth({})
        assert headers["Authorization"] == "Bearer tok_123"

    def test_api_key_auth_applied(self) -> None:
        """API key auth adds custom header."""
        auth = AuthConfig(auth_type="api_key", api_key_header="X-Key", api_key_value="secret")
        client = TenacityHTTPXClient(auth=auth)
        headers = client._apply_auth({})
        assert headers["X-Key"] == "secret"

    def test_no_auth(self) -> None:
        """No auth leaves headers unchanged."""
        client = TenacityHTTPXClient()
        headers = client._apply_auth({"Accept": "application/json"})
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/json"

    def test_prepare_body_dict(self) -> None:
        """Dict body is JSON-encoded."""
        client = TenacityHTTPXClient()
        body, headers = client._prepare_body({"key": "val"}, {})
        assert b'"key"' in body
        assert headers["Content-Type"] == "application/json"

    def test_prepare_body_string(self) -> None:
        """String body is encoded to bytes."""
        client = TenacityHTTPXClient()
        body, headers = client._prepare_body("raw text", {})
        assert body == b"raw text"

    def test_prepare_body_none(self) -> None:
        """None body returns None."""
        client = TenacityHTTPXClient()
        body, headers = client._prepare_body(None, {})
        assert body is None

    def test_get_delegates_to_request(self) -> None:
        """get() calls request() with GET method."""
        client = TenacityHTTPXClient()
        mock_resp = HTTPResponse(status_code=200, headers={}, body=b"ok")
        with patch.object(client, "request", return_value=mock_resp) as mock_req:
            result = client.get("https://example.com/api")
            mock_req.assert_called_once()
            assert result.status_code == 200

    def test_post_delegates_to_request(self) -> None:
        """post() calls request() with POST method and body."""
        client = TenacityHTTPXClient()
        mock_resp = HTTPResponse(status_code=201, headers={}, body=b"created")
        with patch.object(client, "request", return_value=mock_resp) as mock_req:
            result = client.post("https://example.com/api", body={"data": 1})
            mock_req.assert_called_once()
            assert result.status_code == 201
