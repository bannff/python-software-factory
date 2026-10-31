"""Domain-separated durable workflow identity constructors."""
from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonical_json


def _identity(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(canonical_json(list(parts)).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def workflow_version_id(snapshot: dict[str, Any]) -> str:
    return _identity("wfv:v1", snapshot)


def workflow_run_id(version_id: str, run_key: str, inputs: dict[str, Any]) -> str:
    return _identity("wfr:v1", version_id, run_key, inputs)


def step_execution_id(run_execution_id: str, step_id: str) -> str:
    return _identity("wfs:v1", run_execution_id, step_id)


def task_attempt_id(step_execution: str, attempt_number: int) -> str:
    return _identity("wfa:v1", step_execution, attempt_number)
