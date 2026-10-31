"""Protocol interfaces for browser adapters."""

from typing import Any, Protocol


class BrowserPort(Protocol):
    """Protocol for browser automation backends."""

    async def launch(self, config: dict[str, Any]) -> str:
        """Launch browser, return session ID."""
        ...

    async def close(self, session_id: str) -> None:
        """Close browser session."""
        ...

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        """Navigate to URL, return page info."""
        ...

    async def get_content(self, session_id: str) -> str:
        """Get page HTML content."""
        ...

    async def screenshot(
        self, session_id: str, full_page: bool = False
    ) -> bytes:
        """Capture screenshot as PNG bytes."""
        ...

    async def click(
        self, session_id: str, selector: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Click element matching selector."""
        ...

    async def type_text(
        self, session_id: str, selector: str, text: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Type text into element."""
        ...

    async def evaluate(self, session_id: str, script: str) -> Any:
        """Execute JavaScript and return result."""
        ...

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 30000
    ) -> dict[str, Any]:
        """Wait for element to appear."""
        ...

    async def get_cookies(self, session_id: str) -> list[dict[str, Any]]:
        """Get all cookies for current page."""
        ...

    async def set_cookie(
        self, session_id: str, name: str, value: str, domain: str | None = None
    ) -> None:
        """Set a cookie."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        ...
