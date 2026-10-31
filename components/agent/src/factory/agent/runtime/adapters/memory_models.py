"""Data models for in-memory mock agent runtime.

Contains dataclasses and type definitions used by memory adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockAgent:
    """In-memory agent representation."""
    name: str
    system_prompt: str = ""
    model: str = "mock-model"
    tools: list[Any] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)
    call_count: int = 0
