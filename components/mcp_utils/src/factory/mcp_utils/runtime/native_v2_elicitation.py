"""MCP 2.1.1 adapter for the neutral one-round elicitation contracts."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Callable

from pydantic import BaseModel

from .elicitation import (
    ElicitationResponse,
    PrepareCallable,
    PrepareNeedsElicitation,
    PrepareReady,
)
from .tool_result import ToolResult, fail
from .typed_boundary import ingress_kwargs


async def run_preparation(
    handler: Callable[..., Any],
    prepare: PrepareCallable,
    arguments: Mapping[str, Any],
    input_responses: Any,
) -> PrepareReady | ToolResult[Any] | Any:
    """Validate ingress, prepare without effects, and adapt one MRTR round."""
    model = _input_model(handler)
    validated = ingress_kwargs(model, (), dict(arguments))
    initial = await _call_prepare(prepare, validated, None)
    if isinstance(initial, PrepareReady):
        if input_responses is not None:
            return fail("unexpected elicitation response")
        return initial
    if not isinstance(initial, PrepareNeedsElicitation):
        raise TypeError("prepare must return PrepareReady or PrepareNeedsElicitation")
    request = initial.request
    if input_responses is None:
        return _input_required(request)
    response = _response_for(request.key, input_responses)
    if isinstance(response, ToolResult):
        return response
    if response.action != "accept":
        reason = "elicitation declined" if response.action == "decline" else "elicitation cancelled"
        return fail(reason)
    try:
        accepted = request.response_model.model_validate(dict(response.content or {}))
    except Exception:
        return fail("invalid elicitation response")
    neutral = ElicitationResponse("accept", accepted.model_dump())
    ready = await _call_prepare(prepare, validated, neutral)
    if isinstance(ready, PrepareNeedsElicitation):
        return _input_required(ready.request)
    if not isinstance(ready, PrepareReady):
        raise TypeError("prepare must return PrepareReady or PrepareNeedsElicitation")
    return ready


async def _call_prepare(
    prepare: PrepareCallable,
    arguments: Mapping[str, Any],
    response: ElicitationResponse | None,
) -> Any:
    result = prepare(arguments, response)
    return await result if inspect.isawaitable(result) else result


def _input_model(handler: Callable[..., Any]) -> type[BaseModel]:
    model = getattr(handler, "_mcp_input_model", None)
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError("interactive native tools require a typed MCP input model")
    return model


def _input_required(request: Any) -> Any:
    from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult

    form = request.form
    return InputRequiredResult(input_requests={
        request.key: ElicitRequest(params=ElicitRequestFormParams(
            mode="form", message=form.message, requested_schema=form.requested_schema,
        )),
    })


def _response_for(key: str, responses: Any) -> ElicitationResponse | ToolResult[Any]:
    from mcp.types import ElicitResult

    if not isinstance(responses, Mapping) or set(responses) != {key}:
        return fail("invalid elicitation response keys")
    response = responses[key]
    if not isinstance(response, ElicitResult):
        return fail("invalid elicitation response type")
    if response.action == "accept":
        if not isinstance(response.content, Mapping):
            return fail("accepted elicitation response requires content")
        return ElicitationResponse("accept", dict(response.content))
    if response.content is not None:
        return fail("non-accepted elicitation response cannot carry content")
    return ElicitationResponse(response.action)


__all__ = ["run_preparation"]
