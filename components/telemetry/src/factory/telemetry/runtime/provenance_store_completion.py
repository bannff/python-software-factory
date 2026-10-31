"""Durable per-mapping completion records for Telemetry replay."""
from __future__ import annotations

from typing import Any


def initialize_materialization_completions(connection: Any) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS materialization_completions "
        "(completion_key TEXT PRIMARY KEY)"
    )


class MaterializationCompletionStoreMixin:
    """SQLite mixin used by the provenance store without a second backend."""

    @staticmethod
    def _completion_key(
        telemetry_ref: str, mapping_id: str, mapping_version: str, fanout_index: int,
    ) -> str:
        return "\0".join((telemetry_ref, mapping_id, mapping_version, str(fanout_index)))

    def has_materialization_completion(
        self, telemetry_ref: str, mapping_id: str, mapping_version: str,
        fanout_index: int,
    ) -> bool:
        key = self._completion_key(
            telemetry_ref, mapping_id, mapping_version, fanout_index,
        )
        with self._connection() as connection:
            return connection.execute(
                "SELECT 1 FROM materialization_completions WHERE completion_key=?",
                (key,),
            ).fetchone() is not None

    def mark_materialization_completion(
        self, telemetry_ref: str, mapping_id: str, mapping_version: str,
        fanout_index: int,
    ) -> None:
        key = self._completion_key(
            telemetry_ref, mapping_id, mapping_version, fanout_index,
        )
        with self._connection(transaction=True) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO materialization_completions VALUES (?)",
                (key,),
            )
