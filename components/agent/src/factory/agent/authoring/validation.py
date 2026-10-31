"""Validation utilities for authoring operations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from factory.agent.registry.agents import AgentConfig
from factory.agent.registry.graphs import GraphConfig
from factory.agent.registry.swarms import SwarmConfig
from factory.agent.runtime.registry_contracts import SquadConfig


ConfigKind = Literal["agent", "swarm", "graph", "squad", "settings", "tool"]

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_TOOL_MODULE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")


class AuthoringError(ValueError):
    """Error raised during authoring operations."""
    pass


def assert_within_root(root: Path, candidate: Path) -> None:
    """Ensure candidate path is within root directory."""
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as e:
        raise AuthoringError("Path escapes config root") from e


def ensure_id(value: str) -> str:
    """Validate and return an ID string."""
    if not _ID_RE.match(value):
        raise AuthoringError("Invalid id; expected [a-z0-9][a-z0-9_-]{0,127}")
    return value


def ensure_tool_module(value: str) -> str:
    """Validate and return a tool module name."""
    if not _TOOL_MODULE_RE.match(value):
        raise AuthoringError("Invalid tool module name; expected a valid Python identifier")
    return value


def validate_config(kind: ConfigKind, config: dict[str, Any]) -> dict[str, Any]:
    """Validate config content using Pydantic models."""
    try:
        if kind == "agent":
            AgentConfig.model_validate(config)
        elif kind == "swarm":
            SwarmConfig.model_validate(config)
        elif kind == "graph":
            GraphConfig.model_validate(config)
        elif kind == "squad":
            SquadConfig.model_validate(config)
        elif kind == "settings":
            if not isinstance(config, dict):
                raise AuthoringError("settings must be a mapping")
        elif kind == "tool":
            raise AuthoringError("Use validate_tool_module for tool code")
        else:
            raise AuthoringError(f"Unknown kind: {kind}")
        return {"ok": True}
    except Exception as e:
        details = getattr(e, "errors", None)
        return {"ok": False, "error": str(e), "details": details() if callable(details) else None}


def validate_tool_module(code: str) -> dict[str, Any]:
    """Validate Python syntax for a tool module."""
    try:
        compile(code, "<tool_module>", "exec")
        return {"ok": True}
    except SyntaxError as e:
        return {
            "ok": False,
            "error": f"SyntaxError: {e.msg}",
            "details": {"lineno": e.lineno, "offset": e.offset, "text": e.text},
        }
