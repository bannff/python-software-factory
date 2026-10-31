"""Span-processor adapter enforcing OpenTelemetry callback suppression."""
from __future__ import annotations

from threading import Lock

from opentelemetry.context import Context
from opentelemetry.instrumentation.utils import is_instrumentation_enabled
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor


class SuppressionAwareSpanProcessor(SpanProcessor):
    """Drop explicit spans started while instrumentation is suppressed.

    OpenTelemetry instrumentors honor ``suppress_instrumentation()``, but
    libraries can create spans directly without checking it. FastMCP 3.2.4
    does this in ``fastmcp/server/telemetry.py::server_span``. Tracking at
    ``on_start`` also covers spans that end after the suppression context exits.

    Upstream FastMCP telemetry gap:
    https://github.com/PrefectHQ/fastmcp/issues/3993
    """

    def __init__(self, processor: SpanProcessor) -> None:
        self._processor = processor
        self._suppressed: set[int] = set()
        self._lock = Lock()

    @staticmethod
    def _span_id(span: Span | ReadableSpan) -> int:
        return span.get_span_context().span_id

    def on_start(
        self, span: Span, parent_context: Context | None = None,
    ) -> None:
        if not is_instrumentation_enabled():
            with self._lock:
                self._suppressed.add(self._span_id(span))
            return
        self._processor.on_start(span, parent_context=parent_context)

    def _on_ending(self, span: Span) -> None:
        with self._lock:
            suppressed = self._span_id(span) in self._suppressed
        if not suppressed:
            self._processor._on_ending(span)  # noqa: SLF001 - SDK protocol

    def on_end(self, span: ReadableSpan) -> None:
        with self._lock:
            suppressed = self._span_id(span) in self._suppressed
            self._suppressed.discard(self._span_id(span))
        if not suppressed:
            self._processor.on_end(span)

    def shutdown(self) -> None:
        self._processor.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._processor.force_flush(timeout_millis)
