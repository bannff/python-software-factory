"""Strict DTOs for operational Browser MCP tools."""
from __future__ import annotations

from pydantic import Field, field_validator

from .base import DTO, EmptyInput, JsonValue, SessionOutput, _validate_json


class LaunchInput(DTO):
    headless: bool = True
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)
    user_agent: str | None = None


class LaunchOutput(DTO):
    session: SessionOutput


class CloseInput(DTO):
    session_id: str


class CloseOutput(DTO):
    session_id: str


class NavigateInput(DTO):
    session_id: str
    url: str


class NavigateOutput(DTO):
    url: str
    title: str
    status_code: int | None = None
    frame_id: str | None = None


class ContentInput(DTO):
    session_id: str


class ContentOutput(DTO):
    content: str
    length: int


class ScreenshotInput(DTO):
    session_id: str
    full_page: bool = False


class ScreenshotOutput(DTO):
    format: str
    data: str
    size_bytes: int


class ClickInput(DTO):
    session_id: str
    selector: str
    selector_type: str = "css"


class ClickOutput(DTO):
    success: bool
    selector: str
    clicked: bool | None = None
    error: str | None = None


class TypeTextInput(DTO):
    session_id: str
    selector: str
    text: str
    selector_type: str = "css"


class TypeTextOutput(DTO):
    success: bool
    selector: str
    text_length: int
    error: str | None = None


class EvaluateInput(DTO):
    session_id: str
    script: str


class EvaluateOutput(DTO):
    result: JsonValue = None

    @field_validator("result")
    @classmethod
    def _json_safe(cls, value: JsonValue) -> JsonValue:
        return _validate_json(value)


class WaitForSelectorInput(DTO):
    session_id: str
    selector: str
    timeout_ms: int = 30000


class WaitForSelectorOutput(DTO):
    found: bool
    selector: str
    waited_ms: int | None = None
    timeout: bool | None = None


class EngineSmokeInput(EmptyInput):
    pass


class EngineSmokeOutput(DTO):
    """Result of launching and closing one headless session on the active engine."""

    engine: str
    ok: bool
    browser_type: str | None = None
    error: str | None = None
    elapsed_ms: int
