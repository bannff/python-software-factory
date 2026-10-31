"""Hybrid SCANIA/TimeGAN training helpers for ``can_synthesize``.

Extracted from :mod:`can_synthesize` to keep that adapter under the
200-LOC factory ceiling. This module owns the cross-brick wiring for
Phase 4: it turns a ``scania_data_uri`` into a fully trained
:class:`ConditionalTimeGANAdapter` and returns a
:class:`LearnedSampler` closure that the failure-injection layer can
call per event.

The training pipeline:

1. :class:`ScaniaPatternExtractor` → (N, T, F) failure-window tensor
2. :func:`assign_failure_modes`     → (N, n_modes) one-hot labels
3. Persist X and Y as ``.npy`` files (the TimeGAN adapter takes URIs)
4. :class:`ConditionalTimeGANAdapter` → trained checkpoint + ``model_id``
5. Wrap ``adapter.sample`` in a closure that flattens the
   (n, T, F) output to (T, F) for a single window (the sampler is
   used per failure event, never for batches).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ._can_synthesize_hybrid_utils import (
    match_signals, resample_time, uri_to_path,
)
from ._hybrid_injection_helpers import LearnedSampler
from ._scania_record_loader import load_scania_records

_logger = logging.getLogger(__name__)

__all__ = ["build_hybrid_sampler", "ScariaTrainingError"]


class ScariaTrainingError(RuntimeError):
    """Raised when the SCANIA → TimeGAN training pipeline fails."""


def build_hybrid_sampler(
    *,
    scania_data_uri: str | None,
    scania_model_id: str | None,
    seed: int,
    epochs: int = 30,
) -> LearnedSampler | None:
    """Return a :class:`LearnedSampler` closure, or ``None`` if not configured.

    Either ``scania_data_uri`` (train a fresh model) or
    ``scania_model_id`` (reuse an existing checkpoint) must be
    provided. When both are present, ``scania_model_id`` wins — the
    cached checkpoint is faster and the user has already paid for
    training.
    """
    if scania_model_id:
        return _build_sampler_from_checkpoint(scania_model_id)
    if scania_data_uri:
        return _train_and_build_sampler(scania_data_uri, seed, epochs)
    return None


def _train_and_build_sampler(
    scania_data_uri: str, seed: int, epochs: int,
) -> LearnedSampler:
    """End-to-end: SCANIA CSV → patterns → labels → TimeGAN → sampler."""
    try:
        # Lazy imports: the machine_learning brick only needs to be on
        # the path when the caller actually asks for hybrid injection.
        # The dataset brick must remain importable without the optional
        # ML extras.
        from factory.machine_learning.interface import (
            DEFAULT_MODE_NAMES, ConditionalTimeGANAdapter,
            TimeSeriesTrainingConfig, assign_failure_modes,
        )
    except ImportError as exc:
        raise ScariaTrainingError(
            f"Hybrid injection requires the machine_learning brick: {exc}",
        ) from exc

    try:
        from factory.dataset.runtime.adapters.scania_pattern_extractor import (
            ScaniaPatternExtractor,
        )
    except ImportError as exc:
        raise ScariaTrainingError(
            f"Hybrid injection requires the dataset scania adapter: {exc}",
        ) from exc

    signatures = ScaniaPatternExtractor().extract_failure_signatures(
        load_scania_records(scania_data_uri),
    )
    X = signatures["aps_failure"]
    Y, mode_names = assign_failure_modes(X, DEFAULT_MODE_NAMES)
    _logger.info(
        "SCANIA pattern extraction: X=%s Y=%s modes=%s",
        X.shape, Y.shape, list(mode_names),
    )

    workdir = Path(tempfile.mkdtemp(prefix="hybrid_timegan_"))
    x_uri = str(workdir / "scania_X.npy")
    y_uri = str(workdir / "scania_Y.npy")
    np.save(x_uri, X.astype(np.float32))
    np.save(y_uri, Y.astype(np.float32))

    cfg = TimeSeriesTrainingConfig(
        epochs=epochs, seed=seed,
        extra={"mode_names": list(mode_names)},
    )
    adapter = ConditionalTimeGANAdapter()
    job = adapter.train(x_uri, y_uri, config=cfg, experiment_name="hybrid_sampler")
    return _wrap_sampler(adapter, job.id, tuple(mode_names))


def _build_sampler_from_checkpoint(model_id: str) -> LearnedSampler:
    """Wrap an existing conditional TimeGAN checkpoint as a sampler."""
    try:
        from factory.machine_learning.interface import ConditionalTimeGANAdapter
    except ImportError as exc:
        raise ScariaTrainingError(
            f"Hybrid injection requires the machine_learning brick: {exc}",
        ) from exc
    # We don't know the mode vocabulary without loading the checkpoint;
    # a fresh adapter instance re-reads the on-disk registry.
    adapter = ConditionalTimeGANAdapter()
    return _wrap_sampler(adapter, model_id, _default_mode_names())


def _wrap_sampler(
    adapter: Any, model_id: str, mode_names: tuple[str, ...],
) -> LearnedSampler:
    """Bind ``adapter.sample`` into the ``LearnedSampler`` contract.

    The TimeGAN returns a ``file://`` URI; we load the resulting
    ``samples.npy`` and take the first window. The shape contract is
    ``(T, F)`` regardless of the TimeGAN's batch dimension.
    """
    def _sampler(
        n_frames: int,
        failure_mode: str,
        n_signals: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        # Cycle to the first known mode if the caller asked for an
        # unknown mode — keeps the pipeline robust to upstream typos.
        mode = failure_mode if failure_mode in mode_names else mode_names[0]
        out_uri = adapter.sample(
            model_id, n_samples=1, failure_mode=mode,
            seed=int(rng.integers(0, 2**31 - 1)),
        )
        samples = np.load(uri_to_path(out_uri), allow_pickle=False)
        if samples.ndim == 3:
            samples = samples[0]  # (1, T, F) -> (T, F)
        if samples.shape[0] != n_frames:
            samples = resample_time(samples, n_frames)
        if samples.shape[1] != n_signals:
            samples = match_signals(samples, n_signals, rng)
        return samples

    return _sampler


def _default_mode_names() -> tuple[str, ...]:
    """Lazy lookup of the SCANIA mode vocabulary from the ML brick."""
    from factory.machine_learning.interface import DEFAULT_MODE_NAMES
    return tuple(DEFAULT_MODE_NAMES)
