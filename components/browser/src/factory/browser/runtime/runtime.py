"""Browser runtime - main orchestration layer."""

from datetime import datetime, timezone
from typing import Any

from .models import BrowserConfig, SessionInfo
from .ports import BrowserPort


class BrowserRuntime:
    """Runtime for browser automation operations."""

    def __init__(self, adapter: BrowserPort) -> None:
        """Initialize with a browser adapter."""
        self._adapter = adapter
        self._sessions: dict[str, SessionInfo] = {}

    async def launch(self, config: BrowserConfig | None = None) -> SessionInfo:
        """Launch a new browser session."""
        cfg = config or BrowserConfig()
        session_id = await self._adapter.launch(cfg.model_dump())
        
        session = SessionInfo(
            session_id=session_id,
            browser_type=self._adapter.__class__.__name__.replace("Adapter", "").lower(),
            headless=cfg.headless,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._sessions[session_id] = session
        return session

    async def close(self, session_id: str) -> None:
        """Close a browser session."""
        await self._adapter.close(session_id)
        self._sessions.pop(session_id, None)

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
        result = await self._adapter.navigate(session_id, url)
        if session_id in self._sessions:
            self._sessions[session_id].current_url = url
        return result

    async def get_content(self, session_id: str) -> str:
        """Get page HTML content."""
        return await self._adapter.get_content(session_id)

    async def screenshot(self, session_id: str, full_page: bool = False) -> bytes:
        """Capture screenshot."""
        return await self._adapter.screenshot(session_id, full_page)

    async def click(
        self, session_id: str, selector: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Click an element."""
        return await self._adapter.click(session_id, selector, selector_type)

    async def type_text(
        self, session_id: str, selector: str, text: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Type text into an element."""
        return await self._adapter.type_text(session_id, selector, text, selector_type)

    async def evaluate(self, session_id: str, script: str) -> Any:
        """Execute JavaScript."""
        return await self._adapter.evaluate(session_id, script)

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 30000
    ) -> dict[str, Any]:
        """Wait for element to appear."""
        return await self._adapter.wait_for_selector(session_id, selector, timeout_ms)

    def list_sessions(self) -> list[SessionInfo]:
        """List active sessions."""
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> SessionInfo | None:
        """Get session info."""
        return self._sessions.get(session_id)

    def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        adapter_health = self._adapter.health_check()
        return {
            "healthy": adapter_health.get("healthy", False),
            "adapter": adapter_health,
            "active_sessions": len(self._sessions),
        }
