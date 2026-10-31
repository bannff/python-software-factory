"""Properties and caller canaries for the shared validation split."""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from factory.machine_learning.runtime.adapters.temporal_split import (
    temporal_split_indices,
    temporal_split_with_shuffle_fallback,
)


@st.composite
def split_cases(draw):
    """Small valid split inputs with varied label patterns."""
    n = draw(st.integers(min_value=2, max_value=80))
    labels = draw(st.lists(
        st.integers(min_value=0, max_value=2), min_size=n, max_size=n,
    ))
    fraction = draw(st.integers(min_value=1, max_value=99)) / 100
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    return np.asarray(labels), fraction, seed


@settings(max_examples=50, deadline=None)
@given(split_cases())
def test_indices_are_original_complete_disjoint_and_deterministic(case) -> None:
    y, fraction, seed = case
    train, val = temporal_split_indices(y, fraction, seed)
    repeated = temporal_split_indices(y, fraction, seed)
    n_val = max(1, int(len(y) * fraction))
    n_train = max(1, len(y) - n_val)

    np.testing.assert_array_equal(train, repeated[0])
    np.testing.assert_array_equal(val, repeated[1])
    assert len(train) == n_train and len(val) == len(y) - n_train
    assert np.all((0 <= train) & (train < len(y)))
    assert np.all((0 <= val) & (val < len(y)))
    assert len(np.unique(train)) == len(train)
    assert len(np.unique(val)) == len(val)
    assert not set(train).intersection(val)
    np.testing.assert_array_equal(np.sort(np.concatenate([train, val])), np.arange(len(y)))


def test_temporal_branch_returns_original_prefix_and_suffix() -> None:
    y = np.array([0, 1] * 5, dtype=np.int64)
    train, val = temporal_split_indices(y, 0.2, 42)
    np.testing.assert_array_equal(train, np.arange(8))
    np.testing.assert_array_equal(val, np.arange(8, 10))


def test_fallback_returns_exact_seeded_original_row_permutation() -> None:
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int64)
    expected = np.random.default_rng(123).permutation(len(y))
    train, val = temporal_split_indices(y, 0.2, 123)
    np.testing.assert_array_equal(train, expected[:8])
    np.testing.assert_array_equal(val, expected[8:])


def test_wrapper_slices_using_the_exported_original_indices() -> None:
    X = np.arange(30).reshape(10, 3)
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    train, val = temporal_split_indices(y, 0.2, 9)
    Xt, yt, Xv, yv = temporal_split_with_shuffle_fallback(X, y, 0.2, 9)
    np.testing.assert_array_equal(Xt, X[train])
    np.testing.assert_array_equal(yt, y[train])
    np.testing.assert_array_equal(Xv, X[val])
    np.testing.assert_array_equal(yv, y[val])


_CALLERS = (
    ("adapters/sklearn_lightgbm.py", "LightGBM"),
    ("adapters/torch_timeseries.py", "Torch"),
    ("adapters/mlx_timeseries.py", "MLX"),
    ("adapters/transformer_training.py", "transformer/PatchTST"),
    ("adapters/lnn_timespans.py", "LNN"),
    ("adapters/chronos_embedding.py", "Chronos"),
    ("can_model_evaluation.py", "CAN lifecycle Evals holdout"),
)


@pytest.mark.parametrize(("relative_path", "family"), _CALLERS)
def test_all_classifier_callers_delegate_to_shared_wrapper(
    relative_path: str, family: str,
) -> None:
    runtime = Path(__file__).parents[3] / "src/factory/machine_learning/runtime"
    tree = ast.parse((runtime / relative_path).read_text())
    imports_wrapper = any(
        isinstance(node, ast.ImportFrom)
        and any(alias.name == "temporal_split_with_shuffle_fallback" for alias in node.names)
        for node in ast.walk(tree)
    )
    calls_wrapper = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "temporal_split_with_shuffle_fallback"
        for node in ast.walk(tree)
    )
    assert imports_wrapper and calls_wrapper, family
