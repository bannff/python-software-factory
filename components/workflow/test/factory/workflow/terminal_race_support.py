"""Shared deterministic coordination for workflow terminal race tests."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from factory.workflow.runtime.runtime import WorkflowRuntime


@dataclass
class InvokeState:
    calls: list = field(default_factory=list)
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event | None = None


class Invoker:
    def __init__(self, state: InvokeState):
        self.state = state

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.state.calls.append((target, arguments, idempotency_key, envelope))
        self.state.started.set()
        if self.state.release is not None:
            assert self.state.release.wait(timeout=10)
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": 1},
        }}


def config_dir(
    tmp_path: Path, *, lease_seconds: int = 30, max_attempts: int = 1,
) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {
            "work": {"brick_name": "demo", "tool_name": "work"},
        }},
    }))
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump({
        "id": "wf", "name": "Workflow", "steps": [{
            "id": "work", "kind": "task", "task_mode": "named_mcp",
            "task_type": "work", "lease_seconds": lease_seconds,
            "max_attempts": max_attempts,
        }],
    }))
    return config


def runtime(config: Path, state: InvokeState) -> WorkflowRuntime:
    return WorkflowRuntime.from_config_dir(config, tool_invoker=Invoker(state))


def run_threads(calls: list[Callable[[], Any]]) -> list[Any]:
    results: list[Any] = [None] * len(calls)
    errors: list[BaseException] = []

    def run(index: int, call: Callable[[], Any]) -> None:
        try:
            results[index] = call()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i, call)) for i, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert errors == []
    return results


def gate_update(runtime: WorkflowRuntime, barrier: threading.Barrier, status: str) -> None:
    original, first = runtime.storage.update_run, True

    def gated(**kwargs):
        nonlocal first
        if first and kwargs["status"] == status:
            first = False
            barrier.wait(timeout=10)
        return original(**kwargs)

    runtime.storage.update_run = gated  # type: ignore[method-assign]


def run_id(runtime: WorkflowRuntime, key: str) -> str:
    assert runtime.durable_storage is not None
    record = runtime.durable_storage.get_run_by_key(run_key=key)
    assert record is not None
    return record.run_id
