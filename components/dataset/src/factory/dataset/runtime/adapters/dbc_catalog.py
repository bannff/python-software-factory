"""Offline approved-manifest DBC catalog adapter with fail-closed verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..atomic_io import read_bytes_no_follow
from ..dbc_models import DbcCatalogEntry
from ..ports import DbcCatalogPort


class LocalDbcCatalog(DbcCatalogPort):
    """Read an administrator-authored manifest; never fetch source URLs."""

    def __init__(self, storage_root: Path, manifest_path: Path | None = None) -> None:
        self.root = storage_root.resolve() / "dbc_catalog"
        self.manifest_path = (manifest_path or self.root / "manifest.json").resolve()

    def list_entries(self) -> tuple[DbcCatalogEntry, ...]:
        if not self.manifest_path.is_file() or self.manifest_path.is_symlink():
            return ()
        self._inside(self.manifest_path)
        try:
            raw = json.loads(read_bytes_no_follow(self.manifest_path))
            entries = tuple(DbcCatalogEntry.model_validate(item) for item in raw["entries"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("approved DBC manifest is invalid") from error
        keys = [(entry.catalog_id, entry.version) for entry in entries]
        if len(keys) != len(set(keys)):
            raise ValueError("approved DBC manifest has duplicate identity/version")
        return tuple(sorted(entries, key=lambda item: (item.catalog_id, item.version)))

    def get_entry(self, catalog_id: str, version: str = "") -> DbcCatalogEntry | None:
        matches = [entry for entry in self.list_entries() if entry.catalog_id == catalog_id]
        if version:
            matches = [entry for entry in matches if entry.version == version]
        if len(matches) > 1:
            raise ValueError("DBC catalog identity requires an explicit version")
        return matches[0] if matches else None

    def verified_path(self, entry: DbcCatalogEntry) -> Path:
        parsed = urlparse(entry.provenance.artifact_uri)
        path = Path(unquote(parsed.path))
        self._inside(path.resolve(strict=False))
        if path.is_symlink() or not path.is_file():
            raise ValueError("approved DBC artifact is missing or symlinked")
        actual = hashlib.sha256(read_bytes_no_follow(path)).hexdigest()
        if actual != entry.provenance.sha256:
            raise ValueError("approved DBC artifact digest mismatch")
        return path.resolve()

    def _inside(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ValueError("DBC catalog path escapes approved root") from error


__all__ = ["LocalDbcCatalog"]
