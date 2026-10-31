"""Protocol interfaces for the metrics brick.

Ports define what capabilities the metrics system needs, not how they're implemented.
Adapters plug in specific backends (in-memory, DynamoDB, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from factory.metrics.core import DataPoint


SourceDisposition = Literal["available", "unavailable", "deleted", "inaccessible"]


@dataclass(frozen=True)
class SourceObservation:
    """Explicit backend observation used to interpret a focused measurement."""

    disposition: SourceDisposition
    arriving: bool = False
    watermark: float | None = None
    completeness: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.completeness is not None and not 0.0 <= self.completeness <= 1.0:
            raise ValueError("source completeness must be between 0 and 1")


@runtime_checkable
class MetricsStore(Protocol):
    """Port: Where metric data points are stored and queried."""

    def record(
        self,
        metric_id: str,
        value: float,
        labels: dict[str, str] | None = None,
        timestamp: float | None = None,
    ) -> None: ...

    def query(
        self,
        metric_id: str,
        start: float | None = None,
        end: float | None = None,
        labels: dict[str, str] | None = None,
    ) -> list[DataPoint]: ...

    def observe_source(
        self,
        labels: dict[str, str] | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> SourceObservation: ...

    def latest(
        self,
        metric_id: str,
        labels: dict[str, str] | None = None,
    ) -> DataPoint | None: ...

    def count(self, metric_id: str | None = None) -> int: ...

    def health_check(self) -> dict[str, Any]: ...


@runtime_checkable
class MetricsComputer(Protocol):
    """Port: How aggregations and computations are performed."""

    def aggregate(
        self, points: list[DataPoint], method: str = "mean",
    ) -> float: ...

    def trend(self, points: list[DataPoint]) -> dict[str, Any]: ...

    def detect_drift(
        self,
        baseline: list[DataPoint],
        current: list[DataPoint],
        threshold: float = 0.1,
    ) -> dict[str, Any]: ...
