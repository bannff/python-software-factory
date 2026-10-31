"""Generic execution evidence operations composed from Workflow primitives."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .event_emitter import emit as emit_workflow_event


class ExecutionOperations:
    """Mixin requiring durable storage for opaque provider evidence."""

    def append_execution_event(
        self, *, workflow_run_id: str, attempt_id: str, revision: int,
        engine_id: str, registration_digest: str, request_digest: str,
        provider_request_digest: str, sequence: int, terminal: bool,
        raw_evidence: dict[str, Any], safe_metadata: dict[str, str],
    ) -> dict[str, Any]:
        if self._durable is None:
            raise ValueError("execution events require durable storage")
        result = self._durable.append_execution_event(
            workflow_run_id=workflow_run_id, attempt_id=attempt_id,
            revision=revision, engine_id=engine_id,
            registration_digest=registration_digest, request_digest=request_digest,
            provider_request_digest=provider_request_digest, sequence=sequence,
            terminal=terminal, raw_evidence=raw_evidence,
            safe_metadata=safe_metadata, now=datetime.now(UTC),
        )
        if result["appended"]:
            emit_workflow_event("workflow.attempt_stream_event", {
                "run_id": workflow_run_id, "attempt_id": attempt_id,
                "revision": revision, "engine_id": engine_id,
                "sequence": sequence, "terminal": terminal,
                "raw_digest": result["raw_digest"], **safe_metadata,
            })
        return result
