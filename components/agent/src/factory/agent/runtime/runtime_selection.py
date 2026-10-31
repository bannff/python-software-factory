"""Strict trusted configuration for Agent runtime adapter selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class AgentRuntimeConfigError(RuntimeError):
    """The trusted runtime-selection config could not be read."""


class AgentRuntimeSelection(BaseModel):
    """Versioned project-owned selection of one registered runtime bundle."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["v1"] = "v1"
    runtime_adapter_id: str = Field(min_length=1, max_length=128)
    options: dict[str, Any] = Field(default_factory=dict)


def load_runtime_selection(path: str | Path | None = None) -> AgentRuntimeSelection:
    """Load trusted YAML, with one temporary env compatibility fallback."""
    configured = path or os.getenv("AGENT_RUNTIME_CONFIG")
    if configured:
        selection_path = Path(configured)
        try:
            text = selection_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AgentRuntimeConfigError(
                f"Agent runtime config cannot be read: {selection_path} "
                f"({exc.strerror or type(exc).__name__}; from "
                f"{'the path argument' if path is not None else 'AGENT_RUNTIME_CONFIG'}). "
                "Point AGENT_RUNTIME_CONFIG at an existing readable YAML file, or "
                "unset it to fall back to AGENT_RUNTIME_ADAPTER / the built-in "
                "strands default (AGENT_RUNTIME_ADAPTER=langchain restores the "
                "dormant langchain-langgraph adapter)."
            ) from exc
        return AgentRuntimeSelection.model_validate(yaml.safe_load(text))
    legacy = os.getenv("AGENT_RUNTIME_ADAPTER")
    return AgentRuntimeSelection(
        runtime_adapter_id=legacy or "strands",
    )


__all__ = ["AgentRuntimeConfigError", "AgentRuntimeSelection", "load_runtime_selection"]
