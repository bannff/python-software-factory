"""Canonical codec for immutable CAN feature contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .can_contract_models import CanFeatureContract


def create_can_feature_contract(**values: Any) -> CanFeatureContract:
    signal = tuple(values.get("signal_columns") or ())
    context = tuple(values.get("context_columns") or ())
    values["signal_columns"] = signal
    values["context_columns"] = context
    values.setdefault("ordered_columns", tuple(
        [f"signal:{name}" for name in signal]
        + [f"context:{name}" for name in context]
    ))
    timesteps = int(values["num_timesteps"])
    width = len(signal) + len(context)
    values.setdefault("required_shape", (timesteps, width))
    values.setdefault("required_width", timesteps * width)
    values["digest"] = "0" * 64
    provisional = CanFeatureContract.model_validate(values)
    values = provisional.model_dump()
    values["digest"] = contract_digest(provisional)
    contract = CanFeatureContract.model_validate(values)
    if contract.digest != contract_digest(contract):
        raise ValueError("contract digest does not match canonical body")
    return contract


def canonical_contract_body(contract: CanFeatureContract) -> bytes:
    return _canonical(contract.model_dump(mode="json", exclude={"digest"}))


def contract_digest(contract: CanFeatureContract) -> str:
    return hashlib.sha256(canonical_contract_body(contract)).hexdigest()


def contract_artifact_bytes(contract: CanFeatureContract) -> bytes:
    return _canonical(contract.model_dump(mode="json"))


def save_can_feature_contract(contract: CanFeatureContract, path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = contract_artifact_bytes(contract)
    if target.exists() and target.read_bytes() != content:
        raise ValueError("immutable CAN feature contract already exists with different bytes")
    target.write_bytes(content)
    return target.resolve().as_uri()


def load_can_feature_contract(source: str | Path | bytes) -> CanFeatureContract:
    raw = source if isinstance(source, bytes) else _path(source).read_bytes()
    try:
        contract = CanFeatureContract.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"invalid CAN feature contract: {exc}") from exc
    if raw != contract_artifact_bytes(contract):
        raise ValueError("contract artifact bytes are not canonical")
    if contract.digest != contract_digest(contract):
        raise ValueError("contract digest does not match canonical body")
    return contract


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _path(source: str | Path) -> Path:
    if isinstance(source, Path):
        return source
    parsed = urlparse(source)
    return Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(source)


__all__ = [
    "canonical_contract_body", "contract_artifact_bytes", "contract_digest",
    "create_can_feature_contract", "load_can_feature_contract",
    "save_can_feature_contract",
]
