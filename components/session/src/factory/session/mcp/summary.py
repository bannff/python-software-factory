"""Operational typed MCP tool for generating a session's rolling summary
(row 18, feature-map).

Split into its own module for the same reason ``active_checkpoint.py``/
``fork.py`` are split from ``operational.py`` — a genuinely separate
lifecycle concern, kept out of the already near-ceiling ``operational.py``.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, operational
from factory.mcp_utils.registration import typed_tool

from .grouping_contracts import GenerateSummaryInput
from .lifecycle_contracts import SessionOutput
from .lifecycle_support import _ERRORS, identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=GenerateSummaryInput, output_model=SessionOutput)
    def session_generate_summary(
        session_id: str, excerpt: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        """Row 18 — a rolling conversation summary, the read/regenerate
        surface upstream exposes as the chat Summary tab. The FE supplies
        the transcript excerpt (the session brick stays free of chat-
        transcript knowledge, exactly like ``session_generate_title``);
        this resolves the session's OWN configured model, generates the
        summary, and applies it through the SAME revision-fenced write
        every other mutation uses. The stored summary is then read back
        as an ordinary field of the session record (``session_get``)."""
        from factory.session.runtime.summary_generation import (
            SummaryGenerationError, generate_summary,
        )
        runtime = get_runtime().lifecycle
        tenant_id, owner_id = identity(runtime, envelope)
        try:
            session = runtime.get(tenant_id, owner_id, session_id)
        except tuple(_ERRORS) as exc:
            return fail(_ERRORS[type(exc)])
        try:
            summary = generate_summary(session.model, excerpt)
        except SummaryGenerationError:
            return fail("session_summary_generation_unavailable")
        return result(lambda: SessionOutput(session=runtime.set_summary(
            tenant_id, owner_id, session_id, summary, expected_revision,
        )))


__all__ = ["register"]
