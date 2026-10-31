"""Stateless named-MCP task execution through an injected port."""
from __future__ import annotations

import json
from typing import Any

from factory.mcp_utils.interface import (
    is_protected_operation, is_protected_payload, protected_error_text,
    protected_error_value, sanitize_protected,
)

from .canonical import canonical_json, canonical_loads
from .envelope import Envelope
from .models import ToolTarget
from .ports import ToolInvokerPort
from .task_models import TaskExecutionResult, TaskOutcomePolicy
from .task_outcomes import classify_outcome
from .task_refs import build_evidence

_TERMINAL = ("validation", "invalid", "auth", "forbidden", "permission", "notfound", "not found", "configuration", "config")
_TRANSIENT = ("timeout", "timed out", "rate limit", "throttl", "unavailable", "connection", "temporary", "temporarily", "retryable")


def is_retryable_transport(error: Any) -> bool:
    """Retry only explicit transient transport categories or messages."""
    if not isinstance(error, dict):
        return False
    text = f"{error.get('type', '')} {error.get('message', '')}".lower()
    if any(marker in text for marker in _TERMINAL):
        return False
    return any(marker in text for marker in _TRANSIENT)


class NamedMCPTaskExecutor:
    """Execute a frozen structured target with at-least-once semantics.

    The invoker must honor ``idempotency_key``: lease reclaims intentionally
    invoke again with the same deterministic attempt ID.
    """

    @staticmethod
    def _domain_output(result: dict[str, Any]) -> Any:
        if result.get("kind") == "task":
            return result.get("task")
        if result.get("kind") != "tool":
            return result
        structured = result.get("structured_content")
        if structured is not None:
            wrapped = (result.get("meta") or {}).get("fastmcp", {}).get("wrap_result")
            if wrapped and isinstance(structured, dict) and set(structured) == {"result"}:
                return structured["result"]
            return structured
        content = result.get("content") or []
        if len(content) == 1 and content[0].get("type") == "text":
            try:
                return canonical_loads(content[0].get("text", ""))
            except (TypeError, ValueError):
                return {"text": content[0].get("text", "")}
        return {"content": content}

    def __init__(self, invoker: ToolInvokerPort):
        self._invoker = invoker

    @staticmethod
    def _attempt_binding(
        arguments: dict[str, Any], *, required: bool,
    ) -> dict[str, Any] | None:
        if not required:
            return None
        fields = ("workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest", "provider_request_digest")
        if not all(name in arguments for name in fields):
            raise ValueError("service attempt binding fields must be complete")
        return {name: arguments[name] for name in fields}

    def execute(
        self, *, target: ToolTarget, arguments: dict[str, Any],
        attempt_id: str, envelope: Envelope, revision: int = 1,
        outcome_policy: TaskOutcomePolicy | None = None,
        bind_service_attempt: bool = False,
    ) -> TaskExecutionResult:
        protected = is_protected_operation(
            f"{target.brick_name}.{target.tool_name}", arguments,
        )
        canonical_json(arguments)
        attempt = self._attempt_binding(
            arguments, required=bind_service_attempt,
        )
        kwargs = {
            "target": target, "arguments": arguments,
            "idempotency_key": attempt_id,
            "envelope": envelope,
        }
        if attempt is not None:
            kwargs["attempt"] = attempt
        try:
            transport = self._invoker.invoke(**kwargs)
        except (ConnectionError, TimeoutError) as exc:
            error = protected_error_value(
                {"type": type(exc).__name__, "message": str(exc)},
                protected=protected,
            )
            return TaskExecutionResult(
                status="failed", error=json.dumps(
                    error, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ), retryable=True,
            )
        json.dumps(
            transport, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if not isinstance(transport, dict) or not isinstance(transport.get("ok"), bool):
            raise ValueError("malformed tool transport envelope")
        safe_transport = protected_error_value(
            transport, protected=protected or is_protected_payload(transport),
        )
        if transport["ok"] is False:
            raw_error = transport.get("error")
            retryable = is_retryable_transport(raw_error)
            safe_error = protected_error_value(
                raw_error, protected=protected,
            )
            safe_transport = {**transport, "error": safe_error}
            return TaskExecutionResult(
                status="failed", transport_envelope=safe_transport,
                error=json.dumps(
                    safe_error, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ), retryable=retryable,
            )
        native_result = transport.get("result")
        if not isinstance(native_result, dict):
            raise ValueError("successful native result must be an object")
        output = self._domain_output(native_result)
        if isinstance(output, dict) and output.get("schema_version") == "v1":
            if output.get("ok") is not True:
                return TaskExecutionResult(
                    status="failed", output=output, transport_envelope=safe_transport,
                    error=json.dumps(
                        protected_error_value(
                            output.get("error"), protected=protected,
                        ), sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False,
                    ), retryable=False,
                )
            output = output.get("data")
        safe_output = sanitize_protected(output)
        canonical_json(safe_output)
        output = safe_output
        decision = classify_outcome(output, outcome_policy)
        if decision.continued:
            evidence = build_evidence(output, target, attempt_id, safe_transport)
            return TaskExecutionResult(
                status="continued", output=output, transport_envelope=safe_transport,
                evidence=evidence,
            )
        if not decision.succeeded:
            return TaskExecutionResult(
                status="failed", output=output, transport_envelope=safe_transport,
                error=protected_error_text(decision.error, protected=protected),
                retryable=decision.retryable,
            )
        evidence = build_evidence(output, target, attempt_id, safe_transport)
        return TaskExecutionResult(
            status="succeeded", output=output,
            transport_envelope=safe_transport, evidence=evidence,
        )
