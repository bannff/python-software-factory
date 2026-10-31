"""Contracts for canonical IDs, bindings, refs, and named MCP envelopes."""
from __future__ import annotations

import math

import pytest

from factory.workflow.runtime.canonical import canonical_json, canonical_loads
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import StepDefinition, ToolTarget, WorkflowDefinition
from factory.workflow.runtime.task_bindings import bind_named_targets
from factory.workflow.runtime.task_executor import NamedMCPTaskExecutor
from factory.workflow.runtime.task_ids import (
    step_execution_id, task_attempt_id, workflow_run_id, workflow_version_id,
)
from factory.workflow.runtime.task_refs import resolve_refs, verify_artifacts

TARGET = ToolTarget(brick_name="machine_learning", tool_name="ml_train")


class Invoker:
    def __init__(self, transport):
        self.transport = transport
        self.calls = []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        return self.transport


def _execute(transport):
    return NamedMCPTaskExecutor(Invoker(transport)).execute(
        target=TARGET, arguments={}, attempt_id="wfa:v1:" + "0" * 64,
        envelope=Envelope(tenant_id="tenant", principal_id="principal"),
    )


def test_canonical_json_is_strict_sorted_unicode() -> None:
    assert canonical_json({"z": 1, "é": [2]}) == '{"z":1,"é":[2]}'
    assert canonical_loads('{"z":1,"é":[2]}') == {"z": 1, "é": [2]}
    with pytest.raises(ValueError):
        canonical_json({"bad": math.nan})
    with pytest.raises(ValueError):
        canonical_loads('{"bad":NaN}')


def test_all_identity_families_use_full_sha256() -> None:
    version = workflow_version_id({"id": "wf", "steps": [{"id": "s"}]})
    run = workflow_run_id(version, "run-key", {"x": 1})
    step = step_execution_id(run, "s")
    attempt = task_attempt_id(step, 1)
    for value, prefix in ((version, "wfv:v1:"), (run, "wfr:v1:"),
                          (step, "wfs:v1:"), (attempt, "wfa:v1:")):
        assert value.startswith(prefix)
        assert len(value.removeprefix(prefix)) == 64
    assert attempt == task_attempt_id(step, 1)


def test_named_binding_is_structured_and_frozen() -> None:
    workflow = WorkflowDefinition(
        id="wf", name="WF", steps=[StepDefinition(
            id="task", kind="task", task_mode="named_mcp", task_type="train",
        )],
    )
    bound = bind_named_targets(workflow, {"train": TARGET})
    assert bound.steps[0].tool_target == TARGET
    assert workflow.steps[0].tool_target is None
    with pytest.raises(ValueError, match="disallowed"):
        bind_named_targets(workflow, {})


def test_structural_ref_is_exact_and_resolves_json_pointer() -> None:
    output = {"artifacts": {"model": {"uri": "file:///model"}}}
    ref = {"$ref": "workflow-step:///prepare/output#/artifacts/model/uri"}
    assert resolve_refs(ref, lambda _: output) == "file:///model"
    for invalid in ({"$ref": "prepare.output.uri"},
                    {"$ref": "workflow-step:///prepare/output#/missing"},
                    {"$ref": ref["$ref"], "fallback": "x"}):
        with pytest.raises(ValueError):
            resolve_refs(invalid, lambda _: output)


def test_artifact_digest_is_a_declaration_not_byte_verification() -> None:
    digest = "a" * 64
    output = {"artifacts": {"model": {
        "uri": "file:///model", "sha256": digest,
        "evidence": {"verified": True, "sha256": digest},
    }}}
    recorded = verify_artifacts(output)["artifacts"]["model"]
    assert recorded == {"declared_sha256": digest}
    output["artifacts"]["model"]["evidence"]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="mismatch"):
        verify_artifacts(output)


def test_retry_classification_is_explicit() -> None:
    transient = _execute({
        "ok": False, "error": {"type": "TimeoutError", "message": "timed out"},
    })
    permanent = _execute({
        "ok": False, "error": {"type": "ValidationError", "message": "invalid input"},
    })
    missing = _execute({
        "ok": False, "error": {"type": "ToolNotFoundError", "message": "not found"},
    })
    assert transient.retryable is True
    assert permanent.retryable is False
    assert missing.retryable is False



def test_unmarked_sensitive_persistence_is_rejected() -> None:
    for key in ("body", "subject", "to", "html", "query", "provider_response"):
        with pytest.raises(ValueError, match="protected inline content"):
            canonical_json({key: "unmarked-canary@example.test"})


def test_transport_error_aliases_are_sanitized() -> None:
    result = _execute({"ok": False, "error": {
        "type": "TimeoutError", "message": "to=recipient@example.test html=<b>secret</b>",
    }})
    assert "recipient@example.test" not in (result.error or "")
    assert "secret" not in (result.error or "")

    domain = _execute({"ok": True, "result": {
        "kind": "tool", "content": [], "structured_content": {"error": "domain"},
        "meta": {},
    }})
    scalar = _execute({"ok": True, "result": {
        "kind": "tool", "content": [], "structured_content": {"result": [1, 2]},
        "meta": {"fastmcp": {"wrap_result": True}},
    }})
    assert domain.output == {"error": "domain"}
    assert scalar.output == [1, 2]


def test_malformed_envelope_fails_loudly() -> None:
    with pytest.raises(ValueError, match="malformed"):
        _execute({"result": {}})


def test_ordinary_overlapping_argument_names_do_not_mint_service_binding() -> None:
    transport = {"ok": True, "result": {
        "kind": "tool", "content": [], "structured_content": {"value": 1},
        "meta": {},
    }}
    invoker = Invoker(transport)
    arguments = {
        "workflow_run_id": "domain-run", "attempt_id": "domain-attempt",
        "revision": 7, "manifest_digest": "f" * 64,
    }
    result = NamedMCPTaskExecutor(invoker).execute(
        target=TARGET, arguments=arguments,
        attempt_id="wfa:v1:" + "1" * 64, envelope=Envelope(),
    )
    assert result.status == "succeeded"
    assert invoker.calls[0][1] == arguments


def test_protected_attempt_binding_requires_all_four_fields() -> None:
    with pytest.raises(ValueError, match="complete"):
        NamedMCPTaskExecutor(Invoker({})).execute(
            target=TARGET, arguments={"attempt_id": "partial"},
            attempt_id="wfa:v1:" + "2" * 64, envelope=Envelope(),
            bind_service_attempt=True,
        )


def test_protected_transport_classification_uses_original_error_in_memory() -> None:
    canary = "retry-body-canary@example.test"
    result = NamedMCPTaskExecutor(Invoker({
        "ok": False,
        "error": {"type": "TimeoutError", "message": f"body={canary}"},
    })).execute(
        target=ToolTarget(
            brick_name="integrations", tool_name="communications.send_email",
        ),
        arguments={"artifact_ref": "opaque"},
        attempt_id="wfa:v1:" + "3" * 64,
        envelope=Envelope(),
    )
    assert result.retryable is True
    assert canary not in (result.error or "")
    assert "protected-operation-failed" in (result.error or "")
