"""Single authoritative constructor for supported native MLX architectures."""
from __future__ import annotations

from copy import deepcopy

from .mlx_platform import require_mlx_platform

require_mlx_platform()

import mlx.nn as nn  # noqa: E402

from ..ports import TimeSeriesModelType  # noqa: E402
from .mlx_models import LSTMClassifier, TCNClassifier  # noqa: E402

_SPECS = {
    TimeSeriesModelType.lstm: (
        "factory.mlx.lstm.v1",
        {"hidden_size": 64, "num_layers": 1, "dropout": 0.1},
    ),
    TimeSeriesModelType.tcn: (
        "factory.mlx.tcn.v1",
        {"num_channels": [32, 32, 64], "kernel_size": 3, "dropout": 0.1},
    ),
}


def architecture_spec(
    model_type: TimeSeriesModelType,
) -> tuple[str, dict[str, object]]:
    """Return the exact revision and constructor for one supported family."""
    try:
        revision, constructor = _SPECS[model_type]
    except KeyError as exc:
        raise NotImplementedError(
            f"Model type '{model_type.value}' is not supported by MLX"
        ) from exc
    return revision, deepcopy(constructor)


def build_model(
    model_type: TimeSeriesModelType, input_size: int, num_classes: int,
) -> nn.Module:
    """Construct the exact model graph used by both training and cold loading."""
    _, config = architecture_spec(model_type)
    if model_type is TimeSeriesModelType.lstm:
        return LSTMClassifier(
            input_size=input_size, num_classes=num_classes, **config,
        )
    return TCNClassifier(
        input_size=input_size, num_classes=num_classes, **config,
    )


__all__ = ["architecture_spec", "build_model"]
