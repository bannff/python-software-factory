"""Typed result envelopes for fail-closed CAN inference."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanPredictionSuccess(_Result):
    status: Literal["ok"] = "ok"
    model_id: str
    contract_digest: str
    can_id: str
    anomaly_score: float
    prediction: Literal["normal", "anomaly"]
    confidence: float
    alert_level: Literal["normal", "warning", "critical"]
    top_signals: tuple[dict[str, Any], ...] = ()
    window_size: int
    input_shape: tuple[int, ...]


class CanPredictionError(_Result):
    status: Literal["error"] = "error"
    model_id: str
    error_code: str
    error: str
    contract_digest: str | None = None
    can_id: str | None = None


__all__ = ["CanPredictionError", "CanPredictionSuccess"]
