"""Narrow runtime port for isolated native LightGBM execution."""
from __future__ import annotations

from typing import Protocol

from .native_lightgbm_contracts import NativeRequest, NativeResult


class NativeLightGBMPort(Protocol):
    """Execute one closed, typed native operation in a fresh interpreter."""

    def execute(self, request: NativeRequest) -> NativeResult: ...


__all__ = ["NativeLightGBMPort"]
