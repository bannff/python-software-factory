"""Stage and validate a single ``companion-x-v1`` bundle file.

Unlike ``source_snapshot.py`` (walks an untrusted directory tree), a bundle
is exactly ONE owner-supplied file — the safety surface is smaller: reject
symlinks, cap size, require the file to be a regular file the caller owns,
then parse and validate ``bundle_version``/``adapter``/``content_digest``
before any record inside it is trusted. A mismatch fails the whole bundle
(no partial trust of a corrupt/tampered file), mirroring
``PreviewUnavailable``'s all-or-nothing posture on the kirocrew-v1 side.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

MAX_BUNDLE_BYTES = 64 * 1024 * 1024
_BUNDLE_VERSION = 1
_BUNDLE_ADAPTER = "companion-x-v1"


class BundleStageError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_matches(claimed: str, computed: dict[str, Any]) -> bool:
    material = json.dumps(computed, sort_keys=True).encode("utf-8")
    return claimed == f"sha256:{_sha256_hex(material)}"


def stage_bundle(path: Path) -> dict[str, Any]:
    """Read, size/symlink-check, and content-validate a bundle file.

    Returns the parsed bundle dict on success. Raises ``BundleStageError``
    with a fixed, content-free code on any failure — never echoes bundle
    content back in an exception message.
    """
    if not path.is_absolute():
        raise BundleStageError("bundle_path_must_be_absolute")
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        code = "bundle_symlink_rejected" if getattr(exc, "errno", 0) == getattr(os, "ELOOP", 62) else "bundle_unreadable"
        raise BundleStageError(code) from exc
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode):
            raise BundleStageError("bundle_not_regular_file")
        if meta.st_nlink != 1:
            raise BundleStageError("bundle_hardlink_rejected")
        if meta.st_size > MAX_BUNDLE_BYTES:
            raise BundleStageError("bundle_size_exceeded")
        raw = os.read(fd, meta.st_size + 1)
        if len(raw) != meta.st_size:
            raise BundleStageError("bundle_mutated_during_read")
    finally:
        os.close(fd)
    try:
        bundle = json.loads(raw)
    except ValueError as exc:
        raise BundleStageError("bundle_invalid_json") from exc
    if not isinstance(bundle, dict):
        raise BundleStageError("bundle_invalid_shape")
    if bundle.get("bundle_version") != _BUNDLE_VERSION:
        raise BundleStageError("bundle_version_unsupported")
    if bundle.get("adapter") != _BUNDLE_ADAPTER:
        raise BundleStageError("bundle_adapter_mismatch")
    kinds = bundle.get("kinds")
    if not isinstance(kinds, dict):
        raise BundleStageError("bundle_invalid_shape")
    claimed_content_digest = bundle.get("content_digest")
    if not isinstance(claimed_content_digest, str) or not _digest_matches(claimed_content_digest, kinds):
        raise BundleStageError("bundle_content_digest_mismatch")
    for kind, block in kinds.items():
        if not isinstance(block, dict) or "records" not in block or "digest" not in block:
            raise BundleStageError("bundle_invalid_shape")
        records = block["records"]
        if not isinstance(records, list):
            raise BundleStageError("bundle_invalid_shape")
        payload = json.dumps(records, sort_keys=True).encode("utf-8")
        if block["digest"] != f"sha256:{_sha256_hex(payload)}":
            raise BundleStageError(f"bundle_kind_digest_mismatch:{kind}")
    return bundle


__all__ = ["MAX_BUNDLE_BYTES", "BundleStageError", "stage_bundle"]
