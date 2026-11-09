"""Report whether the optional ``ml`` dependency group is installed.

The training libraries ship in a separate uv group, so a default install
advertises training it cannot run. Checking with ``find_spec`` avoids importing
torch (slow) just to answer a health question.
"""
from __future__ import annotations

from importlib.util import find_spec

TRAINING_LIBS = ("lightgbm", "sklearn", "torch")
INSTALL_HINT = (
    "uvx --from uv==0.12.0 uv sync --group ml "
    "--config-settings-package lightgbm:cmake.define.USE_OPENMP=OFF"
)


def missing_training_libs() -> list[str]:
    return [name for name in TRAINING_LIBS if find_spec(name) is None]


__all__ = ["INSTALL_HINT", "TRAINING_LIBS", "missing_training_libs"]
