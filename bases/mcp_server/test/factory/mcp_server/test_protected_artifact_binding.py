"""Exact protected-artifact binding tests for native service handoffs."""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolResult, ok, operational, service_only
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    artifact: dict[str, object]


class _Output(BaseModel):
    changed: bool


def _artifact() -> dict:
    return {
        "artifact_ref": "pc_v1_abcdefghijklmnopqrstuv",
        "fingerprint": "c" * 64,
        "descriptor": {"purpose": "email"},
    }


def _fixture():
    effects: list[str] = []
    catalog = ToolCatalog("demo")

    @catalog.tool(name="demo_artifact")
    @service_only(callers={"integrations"}, binding="protected_artifact")
    @operational(input_model=_Input, output_model=_Output)
    def artifact(artifact: dict[str, object]) -> ToolResult[_Output]:
        effects.append(str(artifact["artifact_ref"]))
        return ok(_Output(changed=True))

    @catalog.tool(name="demo_public")
    @operational(input_model=_Input, output_model=_Output)
    def public(artifact: dict[str, object]) -> ToolResult[_Output]:
        effects.append("public")
        return ok(_Output(changed=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    return aggregator, effects


def _call(aggregator, tool: str, *, artifact=None, binding=None, enrollment=None):
    return NativeEnvelopeInvoker(aggregator).for_caller("integrations")(
        {"brick_name": "demo", "tool_name": tool},
        arguments={"artifact": artifact or _artifact()}, idempotency_key="idem",
        envelope={}, protected_artifact=binding, enrollment=enrollment,
    )


def _binding() -> dict:
    return {key: _artifact()[key] for key in ("artifact_ref", "fingerprint")}


def test_accepts_exact_nested_binding_without_workflow_run_id() -> None:
    aggregator, effects = _fixture()
    result = _call(aggregator, "artifact", binding=_binding())
    assert result["ok"] is True
    assert effects == [_artifact()["artifact_ref"]]


@pytest.mark.parametrize("binding", [
    None,
    "not-a-mapping",
    {},
    {"artifact_ref": _artifact()["artifact_ref"]},
    {**_binding(), "principal_id": "owner"},
    {**_binding(), "artifact_ref": ""},
    {**_binding(), "fingerprint": "a" * 63},
    {**_binding(), "fingerprint": "A" * 64},
])
def test_rejects_malformed_partial_and_extra_binding(binding) -> None:
    aggregator, effects = _fixture()
    result = _call(aggregator, "artifact", binding=binding)
    assert result["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


def test_rejects_protected_binding_supplied_in_wrong_slot() -> None:
    aggregator, effects = _fixture()
    result = _call(aggregator, "artifact", enrollment=_binding())
    assert result["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


def test_rejects_tamper_mixed_and_public_binding() -> None:
    aggregator, effects = _fixture()
    tampered = _call(
        aggregator, "artifact",
        artifact={**_artifact(), "fingerprint": "d" * 64}, binding=_binding(),
    )
    mixed = _call(
        aggregator, "artifact", binding=_binding(),
        enrollment={"run_key": "x", "manifest_digest": "a" * 64},
    )
    public = _call(aggregator, "public", binding=_binding())
    assert {tampered["error"]["type"], mixed["error"]["type"],
            public["error"]["type"]} == {"ServiceOnlyAccessError"}
    assert effects == []
