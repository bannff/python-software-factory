"""Schema tests for the new ``domain_class`` field on LearningEventPayload.

bd python-factory-twxj0 — adds ``domain_class:str=Field(default="",
validation_alias=AliasChoices("domain_class","vuln_class"))`` so domain
agents (wine, workout, ...) can propagate a domain bucket alongside the
legacy ``vuln_class``. Per meta-architect Q2 verdict the two fields MAY
diverge, so there is no mismatch validator — round-trip should preserve
both values verbatim.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.events.runtime.learning_contracts import (
    LEARNING_EVENT_MODELS,
    LearningEventPayload,
    RewardComputedPayload,
    validate_learning_payload,
)


def test_domain_class_default_empty() -> None:
    """Producers that omit the field land on an empty string."""
    payload = LearningEventPayload(run_id="r-1", workflow_run_id="wf-1")
    assert payload.domain_class == ""


def test_domain_class_set_directly() -> None:
    """Setting domain_class directly is preserved."""
    payload = LearningEventPayload(
        run_id="r-1", workflow_run_id="wf-1", domain_class="wine",
    )
    assert payload.domain_class == "wine"
    # Independent field — not coerced from vuln_class default.
    assert payload.vuln_class == ""


def test_domain_class_alias_from_vuln_class_only() -> None:
    """When only vuln_class is set, AliasChoices backfills domain_class."""
    payload = LearningEventPayload.model_validate({
        "run_id": "r-1", "workflow_run_id": "wf-1", "vuln_class": "IDOR",
    })
    assert payload.vuln_class == "IDOR"
    # AliasChoices means an unset domain_class field reads from vuln_class.
    assert payload.domain_class == "IDOR"


def test_domain_class_diverges_from_vuln_class() -> None:
    """Per meta-architect Q2: divergent values are explicitly allowed."""
    payload = LearningEventPayload.model_validate({
        "run_id": "r-1", "workflow_run_id": "wf-1",
        "domain_class": "security_idor", "vuln_class": "IDOR",
    })
    assert payload.domain_class == "security_idor"
    assert payload.vuln_class == "IDOR"


def test_domain_class_reward_computed_validates() -> None:
    """RewardComputedPayload (subclass) inherits domain_class field."""
    payload = validate_learning_payload(
        "reward.computed",
        {
            "run_id": "r-1", "workflow_run_id": "wf-1",
            "status": "completed",
            "idempotency_key": "reward:wf-1:v1",
            "domain_class": "workout", "vuln_class": "FORM_ANALYSIS",
        },
    )
    assert payload["domain_class"] == "workout"
    assert payload["vuln_class"] == "FORM_ANALYSIS"


def test_domain_class_extra_forbid_still_rejects_unknowns() -> None:
    """domain_class is now known; unknown fields still reject."""
    try:
        RewardComputedPayload.model_validate({
            "run_id": "r-1", "workflow_run_id": "wf-1",
            "idempotency_key": "k", "status": "x",
            "domain_class": "wine",
            "novel_field_we_did_not_declare": True,
        })
    except ValidationError:
        return
    raise AssertionError("expected ValidationError on unknown field")


@settings(max_examples=30, deadline=None)
@given(domain=st.text(min_size=0, max_size=32),
       vuln=st.text(min_size=0, max_size=32))
def test_domain_class_round_trip_property(domain: str, vuln: str) -> None:
    """Arbitrary string pairs round-trip through validate_learning_payload.

    Per Pydantic AliasChoices semantics, when both keys are present the first
    listed choice (``domain_class``) wins — so the resulting payload field
    equals the explicit ``domain_class`` input verbatim, even when empty.
    """
    out = validate_learning_payload(
        "memory.learning_stored",
        {
            "run_id": "r-1", "workflow_run_id": "wf-1",
            "summary_type": "workflow_rl",
            "idempotency_key": "k:1",
            "domain_class": domain, "vuln_class": vuln,
        },
    )
    # When both keys are present, AliasChoices picks the first match
    # (``domain_class``).
    assert out["domain_class"] == domain
    assert out["vuln_class"] == vuln


@settings(max_examples=20, deadline=None)
@given(vuln=st.text(min_size=1, max_size=32))
def test_domain_class_alias_fallback_property(vuln: str) -> None:
    """When only vuln_class is set, AliasChoices reads it for domain_class."""
    out = validate_learning_payload(
        "memory.learning_stored",
        {
            "run_id": "r-1", "workflow_run_id": "wf-1",
            "summary_type": "workflow_rl",
            "idempotency_key": "k:1",
            "vuln_class": vuln,
        },
    )
    assert out["domain_class"] == vuln
    assert out["vuln_class"] == vuln


def test_all_learning_models_carry_domain_class() -> None:
    """Every LearningEventPayload subclass picks up the new field."""
    for event_type, model in LEARNING_EVENT_MODELS.items():
        schema = model.model_json_schema()
        props = schema.get("properties", {})
        assert "domain_class" in props, (
            f"{event_type} -> {model.__name__} is missing domain_class"
        )
