"""Schema-v2 structural composition for the six-step CAN lifecycle."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime

_TOOLS = (
    "ml_train_can_portfolio", "evals_record_run", "ml_issue_can_passports",
    "ml_run_can_cold_conformance", "ml_promote_can_passports",
    "ml_project_can_pipeline_result",
)
_EVAL_FIELDS = (
    "experiment_name", "verdict", "pass_rate", "avg_score", "total_cases",
    "passed", "case_results", "evaluators_used", "agent", "timestamp", "source",
    "failed_cases", "duration_ms", "case_scores", "summary", "artifacts",
    "record_kind", "terminal_state", "score_projection",
)


class SequenceInvoker:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        output = self.outputs[len(self.calls) - 1]
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {
                "schema_version": "v1", "ok": True, "data": output,
                "error": None, "idempotency_key": None,
            },
        }}


def _task(step_id, next_id, payload, *, record=False):
    return {
        "id": step_id, "kind": "task", "task_mode": "named_mcp",
        "task_type": step_id, "next": next_id, "task_payload": payload,
        "idempotency_key_argument": "run_id" if record else "attempt_id",
        "task_outcome": {"success": {
            "pointer": "/persisted" if record else "/status",
            "equals": True if record else "completed",
        }},
    }


def _definition():
    train_ref = "workflow-step:///train/output#"
    return {
        "schema_version": "v2", "id": "can", "name": "CAN",
        "result_projection": {"result": {
            "$ref": "workflow-step:///project/output#",
        }},
        "steps": [
            _task("train", "record", {
                "dataset_request": {"$ref": "workflow-run:///input#/dataset_request"},
                "experiment_name": {"$ref": "workflow-run:///input#/experiment_name"},
            }),
            _task("record", "issue", {
                field: {"$ref": f"{train_ref}/evaluation_record_request/{field}"}
                for field in _EVAL_FIELDS
            }, record=True),
            _task("issue", "conform", {
                "training_terminal_ref": {"$ref": f"{train_ref}/terminal_ref"},
                "evaluation_pointers": [{
                    "$ref": "workflow-step:///record/output#/pointer",
                }],
            }),
            _task("conform", "promote", {"passport_refs": {
                "$ref": "workflow-step:///issue/output#/passport_refs",
            }}),
            _task("promote", "project", {"conformance_receipt_refs": {
                "$ref": "workflow-step:///conform/output#/conformance_receipt_refs",
            }}),
            _task("project", None, {
                "training_terminal_ref": {"$ref": f"{train_ref}/terminal_ref"},
                "promotion_terminal_ref": {
                    "$ref": "workflow-step:///promote/output#/terminal_ref",
                },
            }),
        ],
    }


def _runtime(tmp_path: Path, invoker: SequenceInvoker) -> WorkflowRuntime:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    allowlist = {
        name: {"brick_name": "evals" if name == "record" else "machine_learning",
               "tool_name": tool}
        for name, tool in zip(
            ("train", "record", "issue", "conform", "promote", "project"),
            _TOOLS, strict=True,
        )
    }
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": allowlist},
    }))
    (config / "workflows" / "can.yaml").write_text(yaml.safe_dump(_definition()))
    return WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)


def test_can_lifecycle_uses_exact_static_structural_references(tmp_path: Path):
    terminal = {"operation": "train@v1", "digest": "train"}
    promotion = {"operation": "promote@v1", "digest": "promote"}
    evaluation = {field: f"value:{field}" for field in _EVAL_FIELDS}
    pointer, passports, receipts = {"pointer": True}, [{"revision": 1}], [{"receipt": 1}]
    outputs = [
        {"status": "completed", "terminal_ref": terminal,
         "evaluation_record_request": evaluation},
        {"persisted": True, "pointer": pointer},
        {"status": "completed", "passport_refs": passports},
        {"status": "completed", "conformance_receipt_refs": receipts},
        {"status": "completed", "terminal_ref": promotion},
        {"status": "completed", "deployable_model_ids": ["model-1"]},
    ]
    invoker = SequenceInvoker(outputs)
    result = _runtime(tmp_path, invoker).start_run(
        workflow_name_or_id="can",
        input={"dataset_request": {"attempt_id": "dataset"}, "experiment_name": "exp"},
        run_key="composition", envelope=Envelope(),
    )
    assert result["status"] == "succeeded"
    assert [call[0].tool_name for call in invoker.calls] == list(_TOOLS)
    args = [call[1] for call in invoker.calls]
    assert args[0] == {"dataset_request": {"attempt_id": "dataset"},
                       "experiment_name": "exp", "attempt_id": invoker.calls[0][2]}
    assert args[1] == {**evaluation, "run_id": invoker.calls[1][2]}
    assert args[2] == {"training_terminal_ref": terminal,
                       "evaluation_pointers": [pointer],
                       "attempt_id": invoker.calls[2][2]}
    assert args[3] == {"passport_refs": passports, "attempt_id": invoker.calls[3][2]}
    assert args[4] == {"conformance_receipt_refs": receipts,
                       "attempt_id": invoker.calls[4][2]}
    assert args[5] == {"training_terminal_ref": terminal,
                       "promotion_terminal_ref": promotion,
                       "attempt_id": invoker.calls[5][2]}
    assert all(step["task_outcome"] for step in _definition()["steps"])
