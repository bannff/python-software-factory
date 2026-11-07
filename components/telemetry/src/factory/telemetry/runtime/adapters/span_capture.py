"""In-memory span capture backed by strands-evals, implementing the SpanCapture port."""
from __future__ import annotations

from typing import Any


class StrandsSpanCapture:
    """Lazily installs one in-memory exporter; strands-evals is imported only on setup."""

    def __init__(self) -> None:
        self._telemetry: Any = None

    @property
    def ready(self) -> bool:
        return self._telemetry is not None

    def setup(self) -> "StrandsSpanCapture":
        # One global tracer provider per process: repeat setup must not stack exporters.
        if self._telemetry is None:
            from strands_evals.telemetry import StrandsEvalsTelemetry
            self._telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
        return self

    def _exporter(self) -> Any:
        if self._telemetry is None:
            raise RuntimeError("span capture used before setup()")
        return self._telemetry.in_memory_exporter

    def clear(self) -> None:
        self._exporter().clear()

    def get_finished_spans(self) -> list[Any]:
        return list(self._exporter().get_finished_spans())

    def spans_to_session(self, spans: list[Any], session_id: str = "unknown") -> Any:
        from strands_evals.mappers import StrandsInMemorySessionMapper
        return StrandsInMemorySessionMapper().map_to_session(spans, session_id=session_id)


_CAPTURE = StrandsSpanCapture()


def get_capture() -> StrandsSpanCapture:
    return _CAPTURE
