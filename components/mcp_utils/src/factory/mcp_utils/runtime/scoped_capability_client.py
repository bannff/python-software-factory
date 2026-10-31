"""Dependency-free scoped capability client for consumer conformance tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Awaitable, Callable, Mapping

from .scoped_capabilities import (
    CapabilityDescriptor,
    CapabilityInvocation,
    CapabilityResult,
    CapabilityScope,
)

CapabilityHandler = Callable[[CapabilityInvocation], Awaitable[CapabilityResult]]


class CapabilityAccessError(RuntimeError):
    """Raised when a client is closed or a capability is outside its scope."""


class InMemoryScopedCapabilityClient:
    """A deterministic, scope-enforcing test double; never a transport."""

    def __init__(
        self,
        scope: CapabilityScope,
        descriptors: tuple[CapabilityDescriptor, ...],
        handlers: Mapping[str, CapabilityHandler],
    ) -> None:
        self._scope = CapabilityScope.create(
            scope.policy_id, scope.tool_names,
            delegation_depth=scope.delegation_depth, digest=scope.digest,
        )
        self._descriptors = {
            item.name: self._copy_descriptor(item)
            for item in descriptors
            if item.name in scope.tool_names
        }
        self._handlers = dict(handlers)
        self.calls: list[CapabilityInvocation] = []
        self._closed = False

    @property
    def scope(self) -> CapabilityScope:
        """Return the trusted immutable policy bound at construction."""
        return self._scope

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """List allowlisted descriptors in deterministic name order."""
        self._require_open()
        return tuple(self._copy_descriptor(self._descriptors[name]) for name in sorted(self._descriptors))

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
        """Invoke an allowlisted handler without transforming its request."""
        self._require_open()
        if request.name not in self._scope.tool_names:
            raise CapabilityAccessError(f"capability outside scope: {request.name}")
        handler = self._handlers.get(request.name)
        if handler is None:
            raise CapabilityAccessError(f"capability unavailable: {request.name}")
        self.calls.append(request)
        return await handler(request)

    async def close(self) -> None:
        """Close idempotently and prevent all later operations."""
        self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise CapabilityAccessError("capability client is closed")

    @staticmethod
    def _copy_descriptor(item: CapabilityDescriptor) -> CapabilityDescriptor:
        return replace(item, input_schema=deepcopy(item.input_schema))


__all__ = ["CapabilityAccessError", "CapabilityHandler", "InMemoryScopedCapabilityClient"]
