"""Provider-neutral model selection for experiments and the LLM judge.

A bare model id keeps meaning Bedrock (the historical default). An id with the
``ollama:`` prefix targets a local Ollama server through its OpenAI-compatible
endpoint, so evals can run on a machine with no cloud credentials. One env var,
``COMPANION_X_EVAL_MODEL``, picks the default for both the evaluated agent and,
unless ``COMPANION_X_EVAL_JUDGE_MODEL`` overrides it, the judge.
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
OLLAMA_PREFIX = "ollama:"


def default_model_id() -> str:
    return os.getenv("COMPANION_X_EVAL_MODEL") or DEFAULT_BEDROCK_MODEL


def _ollama_client_args() -> dict[str, str]:
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1",
        "api_key": os.getenv("OLLAMA_API_KEY") or "ollama",
    }


def resolve_agent_model(model_id: str) -> Any:
    """Strands accepts a Bedrock id string, or a model object for other providers."""
    if model_id.startswith(OLLAMA_PREFIX):
        from strands.models.openai import OpenAIModel
        return OpenAIModel(
            client_args=_ollama_client_args(), model_id=model_id[len(OLLAMA_PREFIX):],
        )
    return model_id


def resolve_judge_model(model_id: str) -> Any:
    from langchain.chat_models import init_chat_model
    if model_id.startswith(OLLAMA_PREFIX):
        return init_chat_model(f"openai:{model_id[len(OLLAMA_PREFIX):]}", **_ollama_client_args())
    return init_chat_model(f"bedrock_converse:{model_id}")


_UNAVAILABLE_HINTS = (
    "credentials", "bedrock", "connection", "connect", "endpoint", "unreachable",
    "ollama", "openai", "authentication", "timed out", "resolve",
)


def is_model_unavailable(error: BaseException) -> bool:
    """True when a run failed because the evaluation model could not be reached."""
    text = f"{type(error).__name__} {error}".lower()
    return any(hint in text for hint in _UNAVAILABLE_HINTS)
