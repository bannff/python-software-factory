"""Shared Bedrock judge chat model for LLM-as-judge + SDK evaluators.

A LangChain Bedrock chat model is used as the judge so no ``OPENAI_API_KEY``
is required. The model id defaults to Claude Sonnet 4.5 and is overridable
via ``COMPANION_X_EVAL_JUDGE_MODEL``. Imports are lazy so importing this
module never drags in LangChain.

Lives at the adapters level (not inside ``evaluator_providers/``) because it
is shared infra: both the provider rail and the SDK Experiment factory
(``evaluator_factory``) inject the same judge model.
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_JUDGE_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_ENV = "COMPANION_X_EVAL_JUDGE_MODEL"


def judge_model_id() -> str:
    """Return the configured judge model id (env override or default)."""
    return os.getenv(_ENV) or DEFAULT_JUDGE_MODEL


def get_judge_model() -> Any:
    """Return a LangChain Bedrock chat model instance (lazy import)."""
    model_id = judge_model_id()
    from langchain.chat_models import init_chat_model

    return init_chat_model(f"bedrock_converse:{model_id}")
