"""Property tests for authoritative envelope normalization."""

from hypothesis import given, settings, strategies as st
import pytest

from factory.mcp_utils.context import (
    get_envelope, get_run_id, get_session_id, get_workflow_run_id,
    normalize_envelope, push_envelope_updates, reset_envelope,
)

id_st = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))


@given(session_id=st.one_of(st.none(), id_st), run_id=st.one_of(st.none(), id_st))
@settings(max_examples=50)
def test_normalize_envelope_is_idempotent(session_id, run_id):
    envelope = {"session_id": session_id, "run_id": run_id}
    once = normalize_envelope(envelope)
    assert normalize_envelope(once) == once
    assert "workflow_run_id" not in once


@given(run_id=id_st)
@settings(max_examples=50)
def test_workflow_alias_is_ingress_only(run_id):
    normalized = normalize_envelope({"workflow_run_id": run_id})
    assert normalized == {"run_id": run_id}


def test_normalize_envelope_rejects_conflicts() -> None:
    with pytest.raises(ValueError, match="conflicting run_id/workflow_run_id"):
        normalize_envelope({"run_id": "a", "workflow_run_id": "b"})


@given(base_session=id_st, base_run=id_st)
@settings(max_examples=50)
def test_push_updates_scope_and_reset_restore_prior_values(base_session, base_run):
    base_token = push_envelope_updates(session_id=base_session, run_id=base_run)
    try:
        assert get_session_id() == base_session
        assert get_run_id() == base_run
        assert get_workflow_run_id() == base_run
        nested_token = push_envelope_updates(session_id="nested", run_id=base_run)
        try:
            assert get_session_id() == "nested"
            assert get_run_id() == base_run
        finally:
            reset_envelope(nested_token)
        assert (get_envelope() or {}).get("session_id") == base_session
    finally:
        reset_envelope(base_token)
    assert get_envelope() is None
