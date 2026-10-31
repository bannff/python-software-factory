"""Canonical record validation for generation stage boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Literal

from .edge_routing_contracts import EdgeRoutingExample
from .edge_sensor_contracts import EdgeSensorWindowRecord
from .records import ConversationRecord


def validate_conversation_records(records: Iterable[Any]) -> Iterator[Any]:
    """Validate and yield canonical ConversationRecord values lazily."""
    for index, record in enumerate(records):
        try:
            yield ConversationRecord.model_validate(record)
        except Exception as error:
            raise ValueError(f"Invalid conversation record at index {index}") from error


def validate_can_frame_records(records: Iterable[Any]) -> Iterator[Any]:
    """Validate CAN frame records (pass-through with basic shape check)."""
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"CAN frame record at index {index} must be a dict, got {type(record).__name__}"
            )
        yield record


def validate_generic_records(records: Iterable[Any]) -> Iterator[Any]:
    """Pass-through validator — length check only, no schema enforcement."""
    yield from records


def validate_edge_sensor_window_records(records: Iterable[Any]) -> Iterator[EdgeSensorWindowRecord]:
    """Validate and yield strict versioned edge sensor-window records."""
    for index, record in enumerate(records):
        try:
            yield EdgeSensorWindowRecord.model_validate(record)
        except Exception as error:
            raise ValueError(f"Invalid edge sensor-window record at index {index}") from error


def validate_edge_routing_records(records: Iterable[Any]) -> Iterator[EdgeRoutingExample]:
    """Validate rows without hiding duplicates from downstream quality gates."""
    by_id: dict[str, str] = {}
    by_decision: dict[tuple[str, str, str, str, str], str] = {}
    for index, raw in enumerate(records):
        try:
            record = EdgeRoutingExample.model_validate(raw)
        except Exception as error:
            raise ValueError(f"Invalid edge routing record at index {index}") from error
        content = record.model_dump_json(exclude_none=True)
        existing = by_id.get(record.record_id)
        if existing is not None:
            if existing != content:
                raise ValueError("same record_id has different content")
            yield record
            continue
        features = record.features
        identity = (
            features.group_id, features.session_id, features.task_id,
            features.source_event_id, features.decision_at.isoformat(),
        )
        other_id = by_decision.get(identity)
        if other_id is not None:
            raise ValueError("same decision identity has different record IDs")
        by_id[record.record_id] = content
        by_decision[identity] = record.record_id
        yield record


def dispatch_validator(
    records: Iterable[Any],
    record_schema: Literal[
        "conversation", "can_frame", "can_artifact", "generic",
        "edge_sensor_window", "edge_routing_example",
    ] = "conversation",
) -> Iterator[Any]:
    """Dispatch to the correct validator based on the recipe record schema."""
    validators = {
        "conversation": validate_conversation_records,
        "can_frame": validate_can_frame_records,
        "can_artifact": validate_generic_records,
        "generic": validate_generic_records,
        "edge_sensor_window": validate_edge_sensor_window_records,
        "edge_routing_example": validate_edge_routing_records,
    }
    validator = validators.get(record_schema)
    if validator is None:
        raise ValueError(f"Unknown record_schema: {record_schema}")
    return validator(records)
