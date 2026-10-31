"""Create-or-match coordinator for versioned ML training lifecycle terminals.

Family-polymorphic per epic #124 S1: terminal-event names come from the
``lifecycle_family`` spec registry (``resolve_family``), never from
domain-conditioned strings in this module.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from .can_lifecycle_canonical import effect_identity, semantic_request
from .can_lifecycle_contracts import CanEffectIntent, CanEffectReceipt, with_digest
from .can_lifecycle_ports import CanLifecycleStore
from .emit import emit_ml_event
from .lifecycle_family import resolve_family

_RESERVED_RESULT_KEYS = frozenset({
    "schema_version", "operation", "status", "attempt_id", "request_sha256",
    "existing_request_sha256", "error", "terminal_ref",
})
Runner = Callable[["TrainingLifecycleContext"], dict[str, Any]]


class TrainingLifecycleContext:
    def __init__(self, operation: str, request_sha256: str, store: CanLifecycleStore):
        self.operation, self.request_sha256, self.store = operation, request_sha256, store

    def effect(self, unit, inputs, reconcile, execute) -> dict[str, Any]:
        effect_id = effect_identity(self.operation, self.request_sha256, unit)
        with self.store.lock(f"{self.operation}:effect", effect_id):
            intent = with_digest(
                CanEffectIntent, schema_version="1.0", operation=self.operation,
                effect_id=effect_id, request_sha256=self.request_sha256,
                unit=unit, inputs=inputs, intent_sha256="",
            )
            stored = self.store.save_intent(intent)
            receipt = self.store.load_receipt(effect_id)
            if receipt is not None:
                if receipt.intent_sha256 != stored.intent_sha256:
                    raise ValueError("effect receipt is bound to a different intent")
                return receipt.output
            output = reconcile(effect_id)
            if output is None:
                output = execute(effect_id)
            receipt = with_digest(
                CanEffectReceipt, schema_version="1.0", effect_id=effect_id,
                intent_sha256=stored.intent_sha256, output=output, receipt_sha256="",
            )
            return self.store.save_receipt(receipt).output

    def effect_with_ref(self, unit, inputs, reconcile, execute):
        output = self.effect(unit, inputs, reconcile, execute)
        effect_id = effect_identity(self.operation, self.request_sha256, unit)
        return output, self.store.receipt_ref(effect_id, self.operation)

    def completed_terminal(self, value, expected_operation: str) -> dict[str, Any]:
        return self.store.load_terminal_ref(value, expected_operation)

    def conformance_receipt(self, value, expected_operation: str):
        return self.store.load_conformance_receipt(value, expected_operation)


class TrainingLifecycleCoordinator:
    def __init__(
        self, store: CanLifecycleStore, family: str | None = None,
    ) -> None:
        """``family`` is the trinary override: None defers to the versioned
        operation string via the registry; explicit ids never defer."""
        self.store, self.family = store, family

    def run(
        self, operation, request, tool_identities, runner: Runner,
        result_model: type[BaseModel],
    ) -> dict[str, Any]:
        events = resolve_family(self.family, operation)
        attempt_id = str(request.get("attempt_id", ""))
        _, request_sha = semantic_request(operation, request, tool_identities)
        with self.store.lock(operation, attempt_id):
            resolution, record = self.store.claim(operation, attempt_id, request_sha)
            if resolution == "conflict":
                return {
                    "schema_version": "1.0", "operation": operation,
                    "status": "conflict", "attempt_id": attempt_id,
                    "request_sha256": request_sha,
                    "existing_request_sha256": record.request_sha256,
                    "error": "attempt key is already bound to a different request",
                }
            if record.state in {"succeeded", "failed"}:
                terminal = self.store.load_terminal(record)
                self._verify(terminal, operation, attempt_id, request_sha, result_model)
                return self._with_ref(terminal, record)
            record = self.store.running(record)
            emit_ml_event(events.started_event, {
                "operation": operation, "attempt_id": attempt_id,
                "request_sha256": request_sha, "status": "started",
            })
            try:
                result = runner(TrainingLifecycleContext(operation, request_sha, self.store))
                if not isinstance(result, dict):
                    raise TypeError("lifecycle runner result must be a mapping")
                reserved = sorted(_RESERVED_RESULT_KEYS.intersection(result))
                if reserved:
                    raise ValueError(
                        f"lifecycle runner result uses reserved envelope keys: {reserved}"
                    )
                result = result_model.model_validate(result).model_dump(
                    mode="json", exclude_none=True, by_alias=True,
                )
                terminal = {
                    "schema_version": "1.0", "operation": operation,
                    "status": "completed", "attempt_id": attempt_id,
                    "request_sha256": request_sha, **result,
                }
            except Exception as exc:
                terminal = {
                    "schema_version": "1.0", "operation": operation,
                    "status": "failed", "attempt_id": attempt_id,
                    "request_sha256": request_sha, "error": str(exc),
                }
            published = self.store.publish(record, terminal)
            canonical = self.store.load_terminal(published)
            self._verify(canonical, operation, attempt_id, request_sha, result_model)
            emit_ml_event(events.terminal_event(terminal["status"]), {
                "operation": operation, "attempt_id": attempt_id,
                "request_sha256": request_sha, "status": terminal["status"],
                **({"error": terminal["error"]} if "error" in terminal else {}),
            })
            return self._with_ref(canonical, published)

    def _with_ref(self, terminal, record):
        if terminal.get("status") != "completed":
            return terminal
        return {**terminal, "terminal_ref": self.store.terminal_ref(record).model_dump(mode="json")}

    @staticmethod
    def _verify(terminal, operation, attempt_id, request_sha, result_model):
        if (
            terminal.get("operation") != operation
            or terminal.get("attempt_id") != attempt_id
            or terminal.get("request_sha256") != request_sha
            or terminal.get("status") not in {"completed", "failed"}
        ):
            raise ValueError("lifecycle terminal identity mismatch")
        if terminal["status"] == "completed":
            payload = {
                key: value for key, value in terminal.items()
                if key not in _RESERVED_RESULT_KEYS
            }
            result_model.model_validate(payload)


#: API-stability aliases for the S1 rename — call sites migrate to the
#: Training* names over the epic; the CAN-prefixed names stay valid.
CanLifecycleContext = TrainingLifecycleContext
CanLifecycleCoordinator = TrainingLifecycleCoordinator

__all__ = [
    "CanLifecycleContext", "CanLifecycleCoordinator",
    "TrainingLifecycleContext", "TrainingLifecycleCoordinator",
]
