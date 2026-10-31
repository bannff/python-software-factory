"""Typed MCP surface for origin-session completion delivery."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, deterministic, operational, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .completion_contracts import (
    CompletionAckInput, CompletionOutput, CompletionWriteInput,
    CompletionsOutput, PendingCompletionsInput,
)
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(
        input_model=PendingCompletionsInput, output_model=CompletionsOutput,
    )
    def session_list_pending_completions(
        session_id: str, envelope: dict[str, Any] | None = None,
    ) -> ToolResult[CompletionsOutput]:
        runtime = get_runtime()
        return result(lambda: CompletionsOutput(completions=runtime.completion.pending(
            *identity(runtime.lifecycle, envelope), session_id,
        )))

    @typed_tool(mcp)
    @service_only(callers={"workflow"}, binding="completion")
    @operational(
        input_model=CompletionWriteInput, output_model=CompletionOutput,
        idempotent=False,
    )
    def session_record_completion(
        tenant_id: str, owner_id: str, session_id: str, run_id: str,
        revision: int, result_digest: str, outcome: str, summary: str,
    ) -> ToolResult[CompletionOutput]:
        return result(lambda: CompletionOutput(completion=get_runtime().completion.record(
            tenant_id, owner_id, session_id, run_id,
            outcome, summary, result_digest, revision,
        )))

    @typed_tool(mcp)
    @service_only(callers={"agent"}, binding="completion")
    @operational(
        input_model=CompletionAckInput, output_model=CompletionOutput,
        idempotent=False,
    )
    def session_acknowledge_completion(
        tenant_id: str, owner_id: str, session_id: str, run_id: str,
        revision: int, result_digest: str,
    ) -> ToolResult[CompletionOutput]:
        runtime = get_runtime().completion
        return result(lambda: CompletionOutput(completion=runtime.acknowledge(
            tenant_id, owner_id, session_id, run_id, result_digest, revision,
        )))


__all__ = ["register"]
