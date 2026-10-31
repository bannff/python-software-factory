"""Category-neutral typed FastMCP boundary decorator."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from .decorators import _apply_category


def typed(func: Any = None, *, input_model: type[BaseModel] | None = None,
          output_model: type[BaseModel] | None = None) -> Any:
    """Add strict typed ingress/egress without assigning an MCP category."""
    if func is not None:
        return _apply_category(func, None, input_model=input_model, output_model=output_model)

    def bind(function: Callable[..., Any]) -> Any:
        return _apply_category(function, None, input_model=input_model, output_model=output_model)

    return bind
