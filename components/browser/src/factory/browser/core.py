"""Core types and constants for browser component."""

from enum import Enum
from typing import Any

# Component metadata
COMPONENT_NAME = "browser"
COMPONENT_VERSION = "0.1.0"


class BrowserType(str, Enum):
    """Supported browser types."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class ElementSelector(str, Enum):
    """Element selector strategies."""
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ID = "id"


# Default configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "headless": True,
    "timeout_ms": 30000,
    "viewport_width": 1280,
    "viewport_height": 720,
    "user_agent": None,
}
