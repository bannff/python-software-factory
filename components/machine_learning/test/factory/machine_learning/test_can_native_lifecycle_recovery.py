"""Native CAN lifecycle lock and crash-reconciliation invariants."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from hypothesis import given, strategies as st
import pytest

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_lifecycle_canonical import effect_identity
from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext
from factory.machine_learning.runtime.can_native_record import (
    publish_native_record,
    replay_native_record,
)

_OPERATION = "ml.train-can-portfolio@v1"
_REQUEST_SHA = "d" * 64
_UNIT = "train-lnn:0x100@v1"


def _model(root: Path) -> Path:
    path = root / "model" / "weights.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"sealed-native-model")
    return path


def test_nested_attempt_and_effect_locks_are_reentrant(tmp_path: Path) -> None:
    """The outer attempt lock must not self-deadlock on its nested effect."""
    completed = threading.Event()

    def nested() -> None:
        store = LocalCanLifecycleStore(tmp_path)
        with store.lock(_OPERATION, "attempt"):
            with store.lock(f"{_OPERATION}:effect", "effect"):
                completed.set()

    worker = threading.Thread(target=nested, daemon=True)
    worker.start()
    assert completed.wait(2), "nested lifecycle authority lock deadlocked"
    worker.join(2)
    assert not worker.is_alive()


def test_native_record_reconciles_crash_before_effect_receipt(tmp_path: Path) -> None:
    """A sealed native record is the recovery authority after receipt loss."""
    root, store = tmp_path / "models", LocalCanLifecycleStore(tmp_path / "authority")
    model = _model(root)
    binding = {"family": "lnn", "can_id": "0x100", "seed": 17}
    row = {"model_path": str(model), "job_id": "native-job"}
    effect_id = effect_identity(_OPERATION, _REQUEST_SHA, _UNIT)
    expected = publish_native_record(root, effect_id, binding, row)
    context = CanLifecycleContext(_OPERATION, _REQUEST_SHA, store)
    try:
        recovered = context.effect(
            _UNIT, binding,
            lambda observed: replay_native_record(root, observed, binding),
            lambda _observed: pytest.fail("sealed native effect must reconcile"),
        )
        replay = context.effect(
            _UNIT, binding,
            lambda _observed: pytest.fail("receipt must replay first"),
            lambda _observed: pytest.fail("effect must not execute twice"),
        )
        assert recovered == replay == expected
        effects = list((tmp_path / "authority/can_lifecycle/effects").iterdir())
        assert len(effects) == 2
    finally:
        model.parent.chmod(0o700)


@given(st.integers(min_value=0, max_value=2**31 - 1))
def test_native_record_rejects_any_different_exact_binding(
    alternate_seed: int,
) -> None:
    """A native replay record cannot be claimed by another semantic request."""
    original_seed = alternate_seed + 1
    suffix = hashlib.sha256(str(alternate_seed).encode()).hexdigest()
    with TemporaryDirectory() as directory:
        root = Path(directory) / suffix
        model = _model(root)
        binding = {"family": "lnn", "can_id": "0x100", "seed": original_seed}
        effect_id = hashlib.sha256(f"effect:{suffix}".encode()).hexdigest()
        publish_native_record(root, effect_id, binding, {"model_path": str(model)})
        try:
            with pytest.raises(ValueError, match="exact request"):
                replay_native_record(
                    root, effect_id,
                    {**binding, "seed": alternate_seed},
                )
        finally:
            model.parent.chmod(0o700)
