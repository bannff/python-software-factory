"""Focused protected-content persistence and telemetry projection canaries."""
from __future__ import annotations

import pytest

from factory.mcp_utils.protected_persistence import (
    telemetry_projection,
    validate_protected_persistence,
)


def test_unmarked_sensitive_generic_persistence_fails_closed() -> None:
    for field in ("body", "subject", "to", "cc", "bcc", "html", "text", "query", "provider_request"):
        with pytest.raises(ValueError, match="protected inline content"):
            validate_protected_persistence({field: "unmarked@example.test"})


def test_telemetry_projection_drops_common_protected_aliases() -> None:
    secret = "telemetry-secret@example.test"
    projected = telemetry_projection({
        "body": secret, "subject": secret, "recipients": [secret],
        "to": secret, "cc": secret, "bcc": secret, "html": secret,
        "text": secret, "message": secret, "payload": secret,
        "query": secret, "provider_request": secret,
        "provider_response": secret, "attachments": [secret],
        "artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "recipient_count": 1,
    }, protected=True)
    assert projected == {
        "artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "recipient_count": 1,
    }
    assert secret not in str(projected)


def test_unmarked_sensitive_aliases_fail_closed() -> None:
    fields = (
        "body", "subject", "recipients", "to", "cc", "bcc", "html",
        "text", "message", "query", "provider_request", "provider_response",
        "providerRequest", "providerResponse", "toAddresses", "ccAddresses",
        "bccAddresses", "recipientAddresses", "htmlBody", "messageBody",
        "attachments", "raw_evidence",
    )
    for field in fields:
        with pytest.raises(ValueError, match="protected inline content"):
            validate_protected_persistence({field: "unmarked-canary@example.test"})

    with pytest.raises(ValueError, match="protected inline content"):
        validate_protected_persistence({
            "artifact_ref": "pc_v1_abcdefghijklmnopqrstuv",
            "message": "artifact-bound canary",
        })


def test_projection_handles_camel_aliases_and_exception_fields() -> None:
    canary = "projection-canary@example.test"
    projected = telemetry_projection({
        "providerRequest": canary, "rawEvidence": canary,
        "recipientAddresses": [canary], "exceptionText": canary,
        "resultCount": 2, "status": "failed",
    })
    assert projected == {"resultCount": 2, "status": "failed"}
    assert canary not in str(projected)


def test_protected_operation_classifies_names_and_markers() -> None:
    from factory.mcp_utils.protected_persistence import is_protected_operation

    assert is_protected_operation("communications.send_email", {})
    assert is_protected_operation("integrations_business_content_store", {})
    assert is_protected_operation("unrelated_tool", {"artifact_ref": "opaque"})
    assert is_protected_operation("unrelated_tool", {"protected": True})
    assert not is_protected_operation("unrelated_tool", {"status": "ok"})


@pytest.mark.parametrize("field", [
    "api_key", "apiKey", "apikey", "password", "passwd", "token",
    "access_token", "refresh_token", "session_token", "secret", "client_secret",
    "authorization", "authentication", "credential", "credentials", "private_key",
    "cookie", "set_cookie", "bearer",
])
def test_credential_aliases_are_suppressed_top_level_and_nested(field: str) -> None:
    canary = f"credential-canary-{field}"
    projected = telemetry_projection({
        field: canary,
        "route": "public-delegation",
        "result_count": 2,
        "request_digest": "a" * 64,
        "nested": {field: canary, "tool_name": "demo_safe"},
    })
    assert projected == {
        "route": "public-delegation",
        "result_count": 2,
        "request_digest": "a" * 64,
        "nested": {"tool_name": "demo_safe"},
    }
    assert canary not in repr(projected)


def test_artifact_bound_payload_rejects_arbitrary_field_aliases() -> None:
    for alias in ("notes", "memo", "detail_blob"):
        with pytest.raises(ValueError, match="protected inline content"):
            validate_protected_persistence({
                "artifact_ref": "pc_v1_abcdefghijklmnopqrstuv",
                alias: "renamed-private-canary@example.test",
            })
