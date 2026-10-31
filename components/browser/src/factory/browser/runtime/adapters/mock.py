"""Mock browser adapter for testing."""

import uuid
from typing import Any


class MockAdapter:
    """Mock browser adapter for testing without real browser."""

    def __init__(self) -> None:
        """Initialize mock adapter."""
        self._sessions: dict[str, dict[str, Any]] = {}

    async def launch(self, config: dict[str, Any]) -> str:
        """Launch mock browser session."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "config": config,
            "url": "about:blank",
            "content": "<html><body></body></html>",
            "cookies": [],
        }
        return session_id

    async def close(self, session_id: str) -> None:
        """Close mock session."""
        self._sessions.pop(session_id, None)

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        """Mock navigation."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        self._sessions[session_id]["url"] = url
        return {"url": url, "title": f"Mock Page - {url}", "status_code": 200}

    async def get_content(self, session_id: str) -> str:
        """Get mock page content."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return self._sessions[session_id]["content"]

    async def screenshot(self, session_id: str, full_page: bool = False) -> bytes:
        """Return mock screenshot (1x1 PNG)."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        # Minimal valid PNG (1x1 transparent pixel)
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    async def click(
        self, session_id: str, selector: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Mock click action."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return {"success": True, "selector": selector, "clicked": True}

    async def type_text(
        self, session_id: str, selector: str, text: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Mock type action."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return {"success": True, "selector": selector, "text_length": len(text)}

    async def evaluate(self, session_id: str, script: str) -> Any:
        """Mock JavaScript evaluation."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return {"mock_result": True, "script_length": len(script)}

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 30000
    ) -> dict[str, Any]:
        """Mock wait for selector."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return {"found": True, "selector": selector, "waited_ms": 0}

    async def get_cookies(self, session_id: str) -> list[dict[str, Any]]:
        """Get mock cookies."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        return self._sessions[session_id]["cookies"]

    async def set_cookie(
        self, session_id: str, name: str, value: str, domain: str | None = None
    ) -> None:
        """Set mock cookie."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        self._sessions[session_id]["cookies"].append(
            {"name": name, "value": value, "domain": domain}
        )

    def health_check(self) -> dict[str, Any]:
        """Check mock adapter health."""
        return {
            "healthy": True,
            "adapter": "mock",
            "sessions": len(self._sessions),
        }
