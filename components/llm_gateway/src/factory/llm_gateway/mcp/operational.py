"""Strict typed operational MCP tools for LLM Gateway."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from factory.mcp_utils.interface import ToolResult, ok, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    ChatInput,
    CompletionInput,
    CompletionOutput,
    EmbeddingInput,
    EmbeddingOutput,
    usage_output,
)

if TYPE_CHECKING:
    from ..runtime.runtime import LLMRuntime


def _completion_output(response: object) -> CompletionOutput:
    """Project a runtime completion response to its safe public DTO."""
    return CompletionOutput(
        content=response.content,
        model=response.model,
        provider=response.provider,
        usage=usage_output(response.usage),
        finish_reason=response.finish_reason,
    )


def register(mcp: Any, get_runtime: Callable[[], "LLMRuntime"]) -> None:
    """Register strict operational tools with raw flat ingress."""

    @typed_tool(mcp)
    @operational(input_model=CompletionInput, output_model=CompletionOutput)
    def llm_complete(
        prompt: str,
        backend: str = "bedrock",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> ToolResult[CompletionOutput]:
        """Generate a completion with server-owned provider configuration."""
        provider = get_runtime().get_provider(backend)
        response = provider.complete(prompt, model, max_tokens, temperature)
        return ok(_completion_output(response))

    @typed_tool(mcp)
    @operational(input_model=ChatInput, output_model=CompletionOutput)
    def llm_chat(
        messages: list[dict],
        backend: str = "bedrock",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> ToolResult[CompletionOutput]:
        """Generate a chat completion from strict message DTOs."""
        from ..runtime.ports import LLMMessage

        provider = get_runtime().get_provider(backend)
        response = provider.chat(
            [LLMMessage(role=message["role"], content=message["content"]) for message in messages],
            model,
            max_tokens,
            temperature,
        )
        return ok(_completion_output(response))

    @typed_tool(mcp)
    @operational(input_model=EmbeddingInput, output_model=EmbeddingOutput)
    def llm_embed(
        texts: list[str],
        backend: str = "bedrock",
        model: str | None = None,
    ) -> ToolResult[EmbeddingOutput]:
        """Generate finite, bounded embeddings through an eligible backend."""
        response = get_runtime().get_embedder(backend).embed(texts, model)
        return ok(EmbeddingOutput(
            embeddings=response.embeddings,
            model=response.model,
            provider=response.provider,
            usage=usage_output(response.usage),
        ))


__all__ = ["register"]
