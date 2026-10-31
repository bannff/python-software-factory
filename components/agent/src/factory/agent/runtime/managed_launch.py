"""Prepare, store, and enroll one Workflow-managed Agent graph."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from factory.mcp_utils.interface import get_envelope, get_service, normalize_envelope

from .execution_manifest.artifacts import store_manifest
from .execution_manifest.dataset_port import NamedDatasetMCPPort
from .execution_manifest.prepare import prepare_execution_manifest


class ManagedLaunchResult(BaseModel):
    """Strict local projection of Workflow's managed enrollment result."""

    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str
    run_key: str
    status: str
    attempt_id: str | None
    attempt_revision: int | None = Field(ge=0)
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine_id: str
    registration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: Literal["managed"]
    started_at: str
    result: dict[str, Any] | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _validate_attempt_binding(self) -> "ManagedLaunchResult":
        missing_attempt = self.attempt_id is None
        if missing_attempt != (self.attempt_revision is None):
            raise ValueError("managed launch attempt identity must be provided together")
        if missing_attempt and self.status not in {"failed", "cancelled"}:
            raise ValueError("only terminal failed or cancelled runs may lack an attempt")
        return self


def run_key_from_tool_context(tool_context: Any, tool_name: str) -> str:
    """Derive replay identity from trusted tool and envelope context."""
    current = get_envelope() or {}
    agent = getattr(tool_context, "agent", None)
    tool_use = getattr(tool_context, "tool_use", None) or {}
    identity = {
        "version": "v1", "tool": tool_name,
        "tenant_id": str(current.get("tenant_id") or "").strip(),
        "principal_id": str(current.get("principal_id") or "").strip(),
        "session_id": str(current.get("session_id") or "").strip(),
        "agent_id": str(getattr(agent, "agent_id", None) or "").strip(),
        "toolUseId": str(tool_use.get("toolUseId") or "").strip(),
    }
    missing = [key for key in ("session_id", "agent_id", "toolUseId") if not identity[key]]
    if missing:
        raise ValueError(f"missing replay identity context: {', '.join(missing)}")
    raw = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"managed-graph:v1:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def new_run_key(graph_id: str, *, requested: str | None = None) -> str:
    """Return a caller-provided replay key or a fresh launch identity."""
    if isinstance(requested, str) and requested.strip():
        return requested.strip()
    return f"managed-graph:{graph_id}:{uuid.uuid4().hex}"


async def _invoke(
    invoker: Any, target: dict[str, str], **kwargs: Any,
) -> Any:
    """Keep synchronous native gateways off the launcher's event loop."""
    value = await asyncio.to_thread(invoker, target, **kwargs)
    return await value if inspect.isawaitable(value) else value


def _unwrap_enrollment(value: Any) -> ManagedLaunchResult:
    if not isinstance(value, dict) or value.get("ok") is not True:
        raise RuntimeError("workflow enrollment transport failure")
    native = value.get("result")
    if not isinstance(native, dict) or native.get("kind") != "tool":
        raise RuntimeError("workflow.enroll_execution returned malformed native transport")
    inner = native.get("structured_content")
    if not isinstance(inner, dict) or inner.get("schema_version") != "v1":
        raise RuntimeError("workflow.enroll_execution returned malformed ToolResult")
    if inner.get("ok") is not True:
        raise RuntimeError(
            f"workflow.enroll_execution failed: {inner.get('error')}"
        )
    data = inner.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("workflow enrollment returned no result data")
    return ManagedLaunchResult.model_validate(data)


async def launch_managed_graph(
    config: Any, task: str, context: dict[str, Any], *, run_key: str,
    origin_kind: Literal["registered", "dynamic"],
    invocation_state: dict[str, Any] | None = None,
    envelope: dict[str, Any] | None = None,
    execute: bool = True,
    launch_metadata: dict[str, str] | None = None,
) -> ManagedLaunchResult:
    """Freeze mutable Agent inputs and enroll the exact Workflow target."""
    factory = get_service("tool_invoker_for_caller")
    if not callable(factory):
        raise RuntimeError("tool_invoker_for_caller service is unavailable")
    invoke = factory("agent")
    if not callable(invoke):
        raise RuntimeError("agent caller-bound tool invoker is unavailable")
    trusted_envelope = normalize_envelope(envelope or get_envelope())
    manifest = prepare_execution_manifest(
        config, task, context, invocation_state=invocation_state,
        origin_kind=origin_kind,
    )
    if manifest.digest is None:
        raise RuntimeError("prepared execution manifest is unsealed")
    digest = manifest.digest.value

    async def dataset_invoke(tool_name: str, arguments: dict[str, Any]) -> Any:
        return await _invoke(
            invoke, {"brick_name": "dataset", "tool_name": tool_name},
            arguments=arguments,
            idempotency_key=f"{run_key}:dataset:{tool_name}:{digest}",
            envelope=trusted_envelope,
        )

    descriptor = await store_manifest(
        manifest, NamedDatasetMCPPort(dataset_invoke),
    )
    response = await _invoke(
        invoke, {"brick_name": "workflow", "tool_name": "enroll_execution"},
        arguments={
            "engine_id": "langgraph",
            "request": descriptor.model_dump(mode="json"),
            "provider_request_digest": digest,
            "manifest_digest": digest,
            "run_key": run_key,
            "launch_metadata": launch_metadata or {},
            "execute": execute,
            "envelope": trusted_envelope,
        },
        idempotency_key=run_key,
        envelope=trusted_envelope,
        enrollment={"run_key": run_key, "manifest_digest": digest},
    )
    result = _unwrap_enrollment(response)
    if result.run_key != run_key or result.manifest_digest != digest:
        raise RuntimeError("Workflow enrollment did not bind the requested manifest")
    return result


__all__ = [
    "ManagedLaunchResult", "launch_managed_graph", "new_run_key",
    "run_key_from_tool_context",
]
