"""Strict parent/child contracts for isolated LightGBM conformance."""
from __future__ import annotations

from pydantic import ConfigDict, Field

from .model_passport import ModelPassport
from .passport_refs import FrozenModel
from .passport_validation import require_digest, require_text


class PassportProbeInput(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    passport: ModelPassport
    snapshot_root: str
    model_path: str
    contract_path: str
    prepared_x_path: str
    prepared_y_path: str
    prepared_timespans_path: str | None = None
    nonce: str


class PassportProbeResult(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    child_pid: int = Field(strict=True, gt=0)
    parent_nonce: str
    passport_digest: str
    model_digest: str
    probe_rows: int = Field(strict=True, gt=0)
    probe_width: int = Field(strict=True, gt=0)
    probe_input_digest: str
    probe_output_digest: str
    predictions_digest: str
    python: str

    @classmethod
    def _checked_digest(cls, value: str) -> str:
        return require_digest(value, "probe digest")

    from pydantic import field_validator

    _digests = field_validator(
        "passport_digest", "model_digest", "probe_input_digest",
        "probe_output_digest", "predictions_digest",
    )(_checked_digest)
    _texts = field_validator("parent_nonce", "python")(
        lambda value: require_text(value, "probe identity")
    )


__all__ = ["PassportProbeInput", "PassportProbeResult"]
