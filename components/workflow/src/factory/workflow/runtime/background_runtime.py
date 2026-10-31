"""Completion-aware Workflow background lifecycle delegates."""
from __future__ import annotations

from typing import Any

from .background_completion import record_background_completion
from .envelope import Envelope


class BackgroundCompletionRuntime:
    """Decorate existing Workflow operations with durable origin delivery."""

    _ops: Any

    def cancel_run(
        self, *, run_id: str, reason: str | None, envelope: Envelope,
    ) -> dict[str, Any]:
        result = self._ops.cancel_run(run_id=run_id, reason=reason, envelope=envelope)
        record_background_completion(self, run_id, envelope)
        return result

    def resume_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        result = self._ops.resume_run(run_id=run_id, envelope=envelope)
        record_background_completion(self, run_id, envelope)
        return result


__all__ = ["BackgroundCompletionRuntime"]
