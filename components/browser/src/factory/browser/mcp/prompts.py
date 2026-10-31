"""MCP Prompt registration for browser brick.

Prompts provide guided workflows for common tasks:
- Automating page interactions
- Extracting content from pages
- Debugging browser sessions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import BrowserRuntime


def register(mcp: Any, runtime: "BrowserRuntime") -> None:
    """Register all browser prompts with the MCP server."""

    @mcp.prompt()
    def automate_page(url: str, task: str) -> str:
        """Generate guidance for automating a page interaction."""
        return f"""Automate the following task on {url}:

Task: {task}

Steps:
1. Launch a browser session: browser.launch()
2. Navigate to the URL: browser.navigate(session_id, "{url}")
3. Wait for page to load: browser.wait_for_selector(session_id, "body")
4. Perform the required interactions (click, type, etc.)
5. Capture results or screenshot if needed
6. Close the session: browser.close(session_id)

Remember to handle errors and timeouts appropriately."""

    @mcp.prompt()
    def extract_content(url: str, selector: str = "body") -> str:
        """Generate guidance for extracting content from a page."""
        return f"""Extract content from {url} using selector: {selector}

Steps:
1. Launch browser: browser.launch(headless=True)
2. Navigate: browser.navigate(session_id, "{url}")
3. Wait for content: browser.wait_for_selector(session_id, "{selector}")
4. Extract via JS: browser.evaluate(session_id, "document.querySelector('{selector}').textContent")
5. Or get full HTML: browser.get_content(session_id)
6. Close: browser.close(session_id)"""

    @mcp.prompt()
    def debug_session(session_id: str) -> str:
        """Generate guidance for debugging a browser session."""
        # Try to get current session info
        session = runtime.get_session(session_id)
        if session:
            status_info = f"""- Current URL: {session.current_url or 'N/A'}
- Browser Type: {session.browser_type}
- Headless: {session.headless}"""
        else:
            status_info = "(Session not found - may have been closed)"

        return f"""Debug browser session {session_id}:

Current Status:
{status_info}

Debugging Steps:
1. Check session status: browser.get_session("{session_id}")
2. Get current page content: browser.get_content("{session_id}")
3. Take screenshot: browser.screenshot("{session_id}")
4. Check for JS errors: browser.evaluate("{session_id}", "window.errors || []")
5. List all sessions: browser.list_sessions()

If session not found, it may have been closed or timed out."""
