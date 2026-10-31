"""Workflow runtime composition and public operation delegates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .envelope import Envelope
from .execution.adapters import TaskExecutor
from .execution_engines import ExecutionEngineRegistry
from .execution.runner import Runner
from .executor_composition import create_configured_executor
from .execution_runtime import ExecutionRuntime
from .background_runtime import BackgroundCompletionRuntime
from .loop_runtime import LoopRuntime
from .models import Settings, ToolTarget, WorkflowDefinition
from .operations import WorkflowError, WorkflowOperations
from .ports import DurableWorkflowStorage, ToolInvokerPort, WorkflowStorage
from .storage.sqlite import SqliteWorkflowStorage
from .task_executor import NamedMCPTaskExecutor
from .task_invoker_service import resolve_tool_invoker

def _ensure_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise WorkflowError("Path escapes config root") from exc


def _targets(value: dict[str, Any]) -> dict[str, ToolTarget]:
    return {alias: ToolTarget.model_validate(target) for alias, target in value.items()}


@dataclass
class RuntimeFlags:
    authoring_enabled: bool = False
    running_mode: str = "stdio"


class WorkflowRuntime(LoopRuntime, BackgroundCompletionRuntime, ExecutionRuntime):
    def __init__(
        self, *, config_dir: Path, settings: Settings, settings_raw: dict[str, Any],
        workflows: list[WorkflowDefinition], storage: WorkflowStorage,
        executor: TaskExecutor, tool_invoker: ToolInvokerPort | None = None,
        task_allowlist: dict[str, Any] | None = None,
        execution_engines: ExecutionEngineRegistry | None = None,
    ):
        self.config_dir = config_dir
        self.settings = settings
        self.settings_raw = settings_raw
        self._workflows = workflows
        self._workflow_by_id = {workflow.id: workflow for workflow in workflows}
        self._workflow_by_name = {workflow.name.lower(): workflow for workflow in workflows}
        self.storage = storage
        self.executor = executor
        self.durable_storage = (
            storage if isinstance(storage, DurableWorkflowStorage) else None
        )
        allowlist = _targets(task_allowlist) if task_allowlist is not None \
            else settings.durable_tasks.allowlist
        self.execution_engines = execution_engines or ExecutionEngineRegistry(
            settings.execution_engines.engines
        )
        self.named_executor = NamedMCPTaskExecutor(tool_invoker) if tool_invoker else None
        self.runner = Runner(
            storage=storage, workflows=self._workflow_by_id, executor=executor,
            durable_storage=self.durable_storage, named_executor=self.named_executor,
        )
        self.flags = RuntimeFlags()
        self._ops = WorkflowOperations(
            storage, self.runner, self._workflow_by_id, self._workflow_by_name,
            self.durable_storage, allowlist, tool_invoker,
        )

    @classmethod
    def from_config_dir(
        cls, config_dir: Path, *, tool_invoker: ToolInvokerPort | None = None,
        task_allowlist: dict[str, Any] | None = None,
    ) -> "WorkflowRuntime":
        config_dir = config_dir.resolve()
        settings_path = config_dir / "settings.yaml"
        if not settings_path.exists():
            raise WorkflowError("Missing settings.yaml in config_dir")
        raw = yaml.safe_load(settings_path.read_text())
        if not isinstance(raw, dict):
            raise WorkflowError("settings.yaml must parse to a mapping")
        settings = Settings.model_validate(raw)
        return cls(
            config_dir=config_dir, settings=settings, settings_raw=raw,
            workflows=cls._load_workflows(config_dir),
            storage=cls._create_storage(config_dir, settings),
            executor=create_configured_executor(settings),
            tool_invoker=tool_invoker or resolve_tool_invoker(),
            task_allowlist=task_allowlist,
        )

    @staticmethod
    def _load_workflows(config_dir: Path) -> list[WorkflowDefinition]:
        definitions = []
        workflows_dir = config_dir / "workflows"
        if workflows_dir.exists():
            for path in sorted(workflows_dir.glob("*.yaml")):
                parsed = yaml.safe_load(path.read_text())
                if not isinstance(parsed, dict):
                    raise WorkflowError(f"Workflow file must parse to a mapping: {path}")
                definitions.append(WorkflowDefinition.model_validate(parsed))
        return definitions

    @staticmethod
    def _create_storage(config_dir: Path, settings: Settings) -> WorkflowStorage:
        if settings.storage.backend == "aws":
            from .storage.aws import AWSWorkflowStorage
            config = settings.storage.aws
            return AWSWorkflowStorage(
                state_machine_arn=config.state_machine_arn,
                table_name=config.table_name, region=config.region,
            )
        path = (config_dir / settings.storage.sqlite.filename).resolve()
        _ensure_within_root(config_dir, path)
        storage = SqliteWorkflowStorage(path)
        storage.init_schema()
        return storage

    def set_runtime_flags(self, *, authoring_enabled: bool, running_mode: str) -> None:
        self.flags = RuntimeFlags(authoring_enabled, running_mode)

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "schema_versions": {"settings": ["v1"],
                                "workflow_definition": ["v1", "v2"],
                                "tool_contract": 1},
            "supported_storage_backends": ["sqlite", "aws"],
            "supported_executor_backends": ["local", "celery", "dagster"],
            "current_executor": self.executor.backend_name,
            "authoring_enabled": self.flags.authoring_enabled,
            "running_mode": self.flags.running_mode,
            "feature_flags": {
                "step_kinds": ["noop", "wait_for_event", "task"],
                "task_modes": ["executor", "named_mcp"],
                "durable_named_mcp_execution": "sqlite-only",
                "named_mcp_at_least_once": True,
                "projected_named_mcp_inputs": True,
                "declarative_task_outcomes": True,
                "durable_terminal_projection": True,
                "durable_goal_monitor_loops": hasattr(self.storage, "create_loop"),
                "inhouse_execution_engines": self.execution_engines.capabilities(),
            },
        }

    def health_check(self) -> dict[str, Any]:
        storage, executor = self.storage.health_check(), self.executor.health_check()
        named = (
            any(workflow.has_named_mcp() for workflow in self._workflows)
            or bool(self.execution_engines.capabilities())
        )
        durable_ready = not named or (
            self.durable_storage is not None and self.named_executor is not None
        )
        ok = bool(storage.get("ok") and executor.get("ok") and durable_ready)
        error = storage.get("error") or executor.get("error")
        if not durable_ready:
            error = "named MCP requires SQLite durable storage and a tool invoker"
        return {"status": "ok" if ok else "degraded", "storage": storage,
                "executor": executor, "durable_named_mcp_ready": durable_ready,
                "last_error": error}

    def describe_config_schema(self) -> dict[str, Any]:
        return {"settings_schema": Settings.model_json_schema(),
                "workflow_definition_schema": WorkflowDefinition.model_json_schema()}

    def get_workflow_registry(self) -> list[dict[str, Any]]:
        return [{"id": workflow.id, "name": workflow.name, "version": workflow.version,
                 "tags": list(workflow.tags), "schema_version": workflow.schema_version}
                for workflow in self._workflows]

    def start_run(self, *, workflow_name_or_id: str, input: dict[str, Any],
                  envelope: Envelope, run_key: str | None = None) -> dict[str, Any]:
        return self._ops.start_run(
            workflow_name_or_id=workflow_name_or_id, input=input,
            envelope=envelope, run_key=run_key,
        )

    def get_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        return self._ops.get_run(run_id=run_id, envelope=envelope)

    def list_runs(self, *, filter: dict[str, Any], pagination: dict[str, Any],
                  envelope: Envelope) -> dict[str, Any]:
        return self._ops.list_runs(filter=filter, pagination=pagination, envelope=envelope)

    def step_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        return self._ops.step_run(run_id=run_id, envelope=envelope)

    def emit_event(self, *, run_id: str, event_type: str,
                   payload: dict[str, Any], envelope: Envelope) -> dict[str, Any]:
        return self._ops.emit_event(
            run_id=run_id, event_type=event_type, payload=payload, envelope=envelope,
        )
