import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.events.runtime.learning_contracts import (
    VERDICT_BASELINE_SET,
    VERDICT_IMPROVED,
    VERDICT_REGRESSED,
    VERDICT_STABLE,
    LearningAppliedPayload,
    WorkflowImprovementPayload,
    learning_event_schemas,
    validate_learning_payload,
)


def test_validate_learning_payload_normalizes_reward_event() -> None:
    payload = validate_learning_payload(
        "reward.computed",
        {
            "run_id": "run-123",
            "workflow_run_id": "wf-123",
            "status": "completed",
            "idempotency_key": "reward:wf-123:v1",
        },
    )

    assert payload["profile_id"] == "default"
    assert payload["reward_unit"] == "tokens"
    assert payload["score"] == 0


def test_validate_learning_payload_rejects_unknown_fields() -> None:
    with pytest.raises(Exception):
        validate_learning_payload(
            "wallet.rewarded",
            {
                "run_id": "run-123",
                "workflow_run_id": "wf-123",
                "wallet_id": "wallet-1",
                "idempotency_key": "wallet:wf-123:v1:12",
                "unexpected": True,
            },
        )


def test_learning_event_schemas_exposes_all_canonical_event_types() -> None:
    schemas = learning_event_schemas()

    assert set(schemas) == {
        "reward.computed",
        "wallet.rewarded",
        "memory.learning_stored",
        "convergence.checked",
        "learning.applied",
        "workflow.improvement",
    }


# -- LearningAppliedPayload contract — bd python-factory-o7t8 ----------------

_id = st.text(min_size=1, max_size=20,
              alphabet=st.characters(whitelist_categories=("L", "N")))


def test_learning_applied_idempotency_key_min_length_enforced() -> None:
    """Empty idempotency_key must fail validation."""
    with pytest.raises(ValidationError):
        LearningAppliedPayload(
            run_id="run-1",
            workflow_run_id="run-1",
            idempotency_key="",
        )


def test_learning_applied_required_fields_present() -> None:
    """run_id, workflow_run_id, idempotency_key are required (inherited + own)."""
    schema = LearningAppliedPayload.model_json_schema()
    required = set(schema.get("required", []))
    assert {"run_id", "workflow_run_id", "idempotency_key"}.issubset(required)


def test_learning_applied_defaults_work() -> None:
    """Optional fields have sensible defaults."""
    payload = LearningAppliedPayload(
        run_id="run-1",
        workflow_run_id="run-1",
        idempotency_key="learning_applied:run-1:agent:abc123",
    )
    assert payload.agent_id == ""
    assert payload.retrieved_count == 0
    assert payload.retrieved_memory_ids == []
    assert payload.query == ""


@settings(max_examples=30)
@given(run_id=_id, agent=_id, idem=_id, retrieved=st.integers(0, 100))
def test_learning_applied_roundtrips(run_id, agent, idem, retrieved):
    """validate_learning_payload accepts any well-formed LearningApplied dict."""
    p = LearningAppliedPayload(
        run_id=run_id,
        workflow_run_id=run_id,
        idempotency_key=idem,
        agent_id=agent,
        retrieved_count=retrieved,
        retrieved_memory_ids=[f"mem-{i}" for i in range(min(retrieved, 5))],
        query="some query",
    )
    out = validate_learning_payload("learning.applied", p.model_dump())
    assert out["agent_id"] == agent
    assert out["retrieved_count"] == retrieved
    assert out["idempotency_key"] == idem


# ---- bd python-factory-kq6u: WorkflowImprovementPayload contract ---- #

_VERDICT_SET = {
    VERDICT_IMPROVED, VERDICT_REGRESSED, VERDICT_STABLE, VERDICT_BASELINE_SET,
}


def test_workflow_improvement_payload_validates_with_defaults() -> None:
    """Sane defaults — verdict=baseline_set, baseline list empty, scalars 0."""
    payload = validate_learning_payload(
        "workflow.improvement",
        {
            "run_id": "run-1",
            "workflow_run_id": "wf-1",
            "idempotency_key": "improvement:wf-1:v1:n10",
        },
    )

    assert payload["verdict"] == VERDICT_BASELINE_SET
    assert payload["current_score"] == 0.0
    assert payload["baseline_score"] == 0.0
    assert payload["delta"] == 0.0
    assert payload["baseline_window_n"] == 10
    assert payload["baseline_run_ids"] == []


def test_workflow_improvement_payload_rejects_unknown_fields() -> None:
    with pytest.raises(Exception):
        validate_learning_payload(
            "workflow.improvement",
            {
                "run_id": "run-1",
                "workflow_run_id": "wf-1",
                "idempotency_key": "improvement:wf-1:v1:n10",
                "drifted": True,  # not a contract field
            },
        )


@settings(max_examples=50, deadline=None)
@given(
    current=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    baseline=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False),
    verdict=st.sampled_from(sorted(_VERDICT_SET)),
    n=st.integers(1, 20),
    baseline_run_ids=st.lists(st.text(min_size=1, max_size=24), max_size=20),
)
def test_workflow_improvement_payload_property_invariants(
    current, baseline, delta, verdict, n, baseline_run_ids,
) -> None:
    """Validated payload preserves verdict set membership and bounds."""
    payload = WorkflowImprovementPayload(
        run_id="run-h",
        workflow_run_id="wf-h",
        current_score=current,
        baseline_score=baseline,
        delta=delta,
        verdict=verdict,
        baseline_window_n=n,
        baseline_run_ids=baseline_run_ids,
        idempotency_key=f"improvement:wf-h:v1:n{n}",
    ).model_dump()

    assert payload["verdict"] in _VERDICT_SET
    assert payload["baseline_window_n"] == n
    # Producer-side bound: handler enforces N cap; contract permits any
    # length, so we only assert the field is preserved through validation.
    assert payload["baseline_run_ids"] == baseline_run_ids
