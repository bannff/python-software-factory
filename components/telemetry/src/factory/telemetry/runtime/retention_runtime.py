"""Telemetry retention runtime composition."""
from __future__ import annotations

import os
from pathlib import Path

from .retention import RetentionResult, run_retention
from .policy_config import compose_retention_days


class RetentionRuntime:
    def run_retention(
        self, raw_days: int | None = None, rollup_days: int | None = None,
        compact_source: bool = True,
    ) -> RetentionResult:
        composed_raw, composed_rollup = compose_retention_days()
        source = Path(os.getenv("STORAGE_SQLITE_PATH", "./.storage/docs.db"))
        target = Path(os.getenv("TELEMETRY_SQLITE_PATH", "./.storage/telemetry.db"))
        return run_retention(
            source, target,
            raw_days=raw_days if raw_days is not None else composed_raw,
            rollup_days=rollup_days if rollup_days is not None else composed_rollup,
            compact_source=compact_source,
        )


__all__ = ["RetentionRuntime"]
