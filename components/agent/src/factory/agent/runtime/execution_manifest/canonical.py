"""Canonical JSON and manifest sealing."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import DigestValue
from .models import ExecutionManifestV1


def canonical_bytes(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: bytes) -> DigestValue:
    return DigestValue(value=hashlib.sha256(value).hexdigest())


def manifest_bytes(manifest: ExecutionManifestV1) -> bytes:
    payload = manifest.model_dump(mode="json", exclude={"digest"})
    return canonical_bytes(payload)


def seal_manifest(manifest: ExecutionManifestV1) -> ExecutionManifestV1:
    digest = sha256(manifest_bytes(manifest))
    return manifest.model_copy(update={"digest": digest})


def verify_manifest(manifest: ExecutionManifestV1) -> None:
    if manifest.digest is None or manifest.digest != sha256(manifest_bytes(manifest)):
        raise ValueError("execution manifest digest mismatch")


__all__ = ["canonical_bytes", "manifest_bytes", "seal_manifest", "sha256", "verify_manifest"]
