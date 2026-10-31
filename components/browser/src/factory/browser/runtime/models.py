"""Pydantic models for browser component."""

from typing import Any

from pydantic import BaseModel, Field


class BrowserConfig(BaseModel):
    """Browser launch configuration."""

    headless: bool = True
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)
    user_agent: str | None = None
    proxy: str | None = None


class PageInfo(BaseModel):
    """Information about a browser page."""

    url: str
    title: str
    status_code: int | None = None
    load_time_ms: int | None = None


class ElementInfo(BaseModel):
    """Information about a DOM element."""

    tag: str
    text: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    visible: bool = True
    bounds: dict[str, int] | None = None


class SessionInfo(BaseModel):
    """Browser session information."""

    session_id: str
    browser_type: str
    headless: bool
    current_url: str | None = None
    created_at: str
    page_count: int = 1


class ClickResult(BaseModel):
    """Result of a click action."""

    success: bool
    selector: str
    element: ElementInfo | None = None
    error: str | None = None


class TypeResult(BaseModel):
    """Result of a type action."""

    success: bool
    selector: str
    text_length: int
    error: str | None = None


class EvaluateResult(BaseModel):
    """Result of JavaScript evaluation."""

    success: bool
    result: Any = None
    error: str | None = None
