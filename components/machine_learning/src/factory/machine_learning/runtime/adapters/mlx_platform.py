"""Fail-closed platform and package guard for native MLX execution."""
from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version

MLX_VERSION = "0.31.1"


def require_mlx_platform() -> None:
    """Require Apple Silicon macOS and the one approved MLX build."""
    system, machine = platform.system(), platform.machine()
    if system != "Darwin" or machine != "arm64":
        raise RuntimeError(
            "MLX requires Darwin arm64 (Apple Silicon); "
            f"found {system} {machine}"
        )
    try:
        installed = version("mlx")
    except PackageNotFoundError as exc:
        raise RuntimeError(f"MLX {MLX_VERSION} is required but not installed") from exc
    if installed != MLX_VERSION:
        raise RuntimeError(
            f"MLX version drift: required {MLX_VERSION}, found {installed}"
        )


__all__ = ["MLX_VERSION", "require_mlx_platform"]
