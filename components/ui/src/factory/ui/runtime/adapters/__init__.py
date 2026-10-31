"""Adapters for rendering UI to different targets.

Available adapters:
- JsonAdapter: Generic JSON output for any frontend
- InlineHtmlRenderAdapter: A2UI -> inline-HTML envelope (internal; not the @mcp-ui SDK)
- HTMXAdapter: Server-rendered HTML with HTMX + Alpine + DaisyUI
- ReactAdapter: JSON schema for React/shadcn consumption
- HybridAdapter: Route-based adapter selection
- A2UIAdapter: Google A2UI protocol for agent-generated UI
- FletAdapter: Flutter-based cross-platform UI (web, desktop, mobile)
"""

from .base import RenderAdapter, RenderResult
from .json_adapter import JsonAdapter
from .inline_html_adapter import InlineHtmlRenderAdapter
from .htmx_adapter import HTMXAdapter
from .react_adapter import ReactAdapter
from .hybrid_adapter import HybridAdapter
from .a2ui_adapter import A2UIAdapter, A2UIConfig, create_a2ui_adapter

try:
    from .flet_adapter import FletAdapter
except ImportError:
    FletAdapter = None  # type: ignore[assignment,misc]

__all__ = [
    "RenderAdapter",
    "RenderResult",
    "JsonAdapter",
    "InlineHtmlRenderAdapter",
    "HTMXAdapter",
    "ReactAdapter",
    "HybridAdapter",
    "A2UIAdapter",
    "A2UIConfig",
    "create_a2ui_adapter",
    "FletAdapter",
]
