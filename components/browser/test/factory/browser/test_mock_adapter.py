"""Tests for mock browser adapter."""

import pytest

from factory.browser.runtime.adapters.mock import MockAdapter


class TestMockAdapter:
    """Test mock browser adapter."""

    @pytest.fixture
    def adapter(self) -> MockAdapter:
        """Create mock adapter."""
        return MockAdapter()

    @pytest.mark.asyncio
    async def test_launch_and_close(self, adapter: MockAdapter) -> None:
        """Test launching and closing a session."""
        session_id = await adapter.launch({"headless": True})
        assert session_id is not None
        assert len(session_id) > 0
        await adapter.close(session_id)
        await adapter.close(session_id)  # Should not raise on double close

    @pytest.mark.asyncio
    async def test_navigate(self, adapter: MockAdapter) -> None:
        """Test navigation."""
        session_id = await adapter.launch({})
        result = await adapter.navigate(session_id, "https://example.com")
        assert result["url"] == "https://example.com"
        assert "title" in result
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_get_content(self, adapter: MockAdapter) -> None:
        """Test getting page content."""
        session_id = await adapter.launch({})
        content = await adapter.get_content(session_id)
        assert "<html>" in content
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_screenshot(self, adapter: MockAdapter) -> None:
        """Test screenshot capture."""
        session_id = await adapter.launch({})
        data = await adapter.screenshot(session_id)
        assert data[:4] == b"\x89PNG"  # Valid PNG magic bytes
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_click(self, adapter: MockAdapter) -> None:
        """Test click action."""
        session_id = await adapter.launch({})
        result = await adapter.click(session_id, "button.submit")
        assert result["success"] is True
        assert result["selector"] == "button.submit"
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_type_text(self, adapter: MockAdapter) -> None:
        """Test type action."""
        session_id = await adapter.launch({})
        result = await adapter.type_text(session_id, "input#email", "test@example.com")
        assert result["success"] is True
        assert result["text_length"] == len("test@example.com")
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_evaluate(self, adapter: MockAdapter) -> None:
        """Test JavaScript evaluation."""
        session_id = await adapter.launch({})
        result = await adapter.evaluate(session_id, "1 + 1")
        assert result["mock_result"] is True
        await adapter.close(session_id)

    @pytest.mark.asyncio
    async def test_cookies(self, adapter: MockAdapter) -> None:
        """Test cookie operations."""
        session_id = await adapter.launch({})
        await adapter.set_cookie(session_id, "test", "value", "example.com")
        cookies = await adapter.get_cookies(session_id)
        assert len(cookies) == 1
        assert cookies[0]["name"] == "test"
        await adapter.close(session_id)

    def test_health_check(self, adapter: MockAdapter) -> None:
        """Test health check."""
        health = adapter.health_check()
        assert health["healthy"] is True
        assert health["adapter"] == "mock"

    @pytest.mark.asyncio
    async def test_invalid_session(self, adapter: MockAdapter) -> None:
        """Test operations on invalid session."""
        with pytest.raises(ValueError, match="Session not found"):
            await adapter.navigate("invalid-session", "https://example.com")
