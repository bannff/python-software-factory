"""Bind invocation context only while advancing a LangChain source stream."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .langchain_tools import bind_invocation, reset_invocation


async def invocation_stream(source: Any, request: Any) -> AsyncIterator[Any]:
    """Advance each graph step under context, then release before yielding."""
    iterator = source.__aiter__()
    while True:
        token = bind_invocation(request)
        try:
            item = await anext(iterator)
        except StopAsyncIteration:
            return
        finally:
            reset_invocation(token)
        yield item


__all__ = ["invocation_stream"]
