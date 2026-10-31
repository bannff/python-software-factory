"""First-party mcp-ui UIResource paint carrier (carrier #5)."""
from __future__ import annotations

import uuid
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .paint_dtos import UIResourcePaintInput, UIResourcePaintOutput

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

_MIME_BY_MODE = {
    "inline_html": "text/html;profile=mcp-app",
    "external_url": "text/uri-list",
    "remote_dom": "application/vnd.mcp-ui.remote-dom+javascript",
}


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the first-party UIResource paint tool."""
    del get_runtime

    @mcp.tool()
    @operational(input_model=UIResourcePaintInput, output_model=UIResourcePaintOutput)
    def ui_paint_uiresource(
        body: Any, mode: Any = "remote_dom", name: Any = None,
        uri_suffix: Any = None,
    ) -> ToolResult[UIResourcePaintOutput]:
        """Paint a spec-nested mcp-ui resource inline in the chat panel.

        The success ``data`` is the unmodified resource carrier map. It stays
        typed under the outer ToolResult envelope, so Any transports the
        envelope instead of bypassing typed egress for an EmbeddedResource.
        """
        if mode not in _MIME_BY_MODE:
            return fail(f"Invalid mode {mode!r}; expected one of {tuple(_MIME_BY_MODE)}")
        if not isinstance(body, str):
            return fail("body must be a string")
        if not body:
            return fail("body must not be empty")
        if name is not None and not isinstance(name, str):
            return fail("name must be a string or null")
        if uri_suffix is not None and not isinstance(uri_suffix, str):
            return fail("uri_suffix must be a string or null")
        suffix = uri_suffix or str(uuid.uuid4())
        return UIResourcePaintOutput(
            type="resource",
            resource={"uri": f"ui://factory/{suffix}", "mimeType": _MIME_BY_MODE[mode], "text": body},
            _factory_name=name or "UIResource", _factory_mode=mode,
        )
