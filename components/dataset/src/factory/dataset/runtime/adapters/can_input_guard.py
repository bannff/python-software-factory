"""Bound eager standalone CAN input loading until external spooling lands."""
from __future__ import annotations

from ..local_inputs import path_from_uri

MAX_STANDALONE_CAN_INPUT_BYTES = 1 << 30  # 1 GiB


def guard_standalone_can_input(uri: str) -> None:
    """Reject input_uri files too large for the current eager JSONL loader."""
    path = path_from_uri(uri)
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ValueError(f"Cannot inspect standalone CAN input {uri}: {error}") from error
    if size > MAX_STANDALONE_CAN_INPUT_BYTES:
        raise ValueError(
            "Standalone CAN input_uri exceeds the 1 GiB eager-load safety limit; "
            "shard or sample the JSONL before windowing. Bounded external-spool "
            "semantics are tracked by python-factory-5pwmd."
        )


__all__ = ["MAX_STANDALONE_CAN_INPUT_BYTES", "guard_standalone_can_input"]
