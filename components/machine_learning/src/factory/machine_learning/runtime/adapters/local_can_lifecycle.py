"""Descriptor-confined local store for ML CAN lifecycle authority records."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from typing import Iterator

from ..can_lifecycle_canonical import canonical_json
from ..can_lifecycle_contracts import (
    CanEffectIntent, CanEffectReceipt, CanLifecycleAttempt, record_digest,
)
from ..can_lifecycle_refs import CanConformanceReceiptRef, CanTerminalRef
from .local_can_files import PinnedLifecycleDirs
from .local_can_lock import lock_scope
from .local_can_objects import read_regular, write_atomic, write_immutable
from .local_can_validation import decode_attempt, decode_effect, validate_terminal


class LocalCanLifecycleStore:
    """Pin trusted directories and perform every access relative to them."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        self.base = self.root / "can_lifecycle"
        self._dirs = PinnedLifecycleDirs(self.root)

    @contextmanager
    def lock(self, operation: str, attempt_id: str) -> Iterator[None]:
        name = f"{_key(operation, attempt_id)}.lock"
        with lock_scope(self._dirs.fd("locks"), name, authority=True):
            yield

    @contextmanager
    def effect_lock(self, operation: str, effect_id: str) -> Iterator[None]:
        """Per-effect flock that skips the run lock's process-wide authority.

        An authority lock in the issuing thread would deadlock the barrier
        dispatch; a per-effect flock still excludes concurrent publishers and
        readers of one immutable effect.
        """
        name = f"{_key(f'{operation}:effect', effect_id)}.lock"
        with lock_scope(self._dirs.fd("locks"), name, authority=False):
            yield

    def claim(self, operation: str, attempt_id: str, request_sha256: str):
        current = self.load(operation, attempt_id)
        if current is not None:
            state = "matched" if current.request_sha256 == request_sha256 else "conflict"
            return state, current
        record = self._record(operation, attempt_id, request_sha256, "claimed", None, None)
        self._save_record(record)
        return "created", record

    def running(self, record: CanLifecycleAttempt) -> CanLifecycleAttempt:
        updated = self._record(
            record.operation, record.attempt_id, record.request_sha256,
            "running", None, None,
        )
        self._save_record(updated)
        return updated

    def publish(self, record: CanLifecycleAttempt, terminal: dict) -> CanLifecycleAttempt:
        content = canonical_json(terminal)
        digest = hashlib.sha256(content).hexdigest()
        name = f"{digest}.json"
        write_immutable(self._dirs.fd("terminals"), name, content)
        state = "succeeded" if terminal.get("status") == "completed" else "failed"
        updated = self._record(
            record.operation, record.attempt_id, record.request_sha256, state,
            self._dirs.uri("terminals", name), digest,
        )
        self._save_record(updated)
        return updated

    def load(self, operation: str, attempt_id: str) -> CanLifecycleAttempt | None:
        content = self._optional("attempts", self._record_name(operation, attempt_id))
        return decode_attempt(content, operation, attempt_id) if content is not None else None

    def load_terminal(self, record: CanLifecycleAttempt) -> dict:
        if not record.terminal_sha256:
            raise ValueError("attempt has no terminal")
        name = f"{record.terminal_sha256}.json"
        if record.terminal_uri != self._dirs.uri("terminals", name):
            raise ValueError("attempt terminal pointer is invalid")
        content = read_regular(self._dirs.fd("terminals"), name, immutable=True)
        if hashlib.sha256(content).hexdigest() != record.terminal_sha256:
            raise ValueError("attempt terminal digest mismatch")
        value = json.loads(content)
        if canonical_json(value) != content:
            raise ValueError("attempt terminal bytes are not canonical")
        return validate_terminal(value, record)

    def terminal_ref(self, record: CanLifecycleAttempt) -> CanTerminalRef:
        if record.state != "succeeded" or not record.terminal_sha256:
            raise ValueError("only successful lifecycle terminals may be referenced")
        return CanTerminalRef(
            operation=record.operation, attempt_id=record.attempt_id,
            request_sha256=record.request_sha256,
            terminal_sha256=record.terminal_sha256,
        )

    def load_terminal_ref(self, value, expected_operation: str) -> dict:
        ref = CanTerminalRef.model_validate(value)
        if ref.operation != expected_operation:
            raise ValueError("lifecycle terminal reference crosses operations")
        record = self.load(ref.operation, ref.attempt_id)
        if record is None or record.state != "succeeded" or (
            record.request_sha256 != ref.request_sha256
            or record.terminal_sha256 != ref.terminal_sha256
        ):
            raise ValueError("reference is not an exact completed lifecycle terminal")
        return self.load_terminal(record)

    def save_intent(self, intent: CanEffectIntent) -> CanEffectIntent:
        return self._save_effect(intent, "intent", CanEffectIntent)

    def load_intent(self, effect_id: str) -> CanEffectIntent | None:
        return self._load_effect(effect_id, "intent", CanEffectIntent)

    def load_receipt(self, effect_id: str) -> CanEffectReceipt | None:
        return self._load_effect(effect_id, "receipt", CanEffectReceipt)

    def save_receipt(self, receipt: CanEffectReceipt) -> CanEffectReceipt:
        return self._save_effect(receipt, "receipt", CanEffectReceipt)

    def receipt_ref(self, effect_id: str, expected_operation: str):
        intent, receipt = self.load_intent(effect_id), self.load_receipt(effect_id)
        if intent is None or receipt is None or intent.operation != expected_operation:
            raise ValueError("conformance receipt authority is missing")
        return CanConformanceReceiptRef(
            operation=intent.operation, effect_id=effect_id,
            intent_sha256=intent.intent_sha256, receipt_sha256=receipt.receipt_sha256,
        )

    def load_conformance_receipt(self, value, expected_operation: str):
        ref = CanConformanceReceiptRef.model_validate(value)
        if ref.operation != expected_operation:
            raise ValueError("conformance receipt reference crosses operations")
        intent, receipt = self.load_intent(ref.effect_id), self.load_receipt(ref.effect_id)
        if intent is None or receipt is None or (
            intent.operation != ref.operation or intent.intent_sha256 != ref.intent_sha256
            or receipt.intent_sha256 != ref.intent_sha256
            or receipt.receipt_sha256 != ref.receipt_sha256
        ):
            raise ValueError("conformance receipt reference is stale or tampered")
        return intent, receipt

    def _save_effect(self, value, kind, model):
        name = f"{value.effect_id}.{kind}.json"
        content = canonical_json(value.model_dump(mode="json"))
        write_immutable(self._dirs.fd("effects"), name, content)
        stored = read_regular(self._dirs.fd("effects"), name, immutable=True)
        return decode_effect(model, stored, value.effect_id)

    def _load_effect(self, effect_id, kind, model):
        content = self._optional("effects", f"{effect_id}.{kind}.json", immutable=True)
        return decode_effect(model, content, effect_id) if content is not None else None

    def _optional(self, directory, name, immutable=False):
        try:
            return read_regular(self._dirs.fd(directory), name, immutable=immutable)
        except FileNotFoundError:
            return None

    def _save_record(self, record: CanLifecycleAttempt) -> None:
        write_atomic(
            self._dirs.fd("attempts"), self._record_name(record.operation, record.attempt_id),
            canonical_json(record.model_dump(mode="json")),
        )

    def _record(self, operation, attempt_id, request_sha, state, uri, digest):
        values = {
            "schema_version": "1.0", "operation": operation,
            "attempt_id": attempt_id, "request_sha256": request_sha,
            "state": state, "terminal_uri": uri, "terminal_sha256": digest,
        }
        values["record_sha256"] = record_digest(values)
        return CanLifecycleAttempt.model_validate(values)

    @staticmethod
    def _record_name(operation: str, attempt_id: str) -> str:
        return f"{_key(operation, attempt_id)}.json"


def _key(operation: str, attempt_id: str) -> str:
    return hashlib.sha256(f"{operation}\0{attempt_id}".encode()).hexdigest()


__all__ = ["LocalCanLifecycleStore"]
