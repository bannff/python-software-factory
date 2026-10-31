"""Post-injection rate verification (Epic 3 v2 observability).

Extracted from :mod:`failure_injection` so the orchestrator stays
under the 200-LOC factory ceiling while still emitting a warning
when the realized failure rate diverges from the configured target
by more than the stochastic-sampling tolerance band.
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)

# Stochastic sampling on small streams can land up to ~5% off the
# target rate; anything wider indicates a dispatch bug worth logging.
RATE_TOLERANCE: float = 0.05


def verify_failure_rate(
    records: list[dict[str, Any]],
    expected_rate: float,
    *,
    tolerance: float = RATE_TOLERANCE,
) -> None:
    """Log a warning if the realized failure rate diverges from target.

    Empty record lists are a no-op — callers short-circuit on empty
    streams before we get here, but guard anyway for safety.
    """
    if not records:
        return
    actual = sum(r.get("is_failure") for r in records) / len(records)
    if abs(actual - expected_rate) > tolerance:
        _logger.warning(
            "Failure rate mismatch: expected %.2f, got %.2f",
            expected_rate, actual,
        )
