"""Atomic Memory idempotency claims backed by Storage immutable documents."""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, protected_canonical_json

_COLLECTION = "memory_idempotency"


class MemoryIdempotencyError(RuntimeError):
    """Data-safe durable idempotency outcome."""


def store_once(
    runtime: Any, invoke: Callable[..., Any], *, idempotency_key: str,
    user_id: str, content: str, memory_type: str, category: str,
    metadata: dict[str, Any] | None, ttl_seconds: int | None,
):
    """Store exactly once for ``idempotency_key`` (see ``store_once_with_outcome``)."""
    memory, _ = store_once_with_outcome(
        runtime, invoke, idempotency_key=idempotency_key, user_id=user_id,
        content=content, memory_type=memory_type, category=category,
        metadata=metadata, ttl_seconds=ttl_seconds,
    )
    return memory


def store_once_with_outcome(
    runtime: Any, invoke: Callable[..., Any], *, idempotency_key: str,
    user_id: str, content: str, memory_type: str, category: str,
    metadata: dict[str, Any] | None, ttl_seconds: int | None,
) -> tuple[Any, bool]:
    """Store exactly once, returning ``(memory, replayed)``.

    ``replayed`` is ``True`` when an equal prior write is matched (fresh or
    concurrent), ``False`` when this call performed the durable store.
    """
    request_hash = _digest({
        "user_id": user_id, "content": content,
        "memory_type": memory_type, "category": category,
        "metadata": metadata or {}, "ttl_seconds": ttl_seconds,
    })
    stem = hashlib.sha256(protected_canonical_json({
        "user_id": user_id, "idempotency_key": idempotency_key,
    })).hexdigest()
    claim_id, receipt_id = f"memory-claim-{stem}", f"memory-receipt-{stem}"
    existing = _receipt(invoke, receipt_id)
    if existing is not None:
        return _matched(runtime, existing, request_hash), True
    claim = {
        "request_hash": request_hash, "user_id_hash": _digest(user_id),
        "content_hash": request_hash,
    }
    status = _create(invoke, claim_id, claim, request_hash)
    if status == "conflict":
        raise MemoryIdempotencyError("memory idempotency conflict")
    if status == "matched":
        existing = _receipt(invoke, receipt_id)
        if existing is None:
            raise MemoryIdempotencyError("memory idempotency in progress")
        return _matched(runtime, existing, request_hash), True
    if status != "created":
        raise MemoryIdempotencyError("memory idempotency store unavailable")
    projected = dict(metadata or {})
    projected["idempotency_key"] = idempotency_key
    memory = runtime.store(
        user_id=user_id, content=content, memory_type=memory_type,
        category=category, metadata=projected, ttl_seconds=ttl_seconds,
    )
    receipt_hash = _digest({
        "request_hash": request_hash, "memory_id": memory.id,
    })
    receipt = {
        "request_hash": request_hash, "memory_id": memory.id,
        "content_hash": receipt_hash,
    }
    if _create(invoke, receipt_id, receipt, receipt_hash) not in {
        "created", "matched",
    }:
        raise MemoryIdempotencyError("memory idempotency receipt unavailable")
    return memory, False


def _matched(runtime: Any, receipt: dict[str, Any], request_hash: str):
    if receipt.get("request_hash") != request_hash:
        raise MemoryIdempotencyError("memory idempotency conflict")
    memory_id = receipt.get("memory_id")
    memory = runtime.get(memory_id) if isinstance(memory_id, str) else None
    if memory is None:
        raise MemoryIdempotencyError("memory idempotency receipt missing record")
    return memory


def _create(
    invoke: Callable[..., Any], doc_id: str, data: dict[str, Any], digest: str,
) -> str:
    raw = invoke(
        "storage_doc_create_or_match", collection=_COLLECTION,
        doc_id=doc_id, data=data, content_hash=digest,
    )
    payload = _payload(raw)
    status = payload.get("status") if isinstance(payload, dict) else None
    return status if isinstance(status, str) else "unavailable"


def _receipt(invoke: Callable[..., Any], doc_id: str) -> dict[str, Any] | None:
    raw = invoke("storage_doc_get", collection=_COLLECTION, doc_id=doc_id)
    payload = _payload(raw)
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def _payload(raw: Any) -> Any:
    if isinstance(raw, ToolResult):
        if not raw.ok or raw.data is None:
            return None
        return raw.data.model_dump(mode="json") \
            if hasattr(raw.data, "model_dump") else raw.data
    if not isinstance(raw, dict) or raw.get("ok") is False:
        return None
    return raw.get("data") if raw.get("ok") is True else raw


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        protected_canonical_json(value),
    ).hexdigest()


__all__ = ["MemoryIdempotencyError", "store_once", "store_once_with_outcome"]
