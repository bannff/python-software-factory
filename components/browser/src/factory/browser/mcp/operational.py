"""Operational Browser MCP tools with strict transport contracts."""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from ..runtime.models import BrowserConfig
from .contracts.operational import (
    ClickInput, ClickOutput, CloseInput, CloseOutput, ContentInput, ContentOutput,
    EngineSmokeInput, EngineSmokeOutput,
    EvaluateInput, EvaluateOutput, LaunchInput, LaunchOutput, NavigateInput,
    NavigateOutput, ScreenshotInput, ScreenshotOutput, TypeTextInput,
    TypeTextOutput, WaitForSelectorInput, WaitForSelectorOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import BrowserRuntime


def register(mcp: Any, runtime: "BrowserRuntime") -> None:
    """Register operational tools with the MCP server."""

    @mcp.tool(name="browser.engine_smoke")
    @operational(input_model=EngineSmokeInput, output_model=EngineSmokeOutput, idempotent=False)
    async def engine_smoke() -> ToolResult[EngineSmokeOutput]:
        """Launch and close one headless session on the active engine (honest readiness)."""
        import time
        from ..server import selected_engine
        started = time.monotonic()
        try:
            session = await runtime.launch(BrowserConfig(headless=True))
            await runtime.close(session.session_id)
            return EngineSmokeOutput(
                engine=selected_engine(), ok=True, browser_type=session.browser_type,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - the whole point is to report why
            return EngineSmokeOutput(
                engine=selected_engine(), ok=False, error=f"{type(exc).__name__}: {exc}"[:300],
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )

    @mcp.tool(name="browser.launch")
    @operational(input_model=LaunchInput, output_model=LaunchOutput)
    async def launch(
        headless: bool = True,
        timeout_ms: int = 30000,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        user_agent: str | None = None,
    ) -> ToolResult[LaunchOutput]:
        """Launch a new browser session."""
        config = BrowserConfig(
            headless=headless, timeout_ms=timeout_ms,
            viewport_width=viewport_width, viewport_height=viewport_height,
            user_agent=user_agent,
        )
        return LaunchOutput(session=(await runtime.launch(config)).model_dump())

    @mcp.tool(name="browser.close")
    @operational(input_model=CloseInput, output_model=CloseOutput)
    async def close(session_id: str) -> ToolResult[CloseOutput]:
        """Close a browser session."""
        await runtime.close(session_id)
        return CloseOutput(session_id=session_id)

    @mcp.tool(name="browser.navigate")
    @operational(input_model=NavigateInput, output_model=NavigateOutput)
    async def navigate(session_id: str, url: str) -> ToolResult[NavigateOutput]:
        """Navigate to a URL."""
        return NavigateOutput.model_validate(await runtime.navigate(session_id, url))

    @mcp.tool(name="browser.get_content")
    @operational(input_model=ContentInput, output_model=ContentOutput)
    async def get_content(session_id: str) -> ToolResult[ContentOutput]:
        """Get page HTML content."""
        content = await runtime.get_content(session_id)
        return ContentOutput(content=content, length=len(content))

    @mcp.tool(name="browser.screenshot")
    @operational(input_model=ScreenshotInput, output_model=ScreenshotOutput)
    async def screenshot(
        session_id: str, full_page: bool = False
    ) -> ToolResult[ScreenshotOutput]:
        """Capture screenshot as base64 PNG."""
        data = await runtime.screenshot(session_id, full_page)
        return ScreenshotOutput(
            format="png", data=base64.b64encode(data).decode(), size_bytes=len(data)
        )

    @mcp.tool(name="browser.click")
    @operational(input_model=ClickInput, output_model=ClickOutput)
    async def click(
        session_id: str, selector: str, selector_type: str = "css"
    ) -> ToolResult[ClickOutput]:
        """Click an element matching the selector."""
        return ClickOutput.model_validate(
            await runtime.click(session_id, selector, selector_type)
        )

    @mcp.tool(name="browser.type_text")
    @operational(input_model=TypeTextInput, output_model=TypeTextOutput)
    async def type_text(
        session_id: str, selector: str, text: str, selector_type: str = "css"
    ) -> ToolResult[TypeTextOutput]:
        """Type text into an element."""
        return TypeTextOutput.model_validate(
            await runtime.type_text(session_id, selector, text, selector_type)
        )

    @mcp.tool(name="browser.evaluate")
    @operational(input_model=EvaluateInput, output_model=EvaluateOutput)
    async def evaluate(session_id: str, script: str) -> ToolResult[EvaluateOutput]:
        """Execute JavaScript in the page context."""
        return EvaluateOutput(result=await runtime.evaluate(session_id, script))

    @mcp.tool(name="browser.wait_for_selector")
    @operational(
        input_model=WaitForSelectorInput, output_model=WaitForSelectorOutput
    )
    async def wait_for_selector(
        session_id: str, selector: str, timeout_ms: int = 30000
    ) -> ToolResult[WaitForSelectorOutput]:
        """Wait for an element to appear in the DOM."""
        return WaitForSelectorOutput.model_validate(
            await runtime.wait_for_selector(session_id, selector, timeout_ms)
        )
