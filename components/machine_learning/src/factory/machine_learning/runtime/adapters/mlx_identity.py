"""One exact lifecycle identity for the pinned native MLX backend."""
from __future__ import annotations

from ..passport_native_contract import native_conformance_identity
from ..timeseries_identity import TimeSeriesLifecycleIdentity
from .mlx_platform import MLX_VERSION

BACKEND = "mlx"
FRAMEWORK = "mlx"
LOADER = "mlx.nn.Module.load_weights"
ARTIFACT_FORMAT = "mlx-safetensors"
VERIFIER = native_conformance_identity(LOADER)[1]

MLX_LIFECYCLE = TimeSeriesLifecycleIdentity(
    backend=BACKEND,
    framework=FRAMEWORK,
    framework_version=MLX_VERSION,
    loader=LOADER,
    artifact_format=ARTIFACT_FORMAT,
    verifier_identity=VERIFIER,
)

__all__ = [
    "ARTIFACT_FORMAT", "BACKEND", "FRAMEWORK", "LOADER", "MLX_LIFECYCLE",
    "VERIFIER",
]
