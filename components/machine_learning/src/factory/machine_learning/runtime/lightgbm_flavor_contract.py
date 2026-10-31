"""Native-free exact MLflow LightGBM flavor contract."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

ALLOWED_FILES = {
    "MLmodel", "conda.yaml", "model.lgb", "python_env.yaml", "requirements.txt",
}
_METADATA_FIXED = {
    "schema_version": 1, "classes": [0, 1], "positive_class": 1,
    "positive_class_index": 1, "threshold": 0.5,
    "prediction_rule": "argmax_tie_to_class_0", "raw_score": False,
    "feature_importance_type": "split", "iteration_semantics": "all_iterations",
}
_TRUSTED_TYPE_NAMES = {
    "collections.OrderedDict", "lightgbm.basic.Booster",
    "lightgbm.sklearn.LGBMClassifier", "lightgbm.sklearn.LGBMRegressor",
}


def lightgbm_metadata(width: int) -> dict[str, Any]:
    return {**_METADATA_FIXED, "feature_width": width}


def validate_lightgbm_flavor(source: str | Path) -> dict[str, Any]:
    path = Path(source).expanduser().absolute()
    if not path.is_dir() or path.is_symlink():
        raise ValueError("MLflow LightGBM flavor must be a regular directory")
    items = list(path.iterdir())
    if {item.name for item in items} != ALLOWED_FILES or any(
        not item.is_file() or item.is_symlink() for item in items
    ):
        raise ValueError("MLflow LightGBM flavor contains missing or extra files")
    try:
        document = yaml.safe_load((path / "MLmodel").read_text())
    except Exception as exc:
        raise ValueError("MLflow LightGBM metadata is malformed") from exc
    if not isinstance(document, dict) or set(document.get("flavors", {})) != {
        "lightgbm", "python_function",
    }:
        raise ValueError("MLflow model must contain exact LightGBM and pyfunc flavors")
    _validate_versions(document, path)
    _validate_flavors(document["flavors"])
    return _validate_metadata(document.get("metadata"))


def _validate_versions(document: dict[str, Any], path: Path) -> None:
    requirements = "\n".join([
        f"lightgbm=={version('lightgbm')}", f"mlflow=={version('mlflow')}",
    ])
    if (
        document.get("mlflow_version") != version("mlflow")
        or document["flavors"]["lightgbm"].get("lgb_version") != version("lightgbm")
        or (path / "requirements.txt").read_text() != requirements
    ):
        raise ValueError("MLflow LightGBM declared versions are not exact")


def _validate_flavors(flavors: dict[str, Any]) -> None:
    lightgbm, pyfunc = flavors["lightgbm"], flavors["python_function"]
    expected_lgb = {
        "code", "data", "lgb_version", "model_class", "serialization_format",
        "skops_trusted_types",
    }
    if not isinstance(lightgbm, dict) or set(lightgbm) != expected_lgb or (
        lightgbm.get("code") is not None
        or lightgbm.get("data") != "model.lgb"
        or lightgbm.get("model_class") != "lightgbm.basic.Booster"
        or lightgbm.get("serialization_format") != "skops"
        or not isinstance(lightgbm.get("skops_trusted_types"), list)
        or set(lightgbm["skops_trusted_types"]) != _TRUSTED_TYPE_NAMES
    ):
        raise ValueError("MLflow LightGBM flavor is not the sealed native Booster")
    required_pyfunc = {"data", "env", "loader_module", "python_version"}
    if not isinstance(pyfunc, dict) or set(pyfunc) not in (
        required_pyfunc, required_pyfunc | {"code"},
    ) or (
        pyfunc.get("code") is not None or pyfunc.get("data") != "model.lgb"
        or pyfunc.get("loader_module") != "mlflow.lightgbm"
        or pyfunc.get("env") != {
            "conda": "conda.yaml", "virtualenv": "python_env.yaml",
        }
    ):
        raise ValueError("MLflow pyfunc flavor is not the sealed LightGBM loader")


def _validate_metadata(value: Any) -> dict[str, Any]:
    expected_keys = {*_METADATA_FIXED, "feature_width"}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError("MLflow classifier metadata fields are not exact")
    fixed = {key: value[key] for key in _METADATA_FIXED}
    if fixed != _METADATA_FIXED or any(
        type(value[key]) is not type(expected) for key, expected in _METADATA_FIXED.items()
    ):
        raise ValueError("MLflow classifier metadata values are not exact")
    if type(value["feature_width"]) is not int or value["feature_width"] <= 0:
        raise ValueError("MLflow classifier feature width is invalid")
    return value


__all__ = ["ALLOWED_FILES", "lightgbm_metadata", "validate_lightgbm_flavor"]
