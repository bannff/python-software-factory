"""get_capture() must exist and satisfy the SpanCapture port (issue #300)."""
from factory.telemetry.interface import get_capture
from factory.telemetry.runtime.ports import SpanCapture


def test_get_capture_returns_singleton_satisfying_port():
    capture = get_capture()
    assert isinstance(capture, SpanCapture)
    assert get_capture() is capture


def test_setup_is_idempotent_and_marks_ready():
    capture = get_capture()
    assert capture.setup() is capture
    assert capture.setup() is capture
    assert capture.ready is True


def test_captures_emitted_spans_and_clear_resets():
    from opentelemetry import trace

    capture = get_capture().setup()
    capture.clear()
    with trace.get_tracer("t").start_as_current_span("probe"):
        pass
    names = [s.name for s in capture.get_finished_spans()]
    assert "probe" in names
    capture.clear()
    assert capture.get_finished_spans() == []
