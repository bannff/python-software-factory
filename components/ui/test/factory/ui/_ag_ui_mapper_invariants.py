"""Shared invariant checker for chat-stream mapper tests.

Kept in a sibling module so each individual test file stays under the
200 LOC cap (the cap applies to source AND test files per
``foreman_guardian_check``).
"""
from __future__ import annotations

from typing import Any


def check_invariants(events: list[dict[str, Any]],
                     require_closure: bool = True) -> None:
    """Raise ``AssertionError`` on any AG-UI invariant violation.

    Invariants:
    1. Exactly one ``TEXT_MESSAGE_START`` per ``messageId``.
    2. Exactly one ``TEXT_MESSAGE_END`` per ``messageId``.
    3. ``TEXT_MESSAGE_CONTENT`` only inside an open START/END pair.
    4. ``TOOL_CALL_END/ARGS`` references a prior ``TOOL_CALL_START``.
    5. No further ``RUN_ERROR`` after ``RUN_ERROR``.
    6. Every ``TOOL_CALL_END`` is followed by a matching
       ``TOOL_CALL_RESULT`` (same ``toolCallId``) — the RESULT event is
       what creates the ``role:"tool"`` message in the AG-UI client
       (bd:python-factory-3uhr).
    7. Every ``REASONING_MESSAGE_END`` is preceded by a matching
       ``REASONING_MESSAGE_START`` with the same ``messageId``;
       ``REASONING_MESSAGE_CONTENT`` only inside an open START/END pair;
       at most one END per ``messageId``; no CONTENT after END for the
       same ``messageId`` (bd:python-factory-eyuj).
    8. Every ``ACTIVITY_SNAPSHOT(replace=True)`` is preceded by a
       paired ``ACTIVITY_SNAPSHOT(replace=False)`` with the same
       ``messageId``; ``ACTIVITY_DELTA`` events only appear between the
       paired open and close snapshots; ``activityType`` is consistent
       across the entire pair (bd:python-factory-6zyg).

    Set ``require_closure=False`` to allow open messages mid-run (used
    by the state machine invariant check).
    """
    starts: dict[str, int] = {}
    ends: dict[str, int] = {}
    open_msg: str | None = None
    tool_starts: set[str] = set()
    pending_result: dict[str, int] = {}  # tcid -> index of TOOL_CALL_END
    matched_result_tcids: set[str] = set()
    reasoning_starts: dict[str, int] = {}
    reasoning_ends: dict[str, int] = {}
    open_reasoning: str | None = None
    activity_open: dict[str, str] = {}  # messageId -> activityType
    activity_closed: set[str] = set()
    terminal_seen = False

    for idx, evt in enumerate(events):
        t = evt["type"]
        assert not terminal_seen or t != "RUN_ERROR", (
            "Event after RUN_ERROR")
        if t == "TEXT_MESSAGE_START":
            mid = evt["messageId"]
            starts[mid] = starts.get(mid, 0) + 1
            assert starts[mid] == 1, f"Duplicate START for {mid}"
            assert open_msg is None, "Nested TEXT_MESSAGE not allowed"
            open_msg = mid
        elif t == "TEXT_MESSAGE_CONTENT":
            mid = evt["messageId"]
            assert open_msg == mid, (
                f"CONTENT outside open message ({mid} vs {open_msg})")
            assert mid not in ends, "CONTENT after END"
        elif t == "TEXT_MESSAGE_END":
            mid = evt["messageId"]
            ends[mid] = ends.get(mid, 0) + 1
            assert ends[mid] == 1, f"Duplicate END for {mid}"
            assert open_msg == mid, "END without matching START"
            open_msg = None
        elif t == "TOOL_CALL_START":
            tool_starts.add(evt["toolCallId"])
        elif t == "TOOL_CALL_ARGS":
            assert evt["toolCallId"] in tool_starts, "ARGS before START"
        elif t == "TOOL_CALL_END":
            tcid = evt["toolCallId"]
            assert tcid in tool_starts, (
                "END references unknown TOOL_CALL_START")
            pending_result[tcid] = idx
        elif t == "TOOL_CALL_RESULT":
            tcid = evt["toolCallId"]
            assert tcid in pending_result, (
                f"RESULT for {tcid} without preceding TOOL_CALL_END")
            assert idx > pending_result[tcid], (
                f"RESULT must come AFTER END for {tcid}")
            matched_result_tcids.add(tcid)
        elif t == "REASONING_MESSAGE_START":
            mid = evt["messageId"]
            reasoning_starts[mid] = reasoning_starts.get(mid, 0) + 1
            assert reasoning_starts[mid] == 1, (
                f"Duplicate REASONING_MESSAGE_START for {mid}")
            assert open_reasoning is None, (
                "Nested REASONING_MESSAGE not allowed")
            open_reasoning = mid
        elif t == "REASONING_MESSAGE_CONTENT":
            mid = evt["messageId"]
            assert open_reasoning == mid, (
                f"REASONING_MESSAGE_CONTENT outside open block "
                f"({mid} vs {open_reasoning})")
            assert mid not in reasoning_ends, (
                "REASONING_MESSAGE_CONTENT after END")
        elif t == "REASONING_MESSAGE_END":
            mid = evt["messageId"]
            assert mid in reasoning_starts, (
                f"REASONING_MESSAGE_END without START for {mid}")
            reasoning_ends[mid] = reasoning_ends.get(mid, 0) + 1
            assert reasoning_ends[mid] == 1, (
                f"Duplicate REASONING_MESSAGE_END for {mid}")
            assert open_reasoning == mid, (
                "REASONING_MESSAGE_END without matching open START")
            open_reasoning = None
        elif t == "ACTIVITY_SNAPSHOT":
            mid = evt["messageId"]
            atype = evt["activityType"]
            replace = bool(evt.get("replace", True))
            if not replace:
                assert mid not in activity_open, (
                    f"Duplicate ACTIVITY_SNAPSHOT(open) for {mid}")
                assert mid not in activity_closed, (
                    f"ACTIVITY_SNAPSHOT(open) reusing closed mid {mid}")
                activity_open[mid] = atype
            else:
                assert mid in activity_open, (
                    f"ACTIVITY_SNAPSHOT(replace=True) for {mid} "
                    f"without prior open snapshot")
                assert activity_open[mid] == atype, (
                    f"activityType mismatch on close for {mid}: "
                    f"{activity_open[mid]} → {atype}")
                activity_open.pop(mid)
                activity_closed.add(mid)
        elif t == "ACTIVITY_DELTA":
            mid = evt["messageId"]
            atype = evt["activityType"]
            assert mid in activity_open, (
                f"ACTIVITY_DELTA for {mid} outside paired snapshots")
            assert activity_open[mid] == atype, (
                f"activityType mismatch on delta for {mid}: "
                f"{activity_open[mid]} vs {atype}")
        elif t == "RUN_ERROR":
            terminal_seen = True

    if require_closure:
        for mid in starts:
            assert mid in ends, f"Open message {mid} never closed"
        for tcid in pending_result:
            assert tcid in matched_result_tcids, (
                f"TOOL_CALL_END for {tcid} never followed by TOOL_CALL_RESULT")
        for mid in reasoning_starts:
            assert mid in reasoning_ends, (
                f"REASONING_MESSAGE_START for {mid} never closed")


__all__ = ["check_invariants"]
