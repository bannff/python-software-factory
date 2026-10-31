"""Tests for AIOHTTP adapter with mocked HTTP calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from factory.http.runtime.ports import AuthConfig
from factory.http.runtime.adapters.aiohttp_adapter import AIOHTTPClient


class TestAIOHTTPClientMocked:
    """Tests for AIOHTTP client with mocked aiohttp library."""

    def test_build_url_absolute(self) -> None:
        """Should return absolute URLs unchanged."""
        client = AIOHTTPClient()
        url = client._build_url("https://example.com/api")
        assert url == "https://example.com/api"

    def test_build_url_relative_with_base(self) -> None:
        """Should prepend base URL to relative paths."""
        client = AIOHTTPClient(base_url="https://api.example.com")
        url = client._build_url("/users")
        assert url == "https://api.example.com/users"

    def test_build_url_handles_slashes(self) -> None:
        """Should handle trailing/leading slashes correctly."""
        client = AIOHTTPClient(base_url="https://api.example.com/")
        url = client._build_url("/users")
        assert url == "https://api.example.com/users"

    def test_apply_bearer_auth(self) -> None:
        """Should apply bearer auth to headers."""
        auth = AuthConfig(auth_type="bearer", token="my-token")
        client = AIOHTTPClient(auth=auth)
        headers = client._apply_auth({})
        assert headers["Authorization"] == "Bearer my-token"

    def test_apply_api_key_auth(self) -> None:
        """Should apply API key auth to headers."""
        auth = AuthConfig(auth_type="api_key", api_key_header="X-Key", api_key_value="secret")
        client = AIOHTTPClient(auth=auth)
        headers = client._apply_auth({})
        assert headers["X-Key"] == "secret"

    def test_apply_no_auth(self) -> None:
        """Should not modify headers when no auth configured."""
        client = AIOHTTPClient()
        headers = client._apply_auth({"X-Existing": "value"})
        assert headers == {"X-Existing": "value"}

    def test_health_check_success(self) -> None:
        """Should return healthy when aiohttp is available."""
        client = AIOHTTPClient()
        health = client.health_check()
        assert health.healthy is True
        assert health.backend == "aiohttp"

    @pytest.mark.asyncio
    async def test_async_get_request(self) -> None:
        """Should make async GET request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read = AsyncMock(return_value=b'{"data": "test"}')

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("aiohttp.ClientTimeout"):
                client = AIOHTTPClient()
                response = await client.request_async("GET", "https://api.example.com/test")

                assert response.status_code == 200
                assert response.json() == {"data": "test"}

    @pytest.mark.asyncio
    async def test_async_post_with_json_body(self) -> None:
        """Should make async POST request with JSON body."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.headers = {}
        mock_response.read = AsyncMock(return_value=b'{"id": 1}')

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("aiohttp.ClientTimeout"):
                client = AIOHTTPClient()
                response = await client.request_async(
                    "POST", "https://api.example.com/items", body={"name": "test"}
                )

                assert response.status_code == 201
                call_kwargs = mock_session.request.call_args
                assert call_kwargs[1]["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_async_request_with_auth(self) -> None:
        """Should apply auth to async requests."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.read = AsyncMock(return_value=b'{}')

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("aiohttp.ClientTimeout"):
                auth = AuthConfig(auth_type="bearer", token="async-token")
                client = AIOHTTPClient(auth=auth)
                await client.request_async("GET", "https://api.example.com/protected")

                call_kwargs = mock_session.request.call_args
                assert call_kwargs[1]["headers"]["Authorization"] == "Bearer async-token"
