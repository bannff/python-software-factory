"""Typed MCP egress conversion, failure normalization, and replay stamping."""
from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

from .bounded_json import to_plain_json
from .tool_failure import tool_execution_failure
from .tool_result import ToolResult, with_idempotency_key

_MAX_RESULT_BYTES = 16 * 1024 * 1024


def validate_idempotency_key(key: Any) -> str:
    """Validate and return a non-empty string key for typed replay."""
    if not isinstance(key, str) or not key:
        raise ValueError("idempotency_key must be a non-empty string")
    return ToolResult(idempotency_key=key).idempotency_key or ""


def _checked(envelope: ToolResult[Any]) -> ToolResult[Any]:
    try:
        encoded = json.dumps(
            to_plain_json(envelope.model_dump(mode="python")),
            ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("typed MCP result is not JSON-safe") from exc
    if len(encoded) > _MAX_RESULT_BYTES:
        raise ValueError("typed MCP result exceeds the size limit")
    return envelope


def _egress(result: Any, output_model: type[BaseModel]) -> Any:
    from .tool_result import ok

    if result is None:
        if getattr(output_model, "allows_null", False):
            return _checked(ok(None))
        raise ValueError("successful typed MCP result cannot be null")
    if isinstance(result, ToolResult):
        if not result.ok:
            return result
        data = result.data
        if data is None:
            if not getattr(output_model, "allows_null", False):
                raise ValueError("successful typed MCP result cannot be null")
        else:
            if isinstance(data, BaseModel):
                data = data.model_dump(mode="python")
            data = output_model.model_validate(data)
        return _checked(ToolResult(
            schema_version=result.schema_version,
            ok=result.ok,
            data=data,
            error=result.error,
            idempotency_key=result.idempotency_key,
        ))
    if isinstance(result, output_model):
        return _checked(ok(result))
    if isinstance(result, BaseModel):
        return _checked(ok(output_model.model_validate(result.model_dump())))
    if isinstance(result, dict):
        return _checked(ok(output_model.model_validate(result)))
    return _checked(ok(output_model.model_validate({"value": result})))


def safe_egress(
    result: Any, output_model: type[BaseModel], func: Callable[..., Any],
) -> Any:
    """Convert output or return the stable public failure envelope."""
    try:
        return _egress(result, output_model)
    except Exception:
        return tool_execution_failure(func)


def cache_egress(
    result: Any, key: Any, scope: str, func: Callable[..., Any],
    *, claim: Any = None,
) -> Any:
    """Stamp a result and complete the sole idempotency owner, if present."""
    from . import idempotency

    if not key or not isinstance(result, ToolResult):
        if claim is not None:
            return idempotency.complete(claim, tool_execution_failure(func))
        return result
    try:
        key_text = validate_idempotency_key(key)
        stamped = with_idempotency_key(result, key_text)
        if claim is not None:
            return idempotency.complete(claim, stamped)
        return stamped
    except Exception:
        if claim is not None:
            return idempotency.complete(
                claim, tool_execution_failure(func),
            )
        return tool_execution_failure(func)


__all__ = ["cache_egress", "safe_egress", "validate_idempotency_key"]
