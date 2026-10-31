from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.agent.mcp.async_tools import _build_async_context


def test_build_async_context_merges_current_envelope_fields() -> None:
    token = set_envelope({
        "session_id": "session-1",
        "principal_id": "principal-1",
        "run_id": "run-1",
    })
    try:
        context = _build_async_context({
            "target_app": "webgoat",
            "tenant_id": "tenant-1",
        })
    finally:
        reset_envelope(token)

    assert context == {
        "session_id": "session-1",
        "principal_id": "principal-1",
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "workflow_run_id": "run-1",
        "target_app": "webgoat",
    }


def test_build_async_context_prefers_explicit_context_values() -> None:
    token = set_envelope({
        "session_id": "session-1",
        "principal_id": "principal-1",
        "run_id": "run-1",
    })
    try:
        context = _build_async_context({
            "session_id": "session-override",
            "run_id": "run-override",
            "workflow_id": "workflow-1",
        })
    finally:
        reset_envelope(token)

    assert context == {
        "session_id": "session-override",
        "principal_id": "principal-1",
        "run_id": "run-override",
        "workflow_run_id": "run-override",
        "workflow_id": "workflow-1",
    }
