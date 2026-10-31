"""Strict JSONL I/O around the shared CAN tensor materializer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np

from ..can_feature_contract import CanFeatureContract, load_can_feature_contract
from ..can_materializer import materialize_can_windows


def convert_jsonl_windows(
    jsonl_path: str | Path, output_dir: str | Path, max_features: int = 23,
    prefix: str = "can", layout: str = "3d", *,
    contract: CanFeatureContract | None = None, contract_uri: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    return convert_records_to_npy(
        load_jsonl_windows(jsonl_path), output_dir, max_features, prefix, layout,
        contract=contract, contract_uri=contract_uri,
    )


def convert_records_to_npy(
    records: list[dict[str, Any]], output_dir: str | Path,
    max_features: int = 23, prefix: str = "can", layout: str = "3d", *,
    contract: CanFeatureContract | None = None, contract_uri: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Write exact 3D and flattened tensors; never slice or pad features."""
    _validate_layout(layout)
    resolved = contract or (load_can_feature_contract(contract_uri) if contract_uri else None)
    if resolved is None:
        raise ValueError("CAN feature contract is required")
    width = len(resolved.ordered_columns)
    if width > max_features:
        raise ValueError(f"contract width {width} exceeds max_features {max_features}")
    batch = materialize_can_windows(records, resolved)
    X_3d, y = batch.X, batch.y
    names = list(resolved.ordered_columns)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    x3d_path, x2d_path = out / f"{prefix}_X_3d.npy", out / f"{prefix}_X_2d.npy"
    y_path = out / f"{prefix}_y.npy"
    np.save(x3d_path, X_3d)
    np.save(x2d_path, X_3d.reshape(X_3d.shape[0], -1))
    np.save(y_path, y)
    info = _info(X_3d, y, names)
    timespans_uri = extract_timespans_npy(records, out, prefix)
    if timespans_uri is not None:
        info["timespans_uri"] = timespans_uri
    info.update({
        "x_3d_uri": x3d_path.resolve().as_uri(),
        "x_2d_uri": x2d_path.resolve().as_uri(),
        "y_uri": y_path.resolve().as_uri(),
        "contract_digest": resolved.digest if resolved else None,
    })
    selected = info["x_2d_uri"] if layout == "2d" else info["x_3d_uri"]
    return selected, info["y_uri"], info


def convert_jsonl_to_npy(
    jsonl_path: str | Path, output_dir: str | Path, max_features: int = 23,
    prefix: str = "can", layout: str = "3d", *, contract_uri: str | None = None,
) -> tuple[str, str]:
    x_uri, y_uri, _ = convert_jsonl_windows(
        jsonl_path, output_dir, max_features, prefix, layout,
        contract_uri=contract_uri,
    )
    return x_uri, y_uri


def inspect_jsonl_windows(
    jsonl_path: str | Path, max_features: int = 23,
    *, contract_uri: str | None = None,
) -> dict[str, Any]:
    records = load_jsonl_windows(jsonl_path)
    contract = load_can_feature_contract(contract_uri) if contract_uri else None
    if contract is None:
        raise ValueError("CAN feature contract is required")
    width = len(contract.ordered_columns)
    if width > max_features:
        raise ValueError(f"contract width {width} exceeds max_features {max_features}")
    batch = materialize_can_windows(records, contract)
    return _info(batch.X, batch.y, list(contract.ordered_columns))


def load_jsonl_windows(jsonl_path: str | Path) -> list[dict[str, Any]]:
    path = _path(jsonl_path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Malformed JSONL record at line {line_number}")
        records.append(value)
    if not records:
        raise ValueError("No records in JSONL artifact")
    return records


def windows_to_arrays(
    records: list[dict[str, Any]], layout: str = "3d", max_features: int = 23,
    *, contract: CanFeatureContract | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    _validate_layout(layout)
    if contract is None:
        raise ValueError("CAN feature contract is required")
    width = len(contract.ordered_columns)
    if width > max_features:
        raise ValueError(f"contract width {width} exceeds max_features {max_features}")
    batch = materialize_can_windows(records, contract, flatten=layout == "2d")
    return batch.X, batch.y


def extract_timespans_npy(
    records: list[dict[str, Any]], output_dir: str | Path, prefix: str = "can",
) -> str | None:
    if not records or not any("timespans" in record for record in records):
        return None
    timesteps = int(records[0].get("num_timesteps", 0))
    values = np.empty((len(records), timesteps), dtype=np.float64)
    for index, record in enumerate(records):
        row = np.asarray(record.get("timespans", []))
        if row.shape != (timesteps,):
            raise ValueError("timespans shape is inconsistent")
        if row.dtype.kind not in "fiu" or not np.isfinite(row).all() or not (row > 0).all():
            raise ValueError("timespans must be finite positive numeric values")
        values[index] = row
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prefix}_timespans.npy"
    np.save(path, values)
    return path.resolve().as_uri()


def _info(X: np.ndarray, y: np.ndarray, names: list[str]) -> dict[str, Any]:
    distribution = {0: int((y == 0).sum()), 1: int((y == 1).sum())}
    return {
        "n_samples": int(X.shape[0]), "window_size": int(X.shape[1]),
        "n_features": int(X.shape[2]), "signal_names": names,
        "label_distribution": distribution,
        "label_dist": {str(key): value for key, value in distribution.items()},
    }


def _validate_layout(layout: str) -> None:
    if layout not in {"2d", "3d"}:
        raise ValueError("layout must be '2d' or '3d'")


def _path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value
    parsed = urlparse(value)
    return Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(value)


__all__ = [
    "convert_jsonl_to_npy", "convert_jsonl_windows", "convert_records_to_npy",
    "extract_timespans_npy", "inspect_jsonl_windows", "load_jsonl_windows",
    "windows_to_arrays",
]
