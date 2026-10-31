"""Conditional TimeGAN helper functions (checkpoints, registry, validation).

Kept out of ``timegan_conditional.py`` so the main adapter class stays
under the 200-LOC factory ceiling. The training loop itself lives in
:mod:`timegan_conditional_training` for the same reason. The split
mirrors the Phase 1 ``timegan.py`` + ``timegan_models.py`` +
``timegan_loss.py`` + ``timegan_checkpoint.py`` layout.

Public surface used by the adapter:
* :func:`save_conditional_checkpoint` — write G+D+mode metadata to disk.
* :func:`load_conditional_checkpoint` — load G+D, return checkpoint meta.
* :func:`register_conditional_model` — append to in-memory + disk registry.
* :func:`validate_conditional_inputs` — shape + one-hot sanity checks.
* :func:`build_conditional_loader` — torch DataLoader for (x, y) pairs.
* :func:`build_conditional_metrics` — assemble the metrics dict.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from .timegan_checkpoint import save_registry
from .timegan_conditional_models import (
    ConditionalDiscriminator, ConditionalGenerator,
)

_CONDITIONAL_MODEL_TYPE = "timegan_conditional"


def save_conditional_checkpoint(
    root: Path, G: ConditionalGenerator, D: ConditionalDiscriminator,
    hyper: dict[str, Any], n_features: int, seq_len: int, n_modes: int,
    mode_names: list[str], parent_id: str | None, iteration: int,
) -> tuple[str, str]:
    """Persist conditional G+D+mode metadata to a new ``.pt`` file.

    Returns ``(job_id, model_path)``. The mode registry travels inside
    the checkpoint so :func:`load_conditional_checkpoint` can rebuild
    the failure-mode vocabulary without an external mapping.
    """
    job_id = str(uuid.uuid4())
    model_dir = root / job_id
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = str(model_dir / "timegan_conditional.pt")
    torch.save({
        "G_state": G.state_dict(), "D_state": D.state_dict(),
        "latent_dim": hyper["latent_dim"], "hidden_dim": hyper["hidden_dim"],
        "n_layers": hyper["n_layers"], "n_features": n_features,
        "seq_len": seq_len, "n_modes": n_modes,
        "mode_names": list(mode_names),
        "parent_model_id": parent_id, "iteration": iteration,
    }, model_path)
    return job_id, model_path


def load_conditional_checkpoint(
    model_path: str, G: ConditionalGenerator, D: ConditionalDiscriminator,
) -> dict[str, Any]:
    """Load G+D state dicts; return the checkpoint metadata dict.

    The returned dict carries ``mode_names`` and ``n_modes`` so the
    adapter can map ``failure_mode='amplitude_spike'`` → one-hot at
    sample time.
    """
    payload = torch.load(model_path, weights_only=True)
    G.load_state_dict(payload["G_state"])
    D.load_state_dict(payload["D_state"])
    return {
        "latent_dim": payload["latent_dim"],
        "hidden_dim": payload["hidden_dim"],
        "n_layers": payload["n_layers"],
        "n_features": payload["n_features"],
        "seq_len": payload["seq_len"],
        "n_modes": payload["n_modes"],
        "mode_names": payload["mode_names"],
        "parent_model_id": payload.get("parent_model_id"),
        "iteration": payload.get("iteration", 0),
    }


def register_conditional_model(
    root: Path, models: dict[str, dict[str, Any]],
    job_id: str, model_path: str, metrics: dict[str, Any],
    hyper: dict[str, Any], n_features: int, seq_len: int, n_modes: int,
    mode_names: list[str], X_uri: str, y_uri: str,
    exp_id: str | None, run_id: str | None,
    parent_id: str | None, iteration: int,
) -> dict[str, Any]:
    """Append a new conditional model record to the in-memory + disk registry.

    The record is the adapter's source of truth for the model (paths,
    mode vocabulary, lineage). The same shape is also returned so
    callers can read fields back without indexing the registry.
    """
    rec = {
        "id": job_id, "model_type": _CONDITIONAL_MODEL_TYPE,
        "model_path": model_path, "metrics": metrics,
        "X_uri": X_uri, "y_uri": y_uri,
        "n_modes": n_modes, "mode_names": list(mode_names),
        "experiment_id": exp_id, "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "latent_dim": hyper["latent_dim"], "hidden_dim": hyper["hidden_dim"],
        "n_layers": hyper["n_layers"], "n_features": n_features,
        "seq_len": seq_len, "parent_model_id": parent_id, "iteration": iteration,
    }
    models[job_id] = rec
    save_registry(root, models)
    return rec


# ----- Input validation + DataLoader + metrics ---------------------------


def validate_conditional_inputs(
    X: np.ndarray, Y: np.ndarray, n_modes: int, mode_names: list[str],
) -> tuple[int, int, int]:
    """Validate X/Y shapes, one-hot distribution, and mode-names length.

    Returns ``(n_samples, seq_len, n_features)``. Raises ``ValueError``
    with a descriptive message on the first inconsistency. The one-hot
    check enforces ``sum(Y_i) == 1.0`` for every row (within 1e-3) so
    silent label corruption fails loudly.
    """
    if X.ndim != 3:
        raise ValueError(f"ConditionalTimeGAN expects 3D X (n, T, F); got ndim={X.ndim}")
    if Y.ndim != 2:
        raise ValueError(f"ConditionalTimeGAN expects 2D one-hot Y (n, n_modes); got ndim={Y.ndim}")
    if X.shape[0] != Y.shape[0]:
        raise ValueError(
            f"X/Y row mismatch: X has {X.shape[0]} windows, Y has {Y.shape[0]} labels",
        )
    if Y.shape[1] != n_modes:
        raise ValueError(
            f"Y has {Y.shape[1]} columns but n_modes={n_modes} (from extra.mode_names)",
        )
    row_sums = Y.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-3):
        raise ValueError(
            f"Y rows must sum to 1.0 (one-hot); got min={row_sums.min():.3f}, max={row_sums.max():.3f}",
        )
    # Strict one-hot: each row must have exactly one 1 and the rest 0.
    # A row of all 0.5 would pass the sum check but silently corrupt
    # the conditioning signal.
    binary = np.isclose(Y, 1.0, atol=1e-3)
    if not np.all(binary.sum(axis=1) == 1):
        bad = int(np.sum(binary.sum(axis=1) != 1))
        raise ValueError(
            f"Y must be one-hot (exactly one 1 per row); {bad}/{Y.shape[0]} rows are not",
        )
    if len(mode_names) != n_modes:
        raise ValueError(
            f"mode_names length {len(mode_names)} != n_modes {n_modes}",
        )
    return X.shape


def build_conditional_loader(
    X: np.ndarray, Y: np.ndarray, n_train: int, batch_size: int,
) -> DataLoader:
    """Build a torch DataLoader for the (x, y) training pairs.

    Mirrors the Phase 1 ``TimeGANAdapter`` split: train on the first
    ``n_train`` rows, hold out the tail for validation. Shuffled per
    epoch so the GAN sees different mode-balanced mini-batches.
    """
    return DataLoader(
        TensorDataset(torch.from_numpy(X[:n_train]), torch.from_numpy(Y[:n_train])),
        batch_size=batch_size, shuffle=True,
    )


def build_conditional_metrics(
    g_loss: float, d_loss: float, comp: dict[str, float], auroc: float,
    X: np.ndarray, n_train: int, x_probe: np.ndarray, n_modes: int,
    mode_names: list[str], parent_id: str | None, iteration: int,
) -> dict[str, Any]:
    """Assemble the metrics dict for MLflow / TensorBoard / registry.

    Field set matches the Phase 1 ``TimeGANAdapter`` plus the
    conditional extension fields (``n_modes``, ``mode_names``) so
    downstream dashboards automatically light up the new dimensions.
    """
    return {
        "g_loss_final": g_loss, "d_loss_final": d_loss,
        "real_mean": float(X[:n_train].mean()), "real_std": float(X[:n_train].std()),
        "synthetic_mean": float(x_probe.mean()), "synthetic_std": float(x_probe.std()),
        "n_samples_generated": len(x_probe),
        "n_modes": n_modes, "mode_names": ",".join(mode_names),
        "parent_model_id": parent_id, "iteration": iteration,
        "feedback_auroc": auroc,
        "g_gan_component": comp["g_gan"], "g_div_component": comp["g_div"],
        "g_gan_weight": comp["g_gan_weight"],
    }
