"""Exact projections of Dataset-owned CAN authorization artifacts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, ConfigDict, field_validator


class CanDatasetArtifactRef(BaseModel):
    """Body-digest identity issued by Dataset and bound into ML contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    uri: str
    version: str
    digest: str

    @field_validator("uri", "version")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Dataset artifact ref fields must be non-empty")
        return value

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        _sha256(value, "Dataset artifact ref")
        return value


@dataclass(frozen=True)
class CanPriorPolicyProjection:
    enabled: bool
    columns: tuple[str, ...]


@dataclass(frozen=True)
class CanSignalSchemaProjection:
    can_id: str
    columns: tuple[str, ...]

    def columns_for(self, can_id: str) -> tuple[str, ...]:
        if can_id != self.can_id:
            raise ValueError(f"signal schema missing CAN-ID {can_id}")
        return self.columns


def ref_from_uri(uri: str) -> CanDatasetArtifactRef:
    """Read one canonical Dataset artifact and return its body-digest ref."""
    body, _ = _read_canonical(uri)
    return CanDatasetArtifactRef(
        uri=uri, version=str(body.get("version", "")), digest=str(body.get("digest", "")),
    )


def load_prior_policy(ref: CanDatasetArtifactRef) -> CanPriorPolicyProjection:
    body = _load(ref, {
        "version", "digest", "source_digests", "use_context", "prior_data_allowlist",
    })
    enabled = body.get("use_context")
    columns = body.get("prior_data_allowlist")
    if not isinstance(enabled, bool) or not _string_list(columns, allow_empty=True):
        raise ValueError("invalid prior-data policy projection")
    assert isinstance(columns, list)
    if len(set(columns)) != len(columns) or bool(columns) != enabled:
        raise ValueError("prior-data policy projection is inconsistent")
    return CanPriorPolicyProjection(enabled=enabled, columns=tuple(columns))


def load_signal_schema(ref: CanDatasetArtifactRef) -> CanSignalSchemaProjection:
    body = _load(ref, {
        "version", "digest", "source_digests", "can_id", "signal_columns",
    })
    can_id, columns = body.get("can_id"), body.get("signal_columns")
    if not isinstance(can_id, str) or not can_id or not _string_list(columns):
        raise ValueError("invalid signal schema projection")
    assert isinstance(columns, list)
    if len(set(columns)) != len(columns):
        raise ValueError("signal schema columns must be unique")
    return CanSignalSchemaProjection(can_id=can_id, columns=tuple(columns))


def _load(ref: CanDatasetArtifactRef, expected_keys: set[str]) -> dict[str, Any]:
    body, raw = _read_canonical(ref.uri)
    if set(body) != expected_keys:
        raise ValueError("Dataset CAN artifact has an unexpected shape")
    if body.get("version") != ref.version or body.get("digest") != ref.digest:
        raise ValueError("Dataset CAN artifact reference mismatch")
    digest_body = dict(body)
    digest_body.pop("digest")
    calculated = hashlib.sha256(_canonical(digest_body)).hexdigest()
    if calculated != ref.digest:
        raise ValueError("Dataset CAN artifact body digest mismatch")
    sources = body.get("source_digests")
    if not _string_list(sources, allow_empty=True):
        raise ValueError("Dataset CAN artifact source digests are invalid")
    assert isinstance(sources, list)
    for source in sources:
        _sha256(source, "source")
    if raw != _canonical(body):
        raise ValueError("Dataset CAN artifact bytes are not canonical")
    return body


def _read_canonical(uri: str) -> tuple[dict[str, Any], bytes]:
    raw = _path(uri).read_bytes()
    try:
        body = json.loads(raw)
    except Exception as exc:
        raise ValueError("invalid Dataset CAN artifact JSON") from exc
    if not isinstance(body, dict) or raw != _canonical(body):
        raise ValueError("Dataset CAN artifact bytes are not canonical")
    return body, raw


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()


def _string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def _sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} digest must be lowercase SHA-256")


def _path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("Dataset CAN artifact must use a local file URI")
    return Path(unquote(parsed.path)).resolve()


__all__ = [
    "CanDatasetArtifactRef", "CanPriorPolicyProjection",
    "CanSignalSchemaProjection", "load_prior_policy", "load_signal_schema",
    "ref_from_uri",
]
