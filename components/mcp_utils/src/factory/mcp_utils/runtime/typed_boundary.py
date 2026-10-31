"""Execution boundary for typed MCP category decorators."""

from __future__ import annotations

import asyncio
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from ..context import get_envelope
from ..service_only import authorize_service_boundary
from .schema_migration import migrate_to
from .typed_service_entry import (
    install_service_entry_dependency, pop_service_entry,
)
from .typed_egress import cache_egress, safe_egress, validate_idempotency_key
from .tool_failure import tool_execution_failure, tool_idempotency_conflict

F = TypeVar("F", bound=Callable[..., Any])


def _tag(fn: Any, category: str | None, input_model: Any, output_model: Any) -> None:
    if category is not None:
        setattr(fn, "_mcp_category", category)
    if input_model is not None:
        setattr(fn, "_mcp_input_model", input_model)
    if output_model is not None:
        setattr(fn, "_mcp_output_model", output_model)


def ingress_kwargs(input_model: type[BaseModel], args: tuple, kwargs: dict) -> dict:
    if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
        payload = args[0]
    elif not args:
        payload = dict(kwargs)
    else:
        raise TypeError(
            f"{input_model.__name__} ingress expects flat kwargs or a single "
            "dict positional arg, not mixed args"
        )
    if getattr(input_model, "preserve_domain_schema_version", False):
        model = input_model.model_validate(payload)
    else:
        model = migrate_to(payload, input_model)
    data = model.model_dump()
    if not getattr(input_model, "preserve_domain_schema_version", False):
        data.pop("schema_version", None)
    return data


def _scope_for(func: Callable[..., Any]) -> str:
    return f"{func.__module__}.{func.__qualname__}"


_INVALID_KEY = object()


def _validated_key(
    call_kwargs: dict[str, Any], func: Callable[..., Any], *,
    allow_ambient: bool,
) -> Any:
    key = call_kwargs.get("idempotency_key")
    if key is None and allow_ambient:
        envelope = get_envelope() or {}
        attributes = envelope.get("attributes")
        if isinstance(attributes, dict):
            key = attributes.get("workflow_attempt_id") or attributes.get(
                "idempotency_key",
            )
    if key is None:
        return None
    try:
        return validate_idempotency_key(key)
    except Exception:
        return _INVALID_KEY


def apply_category(
    func: F, category: str | None, *, input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None, idempotent: bool = True,
) -> F:
    _tag(func, category, input_model, output_model)
    if input_model is None and output_model is None:
        return func

    if iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from factory.mcp_utils.runtime import idempotency

            call_args, call_kwargs = args, dict(kwargs)
            entry = pop_service_entry(call_kwargs)
            authorize_service_boundary(
                async_wrapper, call_args, call_kwargs, entry,
            )
            if input_model is not None:
                call_kwargs = ingress_kwargs(input_model, call_args, call_kwargs)
                call_args = ()
            idem_key = (
                _validated_key(call_kwargs, func, allow_ambient=True)
                if idempotent and output_model is not None else None
            )
            if idem_key is _INVALID_KEY:
                return tool_execution_failure(func)
            scope = _scope_for(func)
            claim = None
            if idem_key and output_model is not None:
                try:
                    decision = idempotency.lookup_or_claim(
                        idempotency.build_identity(
                            scope, idem_key, func, call_args, call_kwargs,
                        )
                    )
                except ValueError:
                    return tool_execution_failure(func)
                if decision.action == "hit":
                    return safe_egress(decision.result, output_model, func)
                if decision.action == "conflict":
                    return tool_idempotency_conflict(func)
                if decision.action == "wait" and decision.flight is not None:
                    result = await asyncio.to_thread(
                        idempotency.wait_for, decision.flight,
                    )
                    return safe_egress(result, output_model, func)
                claim = decision.flight
            if output_model is None:
                return await func(*call_args, **call_kwargs)
            try:
                result = await func(*call_args, **call_kwargs)
            except asyncio.CancelledError:
                if claim is not None:
                    idempotency.complete(claim, tool_execution_failure(func))
                raise
            except Exception:
                result = tool_execution_failure(func)
            return cache_egress(
                safe_egress(result, output_model, func), idem_key, scope, func,
                claim=claim,
            )

        _tag(async_wrapper, category, input_model, output_model)
        install_service_entry_dependency(async_wrapper, func)
        return async_wrapper  # type: ignore[return-value]

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from factory.mcp_utils.runtime import idempotency

        call_args, call_kwargs = args, dict(kwargs)
        entry = pop_service_entry(call_kwargs)
        authorize_service_boundary(wrapper, call_args, call_kwargs, entry)
        if input_model is not None:
            call_kwargs = ingress_kwargs(input_model, call_args, call_kwargs)
            call_args = ()
        idem_key = (
            _validated_key(call_kwargs, func, allow_ambient=True)
            if idempotent and output_model is not None else None
        )
        if idem_key is _INVALID_KEY:
            return tool_execution_failure(func)
        scope = _scope_for(func)
        claim = None
        if idem_key and output_model is not None:
            try:
                decision = idempotency.lookup_or_claim(
                    idempotency.build_identity(
                        scope, idem_key, func, call_args, call_kwargs,
                    )
                )
            except ValueError:
                return tool_execution_failure(func)
            if decision.action == "hit":
                return safe_egress(decision.result, output_model, func)
            if decision.action == "conflict":
                return tool_idempotency_conflict(func)
            if decision.action == "wait" and decision.flight is not None:
                return safe_egress(
                    idempotency.wait_for(decision.flight), output_model, func,
                )
            claim = decision.flight
        if output_model is None:
            return func(*call_args, **call_kwargs)
        try:
            result = func(*call_args, **call_kwargs)
        except Exception:
            result = tool_execution_failure(func)
        return cache_egress(
            safe_egress(result, output_model, func), idem_key, scope, func,
            claim=claim,
        )

    _tag(wrapper, category, input_model, output_model)
    install_service_entry_dependency(wrapper, func)
    return wrapper  # type: ignore[return-value]


__all__ = ["apply_category", "ingress_kwargs"]
