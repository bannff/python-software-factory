from __future__ import annotations

import pytest

from factory.machine_learning.runtime.training_errors import classify_training_error


@pytest.mark.parametrize(("error", "code"), [
    (ValueError("LightGBM deployable persistence requires model_root or ML_LIGHTGBM_MODEL_ROOT"), "model_root_not_configured"),
    (ValueError("ModelPassport paths must not contain symlink ancestors"), "symlink_path_rejected"),
    (RuntimeError("native_operation_failed: ModuleNotFoundError: No module named lightgbm"), "native_dependency_missing"),
    (ModuleNotFoundError("x"), "native_dependency_missing"),
    (FileNotFoundError("missing.npy"), "training_data_unreadable"),
    (ValueError("shapes do not match"), "training_failed"),
])
def test_known_causes_get_their_own_code(error: BaseException, code: str) -> None:
    assert classify_training_error(error) == code
