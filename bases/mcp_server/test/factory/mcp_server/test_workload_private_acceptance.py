from __future__ import annotations

import asyncio
import yaml
from pydantic import BaseModel, ConfigDict

from factory.auth.interface import (
    LocalOpaqueWorkloadCredentialProvider, Runtime, WorkloadGrant,
)
from factory.auth.server import create_tool_catalog
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_server.runtime.workload_grant_policy import GatewayWorkloadGrantPolicy
from factory.mcp_utils.interface import (
    ToolResult, deterministic, get_service, ok, set_service,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(BaseModel):
    ok: bool


def _aggregator(tmp_path):
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = Runtime(
        tmp_path, workload_credentials=LocalOpaqueWorkloadCredentialProvider(),
    )
    auth = create_tool_catalog(runtime)
    demo = ToolCatalog("demo")

    @demo.tool(name="demo.leaf")
    @deterministic(input_model=Empty, output_model=Output)
    def leaf() -> ToolResult[Output]:
        return ok(Output(ok=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["auth", "demo"])
    aggregator._lazy._cache.update({"auth": auth, "demo": demo})
    return aggregator, runtime


def _call(invoker, grant, *, argument_attempt="attempt", bound_attempt="attempt",
          manifest_digest=None):
    manifest = manifest_digest or grant.manifest_digest
    binding = {"workflow_run_id": "run", "attempt_id": bound_attempt,
               "revision": 0, "manifest_digest": manifest}
    return invoker(
        {"brick_name": "auth", "tool_name": "auth.issue_workload_credential"},
        arguments={"workflow_run_id": "run", "attempt_id": argument_attempt,
                   "revision": 0, "manifest_digest": manifest,
                   "grant": grant.model_dump(mode="json")},
        idempotency_key=f"issue:{argument_attempt}:{bound_attempt}",
        envelope={"run_id": "run", "tenant_id": "tenant"}, attempt=binding,
    )


def test_real_private_service_path_rejects_tamper_before_effects(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    aggregator, runtime = _aggregator(tmp_path)
    previous = get_service("workload_grant_policy")
    set_service("workload_grant_policy", GatewayWorkloadGrantPolicy(aggregator))
    grant = WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=["demo_leaf"])
    workflow = NativeEnvelopeInvoker(aggregator).for_caller("workflow")
    wrong = NativeEnvelopeInvoker(aggregator).for_caller("agent")
    try:
        issued = _call(workflow, grant)
        structured = issued["result"]["structured_content"]
        assert structured["ok"], structured
        token = structured["data"]["credential"]["access_token"]
        credential_id = structured["data"]["credential"]["credential"]["credential_id"]
        assert len(runtime.workload_credentials._records) == 1
        errors = [
            _call(wrong, grant),
            _call(workflow, grant, argument_attempt="other"),
            _call(workflow, grant, manifest_digest="0" * 64),
            asyncio.run(aggregator.call_public_brick_tool(
                "auth", "auth.issue_workload_credential", {})),
        ]
        assert len(runtime.workload_credentials._records) == 1
        assert token not in repr(errors)
        binding = {"workflow_run_id": "run", "attempt_id": "attempt",
                   "revision": 0, "manifest_digest": grant.manifest_digest}
        revoked = workflow(
            {"brick_name": "auth", "tool_name": "auth.revoke_workload_credential"},
            arguments={**binding, "credential_id": credential_id},
            idempotency_key=f"revoke:{credential_id}",
            envelope={"run_id": "run", "tenant_id": "tenant"},
            attempt=binding,
        )
        assert revoked["result"]["structured_content"]["data"]["revoked"]
        assert runtime.workload_credentials.verify(token, "companion-x") is None
    finally:
        set_service("workload_grant_policy", previous)
