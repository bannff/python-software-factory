"""Tests for browser core functionality."""

import pytest

from factory.browser.core import COMPONENT_NAME, COMPONENT_VERSION, BrowserType, DEFAULT_CONFIG
from factory.browser.runtime.adapters.mock import MockAdapter
from factory.browser.runtime.models import BrowserConfig
from factory.browser.runtime.runtime import BrowserRuntime


class TestBrowserCore:
    """Test core types and constants."""

    def test_component_metadata(self) -> None:
        """Test component metadata is defined."""
        assert COMPONENT_NAME == "browser"
        assert COMPONENT_VERSION == "0.1.0"

    def test_browser_types(self) -> None:
        """Test browser type enum."""
        assert BrowserType.CHROMIUM == "chromium"
        assert BrowserType.FIREFOX == "firefox"
        assert BrowserType.WEBKIT == "webkit"

    def test_default_config(self) -> None:
        """Test default configuration."""
        assert DEFAULT_CONFIG["headless"] is True
        assert DEFAULT_CONFIG["timeout_ms"] == 30000


class TestBrowserConfig:
    """Test browser configuration model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = BrowserConfig()
        assert config.headless is True
        assert config.timeout_ms == 30000
        assert config.viewport_width == 1280

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = BrowserConfig(headless=False, timeout_ms=60000, user_agent="Custom Agent")
        assert config.headless is False
        assert config.timeout_ms == 60000
        assert config.user_agent == "Custom Agent"


class TestBrowserRuntime:
    """Test browser runtime."""

    @pytest.fixture
    def runtime(self) -> BrowserRuntime:
        """Create runtime with mock adapter."""
        return BrowserRuntime(MockAdapter())

    @pytest.mark.asyncio
    async def test_launch_session(self, runtime: BrowserRuntime) -> None:
        """Test launching a session."""
        session = await runtime.launch()
        assert session.session_id is not None
        assert session.headless is True
        assert session.browser_type == "mock"

    @pytest.mark.asyncio
    async def test_list_sessions(self, runtime: BrowserRuntime) -> None:
        """Test listing sessions."""
        session1 = await runtime.launch()
        session2 = await runtime.launch()
        sessions = runtime.list_sessions()
        assert len(sessions) == 2
        await runtime.close(session1.session_id)
        await runtime.close(session2.session_id)

    @pytest.mark.asyncio
    async def test_get_session(self, runtime: BrowserRuntime) -> None:
        """Test getting session info."""
        session = await runtime.launch()
        retrieved = runtime.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        await runtime.close(session.session_id)
        assert runtime.get_session(session.session_id) is None

    def test_health_check(self, runtime: BrowserRuntime) -> None:
        """Test runtime health check."""
        health = runtime.health_check()
        assert health["healthy"] is True
        assert "adapter" in health
        assert health["active_sessions"] == 0
