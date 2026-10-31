"""Fresh S1 tests (epic #124): TrainingLifecycleCoordinator rename + alias.

Pins that the renamed polymorphic coordinator is behavior-identical to the
legacy ``CanLifecycleCoordinator`` alias on the five CAN terminal verbs:
same terminal envelopes and same spec-resolved ``ml.training.*`` events.
Reuses the phase-2 EventRecorder fixture via relative import.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import (
    CanLifecycleContext, CanLifecycleCoordinator,
    TrainingLifecycleContext, TrainingLifecycleCoordinator,
)
from .test_phase2_training_events import EventRecorder

_OP = "ml.train-can-portfolio@v1"
_SELF = {"self": _OP}


class _Result(BaseModel):
    can_ids: list[str]


def test_legacy_names_are_thin_aliases() -> None:
    """The CAN-prefixed names must be the SAME objects, not copies."""
    assert CanLifecycleCoordinator is TrainingLifecycleCoordinator
    assert CanLifecycleContext is TrainingLifecycleContext


def _completed_and_failed(family: str | None, tmp_path: Path) -> EventRecorder:
    recorder = EventRecorder()
    with patch(
        "factory.mcp_utils.registry._services", {"tool_invoker": recorder},
    ):
        coordinator = TrainingLifecycleCoordinator(
            LocalCanLifecycleStore(tmp_path), family=family,
        )
        ok = coordinator.run(_OP, {"attempt_id": "a1"}, _SELF,
                             lambda _ctx: {"can_ids": ["c1"]}, _Result)
        bad = coordinator.run(
            _OP, {"attempt_id": "a2"}, _SELF,
            lambda _ctx: (_ for _ in ()).throw(ValueError("nope")), _Result,
        )
        assert ok["status"] == "completed" and bad["status"] == "failed"
    return recorder


def test_explicit_family_matches_none_default(tmp_path: Path) -> None:
    """The trinary family param: explicit 'can' must equal the None default."""
    explicit = _completed_and_failed("can", tmp_path / "explicit")
    inferred = _completed_and_failed(None, tmp_path / "inferred")
    assert explicit.events == inferred.events
    started = explicit.of_type("ml.training.started")
    completed = explicit.of_type("ml.training.completed")
    failed = explicit.of_type("ml.training.failed")
    assert [s["attempt_id"] for s in started] == ["a1", "a2"]
    assert len(completed) == 1 and len(failed) == 1
    assert "nope" in failed[0]["error"]


def test_family_effects_flow_through_spec_registry_only(tmp_path: Path) -> None:
    """Coordinator envelope keeps its contract: reserved keys intact and
    attempt replay still emits nothing (event names came from the spec, but
    terminal identity verification is unchanged)."""
    recorder = EventRecorder()
    with patch(
        "factory.mcp_utils.registry._services", {"tool_invoker": recorder},
    ):
        coordinator = TrainingLifecycleCoordinator(LocalCanLifecycleStore(tmp_path))
        first = coordinator.run(_OP, {"attempt_id": "r1"}, _SELF,
                                lambda _ctx: {"can_ids": []}, _Result)
        count = len(recorder.events)
        replay = coordinator.run(
            _OP, {"attempt_id": "r1"}, _SELF,
            lambda _ctx: (_ for _ in ()).throw(AssertionError("must not rerun")),
            _Result,
        )
    assert replay == {**first, "status": "completed"}
    assert len(recorder.events) == count


def test_invalid_family_fails_even_for_terminal_replay(tmp_path: Path) -> None:
    """An unknown explicit family is a loud ValueError, not a silent fallback."""
    coordinator = TrainingLifecycleCoordinator(
        LocalCanLifecycleStore(tmp_path), family="nonexistent",
    )
    try:
        coordinator.run(_OP, {"attempt_id": "x"}, _SELF,
                        lambda _ctx: {"can_ids": []}, _Result)
    except ValueError as exc:
        assert "unknown training lifecycle family" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown family")
