from __future__ import annotations

from factory.auth.interface import WorkloadGrant
from factory.mcp_server.runtime.access_control import GatewayAccessController
from factory.mcp_utils.interface import AccessOperation, AccessPrincipal

class Permit:
    def __init__(self):
        self.context = None

    def decide(self, **kwargs):
        self.context = kwargs["context"]
        return {"decision": "allow", "reason": "ok", "policy_id": "p"}


def _principal(**claims):
    requested_tools = claims.pop("allowed_tools", None)
    principal_subject = claims.pop("_principal_subject", None)
    principal_client = claims.pop("_principal_client", None)
    grant = WorkloadGrant.create(
        launch_id="l", generation=1, tenant_id="t", audience="companion-x",
        allowed_tools=["graph_get_entity"],
    )
    base = grant.model_dump(mode="json")
    base["actor_type"] = "workload"
    base["subject"] = f"svc:squad:{base['launch_id']}"
    base["credential_id"] = "c"
    base.update(claims)
    tools = requested_tools or base["allowed_tools"]
    base["allowed_tools"] = tools
    return AccessPrincipal(
        subject=principal_subject or base["subject"], tenant_id="t",
        client_id=principal_client or base["credential_id"], scopes=tuple(tools),
        roles=("workload",), claims=base,
    )


def _operation(name="graph_get_entity", category="operational"):
    return AccessOperation(
        action="execute", public_name=name, brick="graph",
        source_name="graph.get_entity", category=category,
    )


def test_workload_exact_leaf_reaches_yaml_with_safe_context(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    permit = Permit()
    principal = _principal()
    decision = GatewayAccessController(permit).decide(principal, _operation())
    assert decision.allowed
    assert permit.context["actor_type"] == "workload"
    assert permit.context["capability_scope_digest"] == \
        principal.claims["capability_scope_digest"]
    assert "access_token" not in permit.context


def test_workload_scope_authoring_meta_and_binding_denied_before_policy(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    valid = _principal()
    cases = [
        (valid, _operation("graph_get_entity_extra")),
        (_principal(allowed_tools=["call_brick_tool"]), _operation("call_brick_tool")),
        (valid, _operation(category="authoring")),
        (_principal(audience="other"), _operation()),
        (_principal(_principal_subject="svc:squad:other"), _operation()),
        (_principal(_principal_client="other"), _operation()),
    ]
    for principal, operation in cases:
        permit = Permit()
        assert not GatewayAccessController(permit).decide(principal, operation).allowed
        assert permit.context is None


def test_existing_user_behavior_is_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    permit = Permit()
    user = AccessPrincipal(subject="u", tenant_id="t", client_id="c", roles=("operator",))
    assert GatewayAccessController(permit).decide(user, _operation()).allowed


def test_gateway_does_not_reconstruct_provider_owned_grant_validity(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    permit = Permit()
    principal = _principal(
        capability_scope_digest="provider-opaque", launch_id="provider-owned",
        generation=0, manifest_digest="provider-verified",
    )
    assert GatewayAccessController(permit).decide(principal, _operation()).allowed
