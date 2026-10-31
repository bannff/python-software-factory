"""Concurrency-safe managed graph execution context."""
from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ManagedRunContext:
    run_id: str
    attempt_id: str
    attempt_revision: int
    execution_mode: str
    graph_id: str
    graph_definition_digest: str
    input_manifest_digest: str

    def attributes(self) -> dict[str, str]:
        return {
            "managed_graph.attempt_id": self.attempt_id,
            "managed_graph.attempt_revision": str(self.attempt_revision),
            "managed_graph.execution_mode": self.execution_mode,
            "managed_graph.graph_id": self.graph_id,
            "managed_graph.graph_definition_digest": self.graph_definition_digest,
            "managed_graph.input_manifest_digest": self.input_manifest_digest,
        }

    def invocation_state(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            **context,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "revision": self.attempt_revision,
            "execution_mode": self.execution_mode,
            "durable": True,
            "graph_id": self.graph_id,
            "graph_definition_digest": self.graph_definition_digest,
            "input_manifest_digest": self.input_manifest_digest,
            "attributes": self.attributes(),
            "_managed_trace_attributes": {
                "managed_graph.run_id": self.run_id,
                **self.attributes(),
            },
        }


_CURRENT: contextvars.ContextVar[ManagedRunContext | None] = contextvars.ContextVar(
    "_managed_run_ctx", default=None,
)


def get_current_managed_run() -> ManagedRunContext | None:
    return _CURRENT.get()


@contextmanager
def managed_run_scope(ctx: ManagedRunContext) -> Iterator[ManagedRunContext]:
    from factory.mcp_utils.interface import (
        get_envelope, reset_envelope, set_envelope,
    )

    current = dict(get_envelope() or {})
    envelope_token = set_envelope({
        **current, "run_id": ctx.run_id,
        "attributes": {
            **dict(current.get("attributes") or {}), **ctx.attributes(),
        },
    })
    context_token = _CURRENT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT.reset(context_token)
        reset_envelope(envelope_token)


def envelope_from_managed_context() -> dict[str, Any]:
    ctx = _CURRENT.get()
    if ctx is None:
        return {}
    return {"run_id": ctx.run_id, "attributes": ctx.attributes()}
