"""Canonical compact JSON codec for Dataset-owned CAN artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import unquote, urlparse

from pydantic import BaseModel

from .can_artifact_models import CanArtifactRef, CanPriorDataPolicy, CanSignalSchema
from .atomic_io import read_bytes_no_follow

Artifact = TypeVar("Artifact", CanPriorDataPolicy, CanSignalSchema)


def create_prior_policy(**values: Any) -> CanPriorDataPolicy:
    return _create(CanPriorDataPolicy, values)


def create_signal_schema(**values: Any) -> CanSignalSchema:
    return _create(CanSignalSchema, values)


def canonical_body_bytes(artifact: BaseModel) -> bytes:
    """Canonical bytes used for the body digest, excluding ``digest``."""
    return _canonical(artifact.model_dump(mode="json", exclude={"digest"}))


def canonical_artifact_bytes(artifact: BaseModel) -> bytes:
    """Canonical full artifact bytes, with no JSONL newline or whitespace."""
    return _canonical(artifact.model_dump(mode="json"))


def artifact_digest(artifact: BaseModel) -> str:
    return hashlib.sha256(canonical_body_bytes(artifact)).hexdigest()


def artifact_ref(uri: str, version: str, digest: str) -> CanArtifactRef:
    return CanArtifactRef(uri=uri, version=version, digest=digest)


def load_prior_policy(ref: CanArtifactRef) -> CanPriorDataPolicy:
    return _load(ref, CanPriorDataPolicy)


def load_signal_schema(ref: CanArtifactRef) -> CanSignalSchema:
    return _load(ref, CanSignalSchema)


def ref_from_prior_policy_uri(uri: str) -> CanArtifactRef:
    return _ref_from_uri(uri, CanPriorDataPolicy)


def ref_from_signal_schema_uri(uri: str) -> CanArtifactRef:
    return _ref_from_uri(uri, CanSignalSchema)


def _create(model: type[Artifact], values: dict[str, Any]) -> Artifact:
    body = dict(values)
    body["digest"] = "0" * 64
    provisional = model.model_validate(body)
    body = provisional.model_dump(mode="json")
    body["digest"] = artifact_digest(provisional)
    return model.model_validate(body)


def _load(ref: CanArtifactRef, model: type[Artifact]) -> Artifact:
    raw = read_bytes_no_follow(_path(ref.uri))
    try:
        artifact = model.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"invalid {model.__name__} artifact: {exc}") from exc
    if raw != canonical_artifact_bytes(artifact):
        raise ValueError("CAN artifact bytes are not canonical")
    if artifact.version != ref.version:
        raise ValueError("CAN artifact version mismatch")
    if artifact.digest != ref.digest:
        raise ValueError("CAN artifact reference digest mismatch")
    if artifact.digest != artifact_digest(artifact):
        raise ValueError("CAN artifact body digest mismatch")
    return artifact


def _ref_from_uri(uri: str, model: type[Artifact]) -> CanArtifactRef:
    raw = read_bytes_no_follow(_path(uri))
    try:
        artifact = model.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"invalid {model.__name__} artifact: {exc}") from exc
    ref = artifact_ref(uri, artifact.version, artifact.digest)
    _load(ref, model)
    return ref


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("CAN artifact ref must use a local file URI")
    return Path(unquote(parsed.path)).resolve()


__all__ = [
    "artifact_digest", "artifact_ref", "canonical_artifact_bytes",
    "canonical_body_bytes", "create_prior_policy", "create_signal_schema",
    "load_prior_policy", "load_signal_schema", "ref_from_prior_policy_uri",
    "ref_from_signal_schema_uri",
]
