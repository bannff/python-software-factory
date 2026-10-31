"""Availability-aware source readers for the ML Observatory."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, get_service

from .learning_projection import _load_learning_runs

SourceEnvelope = dict[str, Any]
RuntimeSupplier = Callable[[], Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _envelope(
    name: str, value: Any, *, health: str = "healthy",
    durability: str, error: str | None = None,
) -> SourceEnvelope:
    return {
        "name": name, "health": health, "durability": durability,
        "freshness": _now(), "value": value, "error": error,
    }


def _valid_receipt(value: Any) -> bool:
    return (
        isinstance(value, dict) and bool(value.get("run_id"))
        and bool(value.get("model_type"))
        and isinstance(value.get("metrics"), dict)
    )


def load_training_receipts() -> SourceEnvelope:
    """Read raw durable receipts without collapsing unavailable into empty."""
    try:
        invoker = get_service("tool_invoker")
    except Exception as exc:
        return _envelope("training_receipts", None, health="error", durability="durable", error=str(exc))
    if invoker is None:
        return _envelope("training_receipts", None, health="error", durability="durable", error="tool_invoker unavailable")
    try:
        result = invoker(
            "storage_doc_find", collection="ml_training_runs", query={}, limit=500,
        )
    except Exception as exc:
        return _envelope("training_receipts", None, health="error", durability="durable", error=str(exc))
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            return _envelope("training_receipts", None, health="error", durability="durable", error="malformed storage_doc_find result")
        documents = getattr(result.data, "documents", None)
        if not isinstance(documents, list):
            return _envelope("training_receipts", None, health="error", durability="durable", error="malformed storage_doc_find result")
        records = [document.data for document in documents]
    else:
        if not isinstance(result, dict) or result.get("ok") is False or result.get("error"):
            return _envelope("training_receipts", None, health="error", durability="durable", error="malformed storage_doc_find result")
        payload = result.get("data") if result.get("ok") is True else result
        if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
            return _envelope("training_receipts", None, health="error", durability="durable", error="malformed storage_doc_find result")
        records = [document.get("data", document) if isinstance(document, dict) else None for document in payload["documents"]]
    receipts: list[dict[str, Any]] = []
    skipped = 0
    for record in records:
        if _valid_receipt(record):
            receipts.append(dict(record))
        else:
            skipped += 1
    error = f"skipped {skipped} malformed record(s)" if skipped else None
    return _envelope(
        "training_receipts", receipts,
        health="degraded" if skipped else "healthy",
        durability="durable", error=error,
    )


def load_learning_runs() -> SourceEnvelope:
    """Preflight the invoker before the legacy healthy-empty projection."""
    try:
        if get_service("tool_invoker") is None:
            raise RuntimeError("tool_invoker unavailable")
        value = _load_learning_runs(limit=500)
        if not isinstance(value, list):
            raise TypeError("learning projection returned a non-list")
        return _envelope("learning_runs", value, durability="event_backed")
    except Exception as exc:
        return _envelope("learning_runs", None, health="error", durability="event_backed", error=str(exc))


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _serialize_job(job: Any) -> dict[str, Any]:
    metrics = getattr(job, "metrics", {}) or {}
    return {
        "id": getattr(job, "id", ""),
        "status": _enum_value(getattr(job, "status", "")),
        "method": _enum_value(getattr(job, "method", "")),
        "base_model": getattr(job, "base_model", ""),
        "training_objective": _enum_value(getattr(job, "training_objective", None)),
        "loss": metrics.get("loss"),
        "checkpoints": len(getattr(job, "checkpoints", []) or []),
        "error": getattr(job, "error", None),
    }


def load_fine_tuning_jobs(runtime_supplier: RuntimeSupplier) -> SourceEnvelope:
    """List fine-tuning jobs inside an independent exception boundary."""
    try:
        jobs = runtime_supplier().get_finetuner().list_jobs()
        return _envelope("fine_tuning_jobs", [_serialize_job(job) for job in jobs], durability="runtime")
    except Exception as exc:
        return _envelope("fine_tuning_jobs", None, health="error", durability="runtime", error=str(exc))


def collect_sources(runtime_supplier: RuntimeSupplier) -> list[SourceEnvelope]:
    """Collect all Release-1 Observatory sources in stable order."""
    return [
        load_training_receipts(), load_learning_runs(),
        load_fine_tuning_jobs(runtime_supplier),
        _envelope(
            "live_models", None, health="degraded", durability="runtime",
            error="public live-model enumeration unavailable",
        ),
    ]


__all__ = ["SourceEnvelope", "collect_sources", "load_learning_runs", "load_training_receipts"]
