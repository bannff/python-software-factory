"""Polylith Interface for evals module."""

from .server import create_mcp_server as create_server
from .runtime.runtime import EvalsRuntime as Runtime
from .runtime.runtime import get_runtime, reset_runtime
from .runtime.run_record_verifier import verify_record_pointer
from .runtime.review_policy import REVIEW_TOOL_SCOPE, ReviewPolicy, get_review_policy
from .runtime.ports import (
    EvalRunner,
    EvalPersistencePort,
    EvalCase,
    EvalResult,
    EvalSuite,
    EvalRun,
    EvalMetrics,
    EvalHealth,
    EvalAgentConfig,
    ExperimentConfig,
    ExperimentReport,
)

__all__ = [
    "create_server",
    "Runtime",
    "EvalRunner",
    "EvalPersistencePort",
    "EvalCase",
    "EvalResult",
    "EvalSuite",
    "EvalRun",
    "EvalMetrics",
    "EvalHealth",
    "EvalAgentConfig",
    "ExperimentConfig",
    "ExperimentReport",
    "get_runtime",
    "reset_runtime",
    "REVIEW_TOOL_SCOPE", "ReviewPolicy", "get_review_policy",
    "verify_record_pointer",
]
