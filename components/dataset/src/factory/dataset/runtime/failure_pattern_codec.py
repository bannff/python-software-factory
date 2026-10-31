"""Canonical digest codec for failure-pattern content and bindings."""
from __future__ import annotations

import hashlib
from typing import Any

from .failure_pattern_models import (
    FailurePatternDraft, FailurePatternRef, FailurePatternSpec,
)
from .scenario_codec import canonical_json


def pattern_body(pattern: FailurePatternDraft | FailurePatternSpec) -> dict[str, Any]:
    body = pattern.model_dump(mode="json", exclude={"digest"})
    body["evidence"] = sorted(body["evidence"], key=lambda item: item["evidence_id"])
    body["roles"] = sorted(body["roles"], key=lambda item: item["role"])
    body["applicability"] = sorted(
        body["applicability"], key=lambda item: (item["role"], item["operator"], item["value"]),
    )
    body["constraints"] = sorted(body["constraints"], key=lambda item: (item["kind"], item["value"]))
    return body


def build_failure_pattern(draft: FailurePatternDraft) -> FailurePatternSpec:
    body = pattern_body(draft)
    value = hashlib.sha256(canonical_json(body)).hexdigest()
    return FailurePatternSpec.model_validate({**body, "digest": value})


def verify_failure_pattern(pattern: FailurePatternSpec) -> None:
    expected = hashlib.sha256(canonical_json(pattern_body(pattern))).hexdigest()
    if expected != pattern.digest:
        raise ValueError("failure pattern canonical digest mismatch")


def pattern_ref(pattern: FailurePatternSpec) -> FailurePatternRef:
    return FailurePatternRef(
        pattern_id=pattern.pattern_id, version=pattern.version, digest=pattern.digest,
    )


def binding_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


__all__ = ["binding_digest", "build_failure_pattern", "pattern_ref", "verify_failure_pattern"]
