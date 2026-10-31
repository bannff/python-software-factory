"""Tests for AWS Verified Permissions adapter."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def adapter(mock_boto3):
    from factory.permissions.runtime.evaluation.aws import AWSVerifiedPermissionsAdapter

    return AWSVerifiedPermissionsAdapter(policy_store_id="ps-abc123")


def test_invalid_policy_store_id(mock_boto3):
    from factory.permissions.runtime.evaluation.aws import AWSVerifiedPermissionsAdapter

    with pytest.raises(ValueError, match="Invalid policy_store_id"):
        AWSVerifiedPermissionsAdapter(policy_store_id="bad id!!!")


def test_evaluate_allow(adapter):
    adapter._client.is_authorized.return_value = {
        "decision": "ALLOW",
        "determiningPolicies": [{"policyId": "p1"}],
    }
    r = adapter.evaluate(
        action="read", resource={"type": "Doc", "id": "d1"},
        context={}, principal_id="user-1",
    )
    assert r["decision"] == "allow"
    assert len(r["determining_policies"]) == 1


def test_evaluate_deny(adapter):
    adapter._client.is_authorized.return_value = {
        "decision": "DENY", "determiningPolicies": [],
    }
    r = adapter.evaluate(
        action="delete", resource={"type": "Doc", "id": "d1"},
        context={},
    )
    assert r["decision"] == "deny"


def test_evaluate_with_tenant_context(adapter):
    adapter._client.is_authorized.return_value = {
        "decision": "ALLOW", "determiningPolicies": [],
    }
    adapter.evaluate(
        action="read", resource={"type": "Doc", "id": "d1"},
        context={"env": "prod"}, tenant_id="t1",
    )
    call_kwargs = adapter._client.is_authorized.call_args[1]
    ctx_map = call_kwargs["context"]["contextMap"]
    assert "tenant_id" in ctx_map
    assert "env" in ctx_map


def test_explain_returns_trace(adapter):
    adapter._client.is_authorized.return_value = {
        "decision": "ALLOW",
        "determiningPolicies": [{"policyId": "p1"}],
        "errors": [],
    }
    r = adapter.explain(
        action="read", resource={"type": "Doc", "id": "d1"},
        context={}, principal_id="user-1",
    )
    assert r["decision"] == "allow"
    assert r["trace_id"] == "verified-permissions"
    assert "p1" in r["matched_rules"]


def test_explain_deny_with_errors(adapter):
    adapter._client.is_authorized.return_value = {
        "decision": "DENY",
        "determiningPolicies": [],
        "errors": [{"errorDescription": "bad policy"}],
    }
    r = adapter.explain(
        action="write", resource={"type": "Doc", "id": "d1"}, context={},
    )
    assert r["decision"] == "deny"
    assert len(r["errors"]) == 1


def test_health_check_ok(adapter):
    adapter._client.get_policy_store.return_value = {}
    h = adapter.health_check()
    assert h["healthy"] is True
    assert h["backend"] == "verified-permissions"
    assert "latency_ms" in h


def test_health_check_error(adapter):
    adapter._client.get_policy_store.side_effect = RuntimeError("no store")
    h = adapter.health_check()
    assert h["healthy"] is False
    assert "no store" in h["message"]


def test_infrastructure_spec(adapter):
    spec = adapter.infrastructure_spec()
    assert spec["service"] == "verifiedpermissions"
    assert spec["construct"] == "PolicyStore"


def test_build_request_no_principal(adapter):
    req = adapter._build_request(
        action="read", resource={"type": "Doc", "id": "d1"}, context={},
    )
    assert "principal" not in req


def test_build_request_with_principal(adapter):
    req = adapter._build_request(
        action="read", resource={"type": "Doc", "id": "d1"},
        context={}, principal_id="u1",
    )
    assert req["principal"]["entityId"] == "u1"


def test_build_request_empty_context_no_tenant(adapter):
    req = adapter._build_request(
        action="read", resource={"type": "Doc", "id": "d1"}, context={},
    )
    assert "context" not in req
