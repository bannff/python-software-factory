"""Create-or-match coordinator for the Dataset CAN terminal."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters.dbc_catalog import LocalDbcCatalog
from .adapters.local_can_attempts import LocalCanAttemptStore
from .can_terminal_canonical import (
    canonical_mf4_paths, canonical_source_path, canonicalize_request,
)
from .dbc_resolver import resolve_catalog_dbc, resolve_explicit_dbc
from .mf4_probe import probe_mf4_fingerprints
from .can_terminal_models import CanTerminalRequest
from .can_terminal_paths import secure_storage_root
from .can_terminal_pipeline import CanTerminalPipeline
from .can_terminal_sources import snapshot_sources
from .can_terminal_verify import verify_terminal
from .ports import DatasetTerminalStore


class CanTerminalService:
    """Own attempt identity while delegating CAN effects to Dataset recipes."""

    def __init__(
        self, root: Path, pipeline: Any | None = None,
        store: DatasetTerminalStore | None = None, verifier: Any = verify_terminal,
    ) -> None:
        self.root = secure_storage_root(root)
        self.store = store or LocalCanAttemptStore(self.root)
        self.pipeline = pipeline or CanTerminalPipeline(self.root)
        self.verifier = verifier

    def materialize(self, request: CanTerminalRequest) -> dict[str, Any]:
        if request.dbc_path is not None:
            resolved = resolve_explicit_dbc(canonical_source_path(request.dbc_path))
            effective = request.model_copy(update={"dbc_path": str(resolved.path)})
        else:
            observed = probe_mf4_fingerprints(canonical_mf4_paths(request.mf4_dir))
            expected = set(request.message_fingerprints)
            if expected and not expected.issubset(set(observed)):
                raise ValueError("caller message_fingerprints are not observed in MF4 sources")
            resolved = resolve_catalog_dbc(
                LocalDbcCatalog(self.root), catalog_id=request.dbc_catalog_id,
                version=request.dbc_catalog_version,
                vehicle_alias=request.vehicle_alias or request.vehicle_id,
                vehicle_make=request.vehicle_make, vehicle_model=request.vehicle_model,
                vehicle_year=request.vehicle_year, fingerprints=observed,
            )
            effective = request.model_copy(update={
                "dbc_path": str(resolved.path), "message_fingerprints": observed,
            })
        canonical = canonicalize_request(effective, resolved.definition)
        with self.store.lock(request.attempt_id):
            resolution, record = self.store.claim(
                request.attempt_id, canonical.request_sha256,
            )
            if resolution == "conflict":
                return {
                    "schema_version": "1.0", "status": "conflict",
                    "attempt_id": request.attempt_id,
                    "request_sha256": canonical.request_sha256,
                    "existing_request_sha256": record.request_sha256,
                    "error": "attempt_id is already bound to a different request",
                }
            if record.state in {"succeeded", "failed"}:
                terminal = self.store.load_terminal(record)
                self.verifier(
                    self.root, terminal, attempt_id=request.attempt_id,
                    request_sha256=canonical.request_sha256,
                    use_context=request.use_context,
                )
                return terminal
            canonical = snapshot_sources(canonical, self.root)
            record = self.store.transition(record, "materializing")
            try:
                terminal = self.pipeline.run(effective, canonical)
                self.verifier(
                    self.root, terminal, attempt_id=request.attempt_id,
                    request_sha256=canonical.request_sha256,
                    use_context=request.use_context,
                )
            except Exception as exc:
                failed = {
                    "schema_version": "1.0", "status": "failed",
                    "attempt_id": request.attempt_id,
                    "request_sha256": canonical.request_sha256,
                    "error": str(exc),
                }
                self.store.publish(record, failed)
                return failed
            record = self.store.transition(record, "publishing")
            self.store.publish(record, terminal)
            return terminal


__all__ = ["CanTerminalService"]
