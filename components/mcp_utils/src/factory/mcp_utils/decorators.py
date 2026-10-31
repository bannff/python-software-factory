"""MCP tool category tags + optional typed ingress/egress boundary.

Compat contract when ``input_model`` is set (one call shape only):
1. flat kwargs matching model fields (MCP / Strands default), OR
2. a single dict positional arg (legacy v1 payload).
Do not mix both in one call.

When the resolved kwargs include a non-empty ``idempotency_key`` and the
tool has an ``output_model`` (typed egress), successful ``ToolResult``s are
replayed from the process-local idempotency cache.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, overload

from pydantic import BaseModel

from .runtime.typed_boundary import apply_category as _apply_category

F = TypeVar("F", bound=Callable[..., Any])


def _category_decorator(category: str) -> Callable[..., Any]:
    @overload
    def deco(func: F) -> F: ...

    @overload
    def deco(
        func: None = None, *,
        input_model: type[BaseModel] | None = None,
        output_model: type[BaseModel] | None = None,
        idempotent: bool = True,
    ) -> Callable[[F], F]: ...

    def deco(
        func: F | None = None, *,
        input_model: type[BaseModel] | None = None,
        output_model: type[BaseModel] | None = None,
        idempotent: bool = True,
    ) -> F | Callable[[F], F]:
        if func is not None:
            return _apply_category(
                func, category, input_model=input_model, output_model=output_model,
                idempotent=idempotent,
            )

        def _bind(fn: F) -> F:
            return _apply_category(
                fn, category, input_model=input_model, output_model=output_model,
                idempotent=idempotent,
            )

        return _bind

    return deco


deterministic = _category_decorator("deterministic")
operational = _category_decorator("operational")
authoring = _category_decorator("authoring")
