"""Deterministic canonical codec for immutable model passports."""
from __future__ import annotations

from typing import Any

from .model_passport import ModelPassport, ModelPassportBody
from .passport_validation import canonical_json, semantic_digest


def _body_json(value: ModelPassportBody) -> dict[str, Any]:
    exclude = {"passport_digest"} if isinstance(value, ModelPassport) else set()
    if not value.evaluation_adequacy:
        exclude.add("evaluation_adequacy")
    return value.model_dump(mode="json", exclude=exclude)


def create_model_passport(**values: Any) -> ModelPassport:
    """Validate a semantic body, then bind its deterministic SHA-256 digest."""
    values.pop("passport_digest", None)
    body = ModelPassportBody.model_validate(values)
    payload = body.model_dump(mode="python")
    return ModelPassport.model_validate({
        **payload, "passport_digest": semantic_digest(_body_json(body)),
    })


def passport_body_bytes(passport: ModelPassport) -> bytes:
    return canonical_json(_body_json(passport))


def passport_artifact_bytes(passport: ModelPassport) -> bytes:
    payload = passport.model_dump(mode="json")
    if not passport.evaluation_adequacy:
        payload.pop("evaluation_adequacy", None)
    return canonical_json(payload)


def load_model_passport(value: str | bytes | ModelPassport) -> ModelPassport:
    if isinstance(value, ModelPassport):
        passport = value
        raw = passport_artifact_bytes(passport)
    else:
        raw = value.encode() if isinstance(value, str) else value
        try:
            passport = ModelPassport.model_validate_json(raw)
        except Exception as exc:
            raise ValueError(f"invalid model passport: {exc}") from exc
    if raw != passport_artifact_bytes(passport):
        raise ValueError("model passport bytes are not canonical")
    return passport


__all__ = [
    "create_model_passport", "load_model_passport", "passport_artifact_bytes",
    "passport_body_bytes",
]
