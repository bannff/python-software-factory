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

from .model_resolver import DEFAULT_BEDROCK_MODEL, default_model_id, resolve_judge_model

DEFAULT_JUDGE_MODEL = DEFAULT_BEDROCK_MODEL
_ENV = "COMPANION_X_EVAL_JUDGE_MODEL"


def judge_model_id() -> str:
    """Return the configured judge model id (env override or default)."""
    return os.getenv(_ENV) or default_model_id()


def get_judge_model() -> Any:
    """Return the judge chat model (Bedrock for bare ids, local Ollama for ollama:<model>)."""
    return resolve_judge_model(judge_model_id())
