"""Default execution bounds for Strands graphs (bd:python-factory-h5mju).

A Strands ``GraphBuilder`` (1.50.2) hardcodes ``_max_node_executions`` /
``_execution_timeout`` / ``_node_timeout`` to None in ``__init__`` = truly
UNBOUNDED, and warns "Graph without execution limits may run indefinitely if
cycles exist" when BOTH max_node_executions AND execution_timeout are None
(strands/multiagent/graph.py:490). The platform bounds every graph by default
so a user never has to ask for limits.

This module is the single source of truth — no magic numbers scattered across
build sites. Env vars override; an unset or non-positive value ALWAYS resolves
to the default (None/0 never means "unlimited"). Hitting max_node_executions /
execution_timeout is GRACEFUL (GraphState.should_continue -> status=FAILED, no
exception); only node_timeout raises (handled at the spawn call sites).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_ENV_MAX_NODE_EXECUTIONS = "COMPANION_X_GRAPH_MAX_NODE_EXECUTIONS"
_ENV_EXECUTION_TIMEOUT = "COMPANION_X_GRAPH_EXECUTION_TIMEOUT"
_ENV_NODE_TIMEOUT = "COMPANION_X_GRAPH_NODE_TIMEOUT"
_MIN_MAX_NODE_EXECUTIONS = 25
_PER_NODE_EXECUTION_BUDGET = 5
_DEFAULT_EXECUTION_TIMEOUT = 1800.0
_DEFAULT_NODE_TIMEOUT = 300.0

__all__ = ["apply_execution_bounds", "default_max_node_executions"]


def _env_positive_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer %s=%r", name, raw)
        return None
    return value if value > 0 else None


def _env_positive_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Ignoring non-float %s=%r", name, raw)
        return None
    return value if value > 0 else None


def default_max_node_executions(node_count: int) -> int:
    """Resolve the platform default node-execution cap (single source of truth).

    Env override wins when positive; otherwise a per-node budget floored at a
    hard minimum. An unset/non-positive env value NEVER means "unlimited".
    """
    env_value = _env_positive_int(_ENV_MAX_NODE_EXECUTIONS)
    if env_value is not None:
        return env_value
    return max(_MIN_MAX_NODE_EXECUTIONS, _PER_NODE_EXECUTION_BUDGET * max(node_count, 0))


def _set_if_unset(builder: Any, attr: str, setter: str, value: Any) -> None:
    """Set a builder limit ONLY if the builder still holds None for it.

    Preserves any explicit override a caller already applied. Guards on the
    setter's presence so plain test doubles that don't model the private attr
    are a no-op rather than an AttributeError.
    """
    if getattr(builder, attr, None) is not None:
        return
    fn = getattr(builder, setter, None)
    if fn is None:
        return
    fn(value)
    logger.info("Graph execution bounds: injected %s=%s", attr.lstrip("_"), value)


def apply_execution_bounds(builder: Any, node_count: int) -> None:
    """Bound a Strands ``GraphBuilder`` by default; never leave it unbounded.

    Sets max_node_executions / execution_timeout / node_timeout, each ONLY when
    the builder still holds None for it — an explicit caller override is
    preserved. Unset (or None/0 via env) always resolves to a platform default,
    so the "run indefinitely" warning condition can never be met on a builder
    that passes through here.
    """
    max_executions = default_max_node_executions(node_count)
    execution_timeout = _env_positive_float(_ENV_EXECUTION_TIMEOUT) or _DEFAULT_EXECUTION_TIMEOUT
    node_timeout = _env_positive_float(_ENV_NODE_TIMEOUT) or _DEFAULT_NODE_TIMEOUT
    _set_if_unset(builder, "_max_node_executions", "set_max_node_executions", max_executions)
    _set_if_unset(builder, "_execution_timeout", "set_execution_timeout", execution_timeout)
    _set_if_unset(builder, "_node_timeout", "set_node_timeout", node_timeout)
