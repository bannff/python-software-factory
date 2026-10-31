"""Subject-focused Metrics measurement semantics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .provenance_models import MetricMeasurement, MetricResult
from .provenance_support import (
    _durable_result,
    _lifecycle_result,
    _navigation,
    _observe_source,
    _parse_focus,
    _unavailable,
)

if TYPE_CHECKING:
    from .runtime import MetricsRuntime


def measure_focus(runtime: "MetricsRuntime", raw_focus: dict[str, Any]) -> MetricMeasurement:
    """Validate a focus and query only its exact durable subject labels."""
    if not isinstance(raw_focus, dict):
        raise ValueError("invalid_focus: focus must be an object")
    try:
        focus = _parse_focus(raw_focus)
    except ValidationError:
        try:
            navigation = _navigation(raw_focus)
        except ValidationError:
            navigation = None
        return MetricMeasurement(
            ok=False, focus=None, navigation=navigation,
            measurement=None, error_code="invalid_focus",
        )

    try:
        observation = _observe_source(runtime, focus)
    except Exception:
        return _unavailable(
            focus.navigation, "metrics source observation failed",
        )
    if observation.disposition != "available":
        return _lifecycle_result(focus.navigation, observation)

    try:
        health = runtime.store.health_check()
    except Exception:
        return _unavailable(
            focus.navigation, "metrics source health check failed",
        )
    if not health.get("ok", False):
        return _unavailable(
            focus.navigation, "metrics source health check reported unavailable",
        )

    now = datetime.now(timezone.utc)
    if focus.requested_availability == "live":
        result = MetricResult(
            measurement_state="live_not_persisted",
            source_class="metrics.live",
            last_updated_at=now,
            reason="live activity is not durable evidence",
            next_action="persist_measurement",
        )
    else:
        try:
            result = _durable_result(runtime, focus, observation)
        except Exception:
            return _unavailable(
                focus.navigation, "metrics source query failed",
            )
    return MetricMeasurement(
        ok=True, focus=focus, navigation=focus.navigation, measurement=result,
    )


__all__ = ["measure_focus"]
