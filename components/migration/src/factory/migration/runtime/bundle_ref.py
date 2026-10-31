"""Resolve a caller-supplied bundle filename to a safe, contained path for
reading. Mirrors ``portability.runtime.bundle_writer``'s containment logic
on the read side — both trust the SAME configured root
(``PORTABILITY_EXPORT_ROOT``), since a bundle written there by export is
exactly what an owner re-imports later."""
from __future__ import annotations

import os
from pathlib import Path


class BundleRefError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def resolve_bundle_ref(bundle_ref: str) -> Path:
    if not bundle_ref or "/" in bundle_ref or "\\" in bundle_ref or bundle_ref in (".", ".."):
        raise BundleRefError("migration_bundle_ref_invalid")
    raw_root = os.getenv("PORTABILITY_EXPORT_ROOT", "").strip()
    if not raw_root:
        raise BundleRefError("migration_bundle_root_not_configured")
    root = Path(raw_root).expanduser()
    if not root.is_absolute():
        raise BundleRefError("migration_bundle_root_must_be_absolute")
    if not root.is_dir():
        raise BundleRefError("migration_bundle_root_unavailable")
    root = root.resolve()
    candidate = root / bundle_ref
    if candidate.exists() and candidate.is_symlink():
        raise BundleRefError("migration_bundle_symlink_rejected")
    if candidate.parent.resolve() != root:
        raise BundleRefError("migration_bundle_ref_escapes_root")
    if not candidate.exists():
        raise BundleRefError("migration_bundle_not_found")
    return candidate


__all__ = ["BundleRefError", "resolve_bundle_ref"]
