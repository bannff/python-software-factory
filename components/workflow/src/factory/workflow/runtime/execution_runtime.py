"""Workflow provider-neutral execution delegates."""
from __future__ import annotations

from typing import Any

from .execution_enrollment import enroll


class ExecutionRuntime:
    """Expose only generic execution enrollment and evidence operations."""

    def enroll_execution(
        self, *, engine_id: str, request: dict[str, Any],
        provider_request_digest: str, run_key: str, envelope: Any,
        execute: bool = True, launch_metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return enroll(
            self._ops, spec=self.execution_engines.resolve(engine_id),
            request=request, provider_request_digest=provider_request_digest,
            run_key=run_key, envelope=envelope, execute=execute,
            launch_metadata=launch_metadata or {},
        )

    def append_execution_event(self, **kwargs: Any) -> dict[str, Any]:
        return self._ops.append_execution_event(**kwargs)

    def get_execution_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        if self.durable_storage is None:
            raise ValueError("execution events require durable storage")
        return self.durable_storage.get_execution_events(**kwargs)
