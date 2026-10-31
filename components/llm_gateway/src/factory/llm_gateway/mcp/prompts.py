"""MCP Prompt registration for LLM Gateway brick.

Prompts provide guided workflows for common tasks:
- Configuring LLM backends
- Debugging LLM issues
- Optimizing prompts and costs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES, BACKEND_GUIDES

if TYPE_CHECKING:
    from ..runtime.runtime import LLMRuntime


def register(mcp: Any, get_runtime: Callable[[], "LLMRuntime"]) -> None:
    """Register all LLM Gateway prompts with the MCP server."""

    @mcp.prompt()
    def configure_backend(backend: str = "bedrock") -> str:
        """Generate guidance for setting up an LLM backend."""
        backend = backend.lower()
        if backend not in BACKEND_GUIDES:
            backend = "bedrock"

        guide = BACKEND_GUIDES[backend]
        runtime = get_runtime()
        health = runtime.health_check()

        current_config = (
            "No active providers" if not health else f"Active providers: {len(health)}"
        )

        return PROMPT_TEMPLATES["configure_backend"]["template"].format(
            backend=backend,
            current_config=current_config,
            setup_guide=guide["setup_guide"],
            config_params=guide["config_params"],
        )

    @mcp.prompt()
    def debug_llm(backend: str = "bedrock", issue: str = "") -> str:
        """Generate guidance for debugging LLM issues."""
        return PROMPT_TEMPLATES["debug_llm"]["template"].format(
            backend=backend,
            issue=issue or "LLM not responding as expected",
        )

    @mcp.prompt()
    def optimize_prompts(
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate guidance for prompt optimization."""
        # Analyze temperature
        if temperature < 0.3:
            temp_analysis = "Low temperature - deterministic but may lack creativity"
            rec_temp = "0.3-0.5 for balanced output"
        elif temperature > 0.8:
            temp_analysis = "High temperature - creative but may be inconsistent"
            rec_temp = "0.5-0.7 for more consistent output"
        else:
            temp_analysis = "Balanced temperature"
            rec_temp = str(temperature)

        # Analyze max_tokens
        if max_tokens < 256:
            token_analysis = "Low token limit - may truncate responses"
            rec_tokens = "512-1024 for complete responses"
        elif max_tokens > 4096:
            token_analysis = "High token limit - may increase costs"
            rec_tokens = "1024-2048 for most use cases"
        else:
            token_analysis = "Reasonable token limit"
            rec_tokens = str(max_tokens)

        return PROMPT_TEMPLATES["optimize_prompts"]["template"].format(
            current_usage="See health_check() for active providers",
            token_analysis=token_analysis,
            quality_analysis="Run test completions to assess quality",
            temperature=temperature,
            rec_temperature=rec_temp,
            max_tokens=max_tokens,
            rec_max_tokens=rec_tokens,
            model_recommendations="Use Claude Sonnet 4.5/GPT-4o for quality, Claude Haiku 4.5/Nova 2 Lite for speed",
        )
