import pytest

from factory.mcp_utils.context import (
    envelope_updates_from_mapping,
    get_envelope,
    get_run_id,
    get_workflow_run_id,
    normalize_envelope,
    push_envelope_updates,
    reset_envelope,
)


def test_normalize_envelope_canonicalizes_ingress_alias_without_emitting_it() -> None:
    envelope = normalize_envelope({"session_id": "s1", "workflow_run_id": "run-1"})

    assert envelope["run_id"] == "run-1"
    assert "workflow_run_id" not in envelope


def test_normalize_envelope_rejects_conflicting_run_aliases() -> None:
    with pytest.raises(ValueError, match="conflicting run_id/workflow_run_id"):
        normalize_envelope({"run_id": "run-1", "workflow_run_id": "run-2"})


def test_push_envelope_updates_sets_canonical_run_and_restores() -> None:
    token = push_envelope_updates(session_id="s1", workflow_run_id="run-3")
    try:
        assert get_run_id() == "run-3"
        assert get_workflow_run_id() == "run-3"
        assert "workflow_run_id" not in (get_envelope() or {})
    finally:
        reset_envelope(token)

    assert get_run_id() is None
    assert get_workflow_run_id() is None


def test_envelope_updates_from_mapping_filters_non_contract_fields() -> None:
    updates = envelope_updates_from_mapping({
        "session_id": "s1", "principal_id": "p1", "workflow_run_id": "run-4",
        "target_app": "webgoat", "attributes": {"source": "test"},
        "tracestate": "vendor=value",
    })

    assert updates == {
        "session_id": "s1", "principal_id": "p1", "run_id": "run-4",
        "attributes": {"source": "test"}, "tracestate": "vendor=value",
    }
