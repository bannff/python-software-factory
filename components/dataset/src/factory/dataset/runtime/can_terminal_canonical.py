"""Canonical source inventory and request hashing for CAN attempts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .atomic_io import read_bytes_no_follow
from .dbc_semantics import DbcVersionDefinition
from .can_terminal_models import CanTerminalRequest
from .can_terminal_paths import checked_source_path

_STAGE_VERSIONS = {
    "can_ingest": "factory-can-ingest-1",
    "can_profile": "factory-can-profile-1",
    "can_signal_schema": "factory-can-signal-schema-1",
    "can_prior_policy": "factory-can-prior-policy-1",
    "can_synthesize": "factory-can-synthesize-1",
    "can_window_v2": "factory-can-window-2",
    "can_augment": "factory-can-augment-1",
    "context_ingest": "factory-context-ingest-1",
    "context_augment": "factory-context-augment-1",
    "context_correlate": "factory-context-correlate-1",
}


@dataclass(frozen=True)
class CanonicalCanRequest:
    request_sha256: str
    payload: dict[str, Any]
    mf4_paths: tuple[Path, ...]
    dbc_path: Path
    dbc_definition: DbcVersionDefinition
    context_paths: tuple[Path, ...]


def canonicalize_request(
    request: CanTerminalRequest, dbc_definition: DbcVersionDefinition | None = None,
) -> CanonicalCanRequest:
    """Bind a request to exact local source bytes before any effects."""
    mf4_paths = canonical_mf4_paths(request.mf4_dir)
    if request.dbc_path is None:
        raise ValueError("canonical CAN request requires a resolved DBC path")
    dbc_path = _require_file(canonical_source_path(request.dbc_path), "DBC")
    if dbc_definition is None:
        from .dbc_resolver import resolve_explicit_dbc
        dbc_definition = resolve_explicit_dbc(dbc_path).definition
    contexts = tuple(
        _require_file(canonical_source_path(item), "context source")
        for item in request.context_sources
    ) if request.use_context else ()
    payload = {
        "schema_version": request.schema_version,
        "terminal_version": "dataset-can-terminal-1",
        "mf4": [_inventory(path) for path in mf4_paths],
        "dbc": _inventory(dbc_path),
        "dbc_definition": {
            "definition_id": dbc_definition.definition_id,
            "catalog_id": dbc_definition.catalog_id,
            "version": dbc_definition.version,
            "digest": dbc_definition.digest,
            "provenance": dbc_definition.provenance.model_dump(mode="json"),
        },
        "dbc_selection": {
            "catalog_id": request.dbc_catalog_id,
            "catalog_version": request.dbc_catalog_version,
            "vehicle_alias": request.vehicle_alias,
            "vehicle_make": request.vehicle_make,
            "vehicle_model": request.vehicle_model,
            "vehicle_year": request.vehicle_year,
            "message_fingerprints": [item.model_dump(mode="json") for item in request.message_fingerprints],
        },
        "failure_pattern_refs": [item.model_dump(mode="json") for item in request.failure_pattern_refs],
        "vehicle_id": request.vehicle_id,
        "max_samples": request.max_samples,
        "config_overrides": request.config_overrides,
        "use_context": request.use_context,
        "context_sources": [_inventory(path) for path in contexts],
        "emit_timespans": request.emit_timespans,
        "stage_adapter_versions": _STAGE_VERSIONS,
    }
    content = canonical_json(payload)
    return CanonicalCanRequest(
        request_sha256=hashlib.sha256(content).hexdigest(), payload=payload,
        mf4_paths=mf4_paths, dbc_path=dbc_path, dbc_definition=dbc_definition,
        context_paths=contexts,
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _inventory(path: Path) -> dict[str, str]:
    file_path = _require_file(path, "source")
    return {
        "uri": file_path.resolve().as_uri(),
        "sha256": hashlib.sha256(read_bytes_no_follow(file_path)).hexdigest(),
    }


def canonical_mf4_paths(value: str) -> tuple[Path, ...]:
    """Inventory candidate MF4 files before pathless DBC resolution."""
    root = canonical_source_path(value)
    paths = tuple(sorted({*root.rglob("*.MF4"), *root.rglob("*.mf4")}))
    if not paths:
        raise ValueError(f"no MF4 files under {value}")
    return paths


def canonical_source_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"CAN terminal sources must be local files: {value}")
    raw = unquote(parsed.path) if parsed.scheme == "file" else value
    if ".." in Path(raw).parts:
        raise ValueError("CAN terminal source traversal is forbidden")
    return checked_source_path(Path(raw))


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    return path


__all__ = [
    "CanonicalCanRequest", "canonical_json", "canonical_mf4_paths",
    "canonical_source_path", "canonicalize_request",
]
