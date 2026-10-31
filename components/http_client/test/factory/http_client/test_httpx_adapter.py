"""Tests for HTTPX adapter with mocked HTTP calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.http.runtime.ports import RetryConfig, AuthConfig
from factory.http.runtime.adapters.httpx_adapter import HTTPXClient


class TestHTTPXClientMocked:
    """Tests for HTTPX client with mocked httpx library."""

    def test_get_request_success(self) -> None:
        """Should make GET request and return response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"result": "ok"}'

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            client = HTTPXClient()
            response = client.get("https://api.example.com/test")

            assert response.status_code == 200
            assert response.ok is True
            assert response.json() == {"result": "ok"}
            mock_client.request.assert_called_once()

    def test_post_request_with_json_body(self) -> None:
        """Should POST JSON body with correct content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.content = b'{"id": 123}'

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            client = HTTPXClient()
            response = client.post("https://api.example.com/items", body={"name": "test"})

            assert response.status_code == 201
            call_kwargs = mock_client.request.call_args
            assert call_kwargs[1]["headers"]["Content-Type"] == "application/json"

    def test_put_request(self) -> None:
        """Should make PUT request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"updated": true}'

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            client = HTTPXClient()
            response = client.put("https://api.example.com/items/1", body={"name": "updated"})

            assert response.status_code == 200
            assert mock_client.request.call_args[0][0] == "PUT"

    def test_delete_request(self) -> None:
        """Should make DELETE request."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.content = b""

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            client = HTTPXClient()
            response = client.delete("https://api.example.com/items/1")

            assert response.status_code == 204
            assert mock_client.request.call_args[0][0] == "DELETE"

    def test_bearer_auth_applied(self) -> None:
        """Should apply bearer token to request headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"{}"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            auth = AuthConfig(auth_type="bearer", token="secret-token")
            client = HTTPXClient(auth=auth)
            client.get("https://api.example.com/protected")

            call_kwargs = mock_client.request.call_args
            assert call_kwargs[1]["headers"]["Authorization"] == "Bearer secret-token"

    def test_api_key_auth_applied(self) -> None:
        """Should apply API key to request headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"{}"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            auth = AuthConfig(auth_type="api_key", api_key_header="X-API-Key", api_key_value="key123")
            client = HTTPXClient(auth=auth)
            client.get("https://api.example.com/protected")

            call_kwargs = mock_client.request.call_args
            assert call_kwargs[1]["headers"]["X-API-Key"] == "key123"

    def test_retry_on_server_error(self) -> None:
        """Should retry on 500 status code."""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.headers = {}
        mock_response_fail.content = b"Server Error"

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {}
        mock_response_ok.content = b'{"ok": true}'

        mock_client = MagicMock()
        mock_client.request.side_effect = [mock_response_fail, mock_response_ok]

        with patch("httpx.Client", return_value=mock_client):
            retry = RetryConfig(max_retries=2, backoff_factor=0.01)
            client = HTTPXClient(retry=retry)
            response = client.get("https://api.example.com/flaky")

            assert response.status_code == 200
            assert mock_client.request.call_count == 2

    def test_retry_exhausted_returns_last_response(self) -> None:
        """Should return last response when retries exhausted."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.headers = {}
        mock_response.content = b"Service Unavailable"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            retry = RetryConfig(max_retries=2, backoff_factor=0.01)
            client = HTTPXClient(retry=retry)
            response = client.get("https://api.example.com/down")

            assert response.status_code == 503
            assert mock_client.request.call_count == 3  # initial + 2 retries

    def test_request_with_params(self) -> None:
        """Should pass query params to request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"[]"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            client = HTTPXClient()
            client.get("https://api.example.com/search", params={"q": "test", "page": "1"})

            call_kwargs = mock_client.request.call_args
            assert call_kwargs[1]["params"] == {"q": "test", "page": "1"}

    def test_request_with_custom_headers(self) -> None:
        """Should merge custom headers with auth headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"{}"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            auth = AuthConfig(auth_type="bearer", token="token")
            client = HTTPXClient(auth=auth)
            client.get("https://api.example.com/test", headers={"X-Custom": "value"})

            call_kwargs = mock_client.request.call_args
            headers = call_kwargs[1]["headers"]
            assert headers["X-Custom"] == "value"
            assert headers["Authorization"] == "Bearer token"
