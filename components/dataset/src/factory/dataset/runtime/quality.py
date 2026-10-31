"""Quality evaluation for materialized conversation records."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .contracts import DatasetQualityResults

_MAX_MESSAGE_LENGTH = 100_000

_REQUIRED_ROLES = ("user", "assistant")


def _get_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _get_messages(record: Any) -> Any:
    messages = _get_attr(record, "messages")
    return messages or []


def _record_count(records: list[Any]) -> str:
    return f"passed: {len(records)}" if records else "failed: 0 records"


def _schema_check(records: list[Any]) -> str:
    if not records:
        return "passed"
    for record in records:
        messages = _get_messages(record)
        if not messages and _get_attr(record, "messages") is None:
            return "failed: missing messages attribute"
    return "passed"


def _empty_messages(records: list[Any]) -> str:
    empty_count = 0
    for record in records:
        messages = _get_messages(record)
        if not messages:
            empty_count += 1
            continue
        for msg in messages:
            content = _get_attr(msg, "content")
            if content is None or (isinstance(content, str) and content.strip() == ""):
                empty_count += 1
                break
    if empty_count:
        return f"failed: {empty_count} empty messages"
    return "passed"


def _role_coverage(records: list[Any]) -> str:
    if not records:
        return "passed"
    roles_found: set[str] = set()
    for record in records:
        messages = _get_messages(record)
        if not messages:
            continue
        for msg in messages:
            role = _get_attr(msg, "role")
            if role:
                roles_found.add(role)
    missing = [r for r in _REQUIRED_ROLES if r not in roles_found]
    if missing:
        return f"failed: missing roles {missing}"
    return "passed"


def _duplicate_detection(records: list[Any]) -> str:
    seen: dict[str, int] = {}
    for record in records:
        messages = _get_messages(record)
        if not messages:
            continue
        parts = []
        for msg in messages:
            content = _get_attr(msg, "content") or ""
            role = _get_attr(msg, "role") or ""
            parts.append(f"{role}:{content}")
        content_hash = hashlib.sha256("|".join(parts).encode()).hexdigest()
        seen[content_hash] = seen.get(content_hash, 0) + 1
    dupes = sum(v - 1 for v in seen.values() if v > 1)
    if dupes:
        return f"warn: {dupes} duplicates"
    return "passed"


def _max_message_length(records: list[Any]) -> str:
    violations = 0
    for record in records:
        messages = _get_messages(record)
        if not messages:
            continue
        for msg in messages:
            content = _get_attr(msg, "content") or ""
            if isinstance(content, str) and len(content) > _MAX_MESSAGE_LENGTH:
                violations += 1
    if violations:
        return f"failed: {violations} messages exceed {_MAX_MESSAGE_LENGTH} chars"
    return "passed"


def evaluate_quality(
    records: list[Any], *, record_schema: str = "conversation",
    allowed_local_roots: tuple[Path, ...] = (),
) -> DatasetQualityResults:
    """Run schema-specific quality checks; conversation remains the default."""
    if record_schema == "edge_sensor_window":
        from .quality_edge_sensor import evaluate_edge_sensor_quality
        return evaluate_edge_sensor_quality(
            records, allowed_local_roots=allowed_local_roots,
        )
    if record_schema == "edge_routing_example":
        from .quality_edge_routing import evaluate_edge_routing_quality
        return evaluate_edge_routing_quality(records)
    checks: dict[str, str] = {
        "record_count": _record_count(records),
        "schema": _schema_check(records),
        "empty_messages": _empty_messages(records),
        "role_coverage": _role_coverage(records),
        "duplicate_detection": _duplicate_detection(records),
        "max_message_length": _max_message_length(records),
    }
    return DatasetQualityResults(checks=checks)
