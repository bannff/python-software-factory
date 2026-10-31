"""DTOs for the trajectory landing-zone resolution tool."""
from __future__ import annotations

from typing import Any

from pydantic import StrictInt, StrictStr

from ...runtime.trajectory_landing import TrajectoryRow
from .base import InputDTO, OutputDTO


class TrajectoryZoneInput(InputDTO):
    dataset_uri: StrictStr
    storage_root: StrictStr | None = None


class ResolvedTrajectoryZoneOutput(OutputDTO):
    """Digest-verified rowset: every row respects the frozen v1 contract."""

    schema_version: StrictInt
    digest: StrictStr
    row_count: StrictInt
    rows: list[TrajectoryRow]

    @property
    def root(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


__all__ = ["ResolvedTrajectoryZoneOutput", "TrajectoryZoneInput"]
