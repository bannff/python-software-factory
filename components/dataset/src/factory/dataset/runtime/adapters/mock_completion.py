"""Deterministic in-memory CompletionPort adapter for tests and dev.

Returns queued responses FIFO (or a responder callable's output) and records
every call so tests can assert on prompts, system prompts, and sampling
parameters without any network or model dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MockCompletionAdapter:
    """CompletionPort test double with scripted, deterministic responses."""

    def __init__(
        self,
        responses: list[str] | None = None,
        responder: Callable[[str], str] | None = None,
        default: str = "mock response",
        model_id: str = "mock/deterministic",
    ) -> None:
        self._responses = list(responses or [])
        self._responder = responder
        self._default = default
        self.model_id = model_id
        self.calls: list[dict[str, Any]] = []

    def get_completion(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        if self._responses:
            return self._responses.pop(0)
        if self._responder is not None:
            return self._responder(prompt)
        return self._default
