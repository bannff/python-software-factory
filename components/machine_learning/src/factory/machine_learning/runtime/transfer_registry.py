"""Durable transfer-model registry and sealed publication recovery."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator

from .adapters.mlflow_lightgbm import validate_lightgbm_flavor
from .durable_files import (
    atomic_replace_json, canonical_json, file_lock, fsync_directory, fsync_tree,
    read_regular, write_exclusive,
)
from .passport_tree_manifest import bounded_tree_manifest
from .passport_tree_seal import (
    remove_staging_tree, require_read_only_tree, seal_read_only_tree,
)

_SIDECAR = "transfer-publication.json"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


class TransferRegistry:
    """Serialize registry commits and recover exact sealed LightGBM finals."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("transfer registry root must be a regular directory")
        self.path = self.root / "model_registry.json"
        self.locks = self.root / ".locks"
        self.locks.mkdir(mode=0o700, exist_ok=True)
        if self.locks.is_symlink() or not self.locks.is_dir():
            raise ValueError("transfer registry lock root is invalid")

    def load(self) -> dict[str, Any]:
        if not self.path.exists() and not self.path.is_symlink():
            return {"models": {}, "iterations": []}
        value = json.loads(read_regular(self.path))
        if (
            not isinstance(value, dict) or set(value) != {"models", "iterations"}
            or not isinstance(value["models"], dict)
            or not isinstance(value["iterations"], list)
        ):
            raise ValueError("transfer registry shape is invalid")
        return value

    @contextmanager
    def model_lock(self, model_id: str) -> Iterator[None]:
        if _ID.fullmatch(model_id) is None:
            raise ValueError("transfer model id is invalid")
        with file_lock(self.locks / f"{model_id}.lock"):
            yield

    def reconcile_all(self) -> dict[str, Any]:
        registry = self.load()
        candidates = sorted(
            item for item in self.root.iterdir()
            if _ID.fullmatch(item.name) is not None
            and item.name.startswith("lightgbm_iter")
            and item.name not in registry["models"]
        )
        for final in candidates:
            with self.model_lock(final.name):
                self.reconcile(final.name)
        return self.load()

    def reconcile(
        self, model_id: str, expected_intent: str | None = None,
    ) -> dict[str, Any] | None:
        existing = self.load()["models"].get(model_id)
        final = self.root / model_id
        if existing is not None:
            path = Path(existing.get("path", ""))
            if path.is_dir() and not path.is_symlink():
                observed = self._verify_final(
                    final, model_id, expected_intent=expected_intent,
                )
                if observed != existing:
                    raise ValueError("transfer registry disagrees with sealed final")
            return existing
        if not (final.exists() or final.is_symlink()):
            return None
        try:
            entry = self._verify_final(
                final, model_id, expected_intent=expected_intent,
            )
        except Exception:
            remove_staging_tree(final)
            fsync_directory(self.root)
            return None
        self.commit_model(model_id, entry)
        return entry

    def publish(
        self, model_id: str, staging: Path, final: Path,
        entry: dict[str, Any], intent: str, rounds: int, iterations: int,
    ) -> None:
        model_path = staging / "mlflow-model"
        validate_lightgbm_flavor(model_path)
        body = {
            "schema_version": "1.0", "model_id": model_id, "entry": entry,
            "intent_sha256": intent, "rounds": rounds, "iterations": iterations,
            "model_tree_sha256": _tree_digest(model_path, self.root),
        }
        sidecar = {
            **body, "sidecar_sha256": hashlib.sha256(canonical_json(body)).hexdigest(),
        }
        write_exclusive(staging / _SIDECAR, canonical_json(sidecar))
        seal_read_only_tree(staging)
        require_read_only_tree(staging)
        fsync_tree(staging)
        os.rename(staging, final)
        fsync_directory(self.root)
        self._verify_final(final, model_id, expected_intent=intent)

    def commit_model(self, model_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        with file_lock(self.locks / "registry.lock"):
            registry = self.load()
            current = registry["models"].get(model_id)
            if current is not None and current != entry:
                raise ValueError("transfer registry model id already differs")
            updated = {
                "models": {**registry["models"], model_id: entry},
                "iterations": list(registry["iterations"]),
            }
            atomic_replace_json(self.path, updated)
            if self.load() != updated:
                raise ValueError("durable transfer registry verification failed")
            return updated

    def append_iteration(self, value: dict[str, Any]) -> dict[str, Any]:
        with file_lock(self.locks / "registry.lock"):
            registry = self.load()
            updated = {
                "models": dict(registry["models"]),
                "iterations": [*registry["iterations"], value],
            }
            atomic_replace_json(self.path, updated)
            if self.load() != updated:
                raise ValueError("durable transfer registry verification failed")
            return updated

    def _verify_final(
        self, final: Path, model_id: str, expected_intent: str | None = None,
    ) -> dict[str, Any]:
        require_read_only_tree(final)
        model_path = final / "mlflow-model"
        validate_lightgbm_flavor(model_path)
        sidecar = json.loads(read_regular(final / _SIDECAR))
        expected_keys = {
            "schema_version", "model_id", "entry", "intent_sha256", "rounds",
            "iterations", "model_tree_sha256", "sidecar_sha256",
        }
        if not isinstance(sidecar, dict) or set(sidecar) != expected_keys:
            raise ValueError("transfer publication sidecar shape is invalid")
        digest = sidecar.pop("sidecar_sha256")
        if digest != hashlib.sha256(canonical_json(sidecar)).hexdigest():
            raise ValueError("transfer publication sidecar digest mismatch")
        if (
            sidecar.get("schema_version") != "1.0"
            or sidecar.get("model_id") != model_id
            or sidecar.get("model_tree_sha256") != _tree_digest(model_path, self.root)
            or expected_intent is not None
            and sidecar.get("intent_sha256") != expected_intent
        ):
            raise ValueError("transfer publication sidecar binding mismatch")
        entry = sidecar.get("entry")
        if not isinstance(entry, dict) or entry.get("path") != str(model_path):
            raise ValueError("transfer publication registry entry is invalid")
        return entry


def _tree_digest(path: Path, root: Path) -> str:
    manifest = bounded_tree_manifest(path, root, "transfer LightGBM artifact")
    return hashlib.sha256(canonical_json(manifest)).hexdigest()


__all__ = ["TransferRegistry"]
