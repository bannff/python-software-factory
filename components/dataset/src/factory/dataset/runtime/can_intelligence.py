"""Public runtime facade for DBC discovery and immutable failure patterns."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters.dbc_catalog import LocalDbcCatalog
from .adapters.failure_pattern_store import LocalFailurePatternStore
from .dbc_models import DbcResolution, MessageFingerprint
from .dbc_resolver import (
    rank_dbc_candidates, resolve_catalog_dbc, verified_catalog_entries,
)


def query_dbc_catalog(storage_root: Path) -> dict[str, Any]:
    catalog = LocalDbcCatalog(storage_root)
    entries = []
    errors = []
    for entry in catalog.list_entries():
        try:
            catalog.verified_path(entry)
            status = "verified"
        except ValueError as error:
            status = "rejected"
            errors.append({"catalog_id": entry.catalog_id, "version": entry.version,
                           "error": str(error)})
        entries.append({**entry.model_dump(mode="json"), "artifact_status": status})
    return {"entries": entries, "count": len(entries), "errors": errors}


def resolve_dbc_candidate(
    storage_root: Path, *, catalog_id: str = "", version: str = "",
    vehicle_alias: str = "", vehicle_make: str = "", vehicle_model: str = "",
    vehicle_year: int | None = None,
    message_fingerprints: list[dict[str, Any]] | None = None,
    threshold: int = 10,
) -> dict[str, Any]:
    catalog = LocalDbcCatalog(storage_root)
    fingerprints = tuple(MessageFingerprint.model_validate(item)
                         for item in (message_fingerprints or []))
    if not catalog_id:
        resolution = rank_dbc_candidates(
            verified_catalog_entries(catalog), vehicle_alias=vehicle_alias,
            vehicle_make=vehicle_make, vehicle_model=vehicle_model,
            vehicle_year=vehicle_year, fingerprints=fingerprints, threshold=threshold,
        )
        if resolution.status != "resolved":
            return resolution.model_dump(mode="json")
    try:
        resolved = resolve_catalog_dbc(
            catalog, catalog_id=catalog_id, version=version,
            vehicle_alias=vehicle_alias, vehicle_make=vehicle_make,
            vehicle_model=vehicle_model, vehicle_year=vehicle_year,
            fingerprints=fingerprints, threshold=threshold,
        )
    except ValueError as error:
        return DbcResolution(status="not_found", threshold=threshold,
                             errors=(str(error),)).model_dump(mode="json")
    return {
        **resolved.resolution.model_dump(mode="json"),
        "definition": resolved.definition.model_dump(mode="json"),
        "artifact_path": str(resolved.path),
    }


def list_failure_patterns() -> list[dict[str, Any]]:
    return [ref.model_dump(mode="json") for ref in LocalFailurePatternStore().list_refs()]


def inspect_failure_pattern(pattern_id: str, version: str = "") -> dict[str, Any]:
    return LocalFailurePatternStore().inspect(pattern_id, version).model_dump(mode="json")


__all__ = [
    "inspect_failure_pattern", "list_failure_patterns", "query_dbc_catalog",
    "resolve_dbc_candidate",
]
