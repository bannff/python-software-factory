"""Strict DTO for Security view declaration MCP tool."""
from __future__ import annotations
from typing import Any
from .base import DTO
class ViewsOutput(DTO):
    views: list[dict[str, Any]]
