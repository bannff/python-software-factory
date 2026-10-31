"""Shared fixtures for MLX pointer publication tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

import mlx.core as mx
import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.mlx_architecture import build_model
from factory.machine_learning.runtime.mlx_publication import require_mlx_reference
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import get_service, set_service

from .neural_passport_candidate import neural_candidate


@pytest.fixture(scope="module")
def mlx_pointer_case(tmp_path_factory: pytest.TempPathFactory):
    previous = get_service("tool_invoker")
    case = neural_candidate(
        tmp_path_factory.mktemp("mlx-pointer"), TimeSeriesModelType.lstm,
        backend="mlx",
    )
    try:
        yield case
    finally:
        set_service("tool_invoker", previous)


def model_args(case, root: Path) -> tuple:
    reference = Path(case[1].model_artifact.uri.removeprefix("file://"))
    source = require_mlx_reference(reference)[0]
    metadata = json.loads((source / "factory_model.json").read_bytes())
    model_type = TimeSeriesModelType(metadata["model_type"])
    model = build_model(model_type, metadata["input_size"], metadata["num_classes"])
    model.load_weights(str(source / "model.safetensors"), strict=True)
    mx.eval(model.parameters())
    return (
        root, model, model_type, metadata["input_size"], metadata["window_size"],
        metadata["num_classes"], np.asarray(metadata["scaler_mean"]),
        np.asarray(metadata["scaler_scale"]),
    )


def objects(root: Path) -> list[Path]:
    return sorted(root.glob(".*.mlx-object"))


PUBLISHER = r'''
import json, os, sys
from pathlib import Path
import numpy as np
import mlx.core as mx
from factory.machine_learning.runtime.adapters.mlx_architecture import build_model
from factory.machine_learning.runtime.adapters import mlx_artifact
from factory.machine_learning.runtime.adapters.mlx_artifact import persist_native_model
from factory.machine_learning.runtime.mlx_publication import require_mlx_reference
from factory.machine_learning.runtime.ports import TimeSeriesModelType
reference, root = Path(sys.argv[1]), Path(sys.argv[2])
source = require_mlx_reference(reference)[0]
metadata = json.loads((source / "factory_model.json").read_bytes())
model_type = TimeSeriesModelType(metadata["model_type"])
model = build_model(model_type, metadata["input_size"], metadata["num_classes"])
model.load_weights(str(source / "model.safetensors"), strict=True)
mx.eval(model.parameters())
args = (root, model, model_type, metadata["input_size"], metadata["window_size"],
        metadata["num_classes"], np.asarray(metadata["scaler_mean"]),
        np.asarray(metadata["scaler_scale"]))
if len(sys.argv) == 5:
    os.write(int(sys.argv[3]), b"r"); os.read(int(sys.argv[4]), 1)
mode = os.environ.get("MLX_TEST_CRASH")
if mode == "after-seal":
    mlx_artifact.publish_mlx_reference = lambda *_a, **_k: os._exit(73)
elif mode in {"before-rename", "after-rename"}:
    from factory.machine_learning.runtime import mlx_publication
    if mode == "before-rename":
        mlx_publication.rename_exclusive = lambda *_a, **_k: os._exit(74)
    else:
        mlx_publication.fsync_directory = lambda *_a, **_k: os._exit(75)
persist_native_model(*args)
'''


__all__ = ["PUBLISHER", "mlx_pointer_case", "model_args", "objects"]
