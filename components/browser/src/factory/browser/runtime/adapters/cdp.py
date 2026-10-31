"""Chrome DevTools Protocol (CDP) adapter for browser automation."""

import asyncio
import base64
from typing import Any

from .cdp_base import CDPBase


class CDPAdapter(CDPBase):
    """Browser adapter using Chrome DevTools Protocol directly."""

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        """Navigate to URL."""
        result = await self._send_command(session_id, "Page.navigate", {"url": url})
        return {"url": url, "title": "", "frame_id": result.get("frameId")}

    async def get_content(self, session_id: str) -> str:
        """Get page HTML."""
        result = await self._send_command(
            session_id, "Runtime.evaluate",
            {"expression": "document.documentElement.outerHTML"})
        return result.get("result", {}).get("value", "")

    async def screenshot(self, session_id: str, full_page: bool = False) -> bytes:
        """Capture screenshot."""
        params = {"format": "png", "captureBeyondViewport": full_page}
        result = await self._send_command(session_id, "Page.captureScreenshot", params)
        return base64.b64decode(result["data"])

    async def click(
        self, session_id: str, selector: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Click element."""
        js = f"document.querySelector('{selector}').getBoundingClientRect()"
        result = await self._send_command(
            session_id, "Runtime.evaluate", {"expression": js, "returnByValue": True})
        bounds = result.get("result", {}).get("value", {})
        x = bounds.get("x", 0) + bounds.get("width", 0) / 2
        y = bounds.get("y", 0) + bounds.get("height", 0) / 2
        
        await self._send_command(session_id, "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await self._send_command(session_id, "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
        return {"success": True, "selector": selector}

    async def type_text(
        self, session_id: str, selector: str, text: str, selector_type: str = "css"
    ) -> dict[str, Any]:
        """Type text into element."""
        await self.click(session_id, selector, selector_type)
        for char in text:
            await self._send_command(session_id, "Input.dispatchKeyEvent", {"type": "char", "text": char})
        return {"success": True, "selector": selector, "text_length": len(text)}

    async def evaluate(self, session_id: str, script: str) -> Any:
        """Execute JavaScript."""
        result = await self._send_command(
            session_id, "Runtime.evaluate", {"expression": script, "returnByValue": True})
        return result.get("result", {}).get("value")

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 30000
    ) -> dict[str, Any]:
        """Wait for element."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) * 1000 < timeout_ms:
            result = await self._send_command(
                session_id, "Runtime.evaluate",
                {"expression": f"!!document.querySelector('{selector}')"})
            if result.get("result", {}).get("value"):
                return {"found": True, "selector": selector}
            await asyncio.sleep(0.1)
        return {"found": False, "selector": selector, "timeout": True}

    async def get_cookies(self, session_id: str) -> list[dict[str, Any]]:
        """Get cookies."""
        result = await self._send_command(session_id, "Network.getCookies", {})
        return result.get("cookies", [])

    async def set_cookie(
        self, session_id: str, name: str, value: str, domain: str | None = None
    ) -> None:
        """Set cookie."""
        params = {"name": name, "value": value}
        if domain:
            params["domain"] = domain
        await self._send_command(session_id, "Network.setCookie", params)
