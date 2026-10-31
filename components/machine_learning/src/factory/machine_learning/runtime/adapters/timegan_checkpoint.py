"""TimeGAN checkpoint persistence and disk-backed model registry.

Extracted from ``timegan.py`` to keep that file under the 200-LOC ceiling.
Handles saving/loading model checkpoints and maintaining a JSON registry
that survives adapter instance recreation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import torch

from .timegan_models import Discriminator, Generator

_logger = logging.getLogger(__name__)

_REGISTRY_FILENAME = "registry.json"


def save_checkpoint(
    root: Path,
    G: Generator,
    D: Discriminator,
    hyper: dict[str, Any],
    n_features: int,
    seq_len: int,
    parent_model_id: str | None = None,
    iteration: int = 0,
) -> tuple[str, str]:
    """Persist both networks + shapes to ``<root>/<job_id>/timegan.pt``.

    Returns (job_id, model_path).
    """
    job_id = str(uuid.uuid4())
    model_dir = root / job_id
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = str(model_dir / "timegan.pt")
    torch.save({
        "G_state": G.state_dict(), "D_state": D.state_dict(),
        "latent_dim": hyper["latent_dim"], "hidden_dim": hyper["hidden_dim"],
        "n_layers": hyper["n_layers"], "n_features": n_features, "seq_len": seq_len,
    }, model_path)
    return job_id, model_path


def load_checkpoint(model_path: str, G: Generator, D: Discriminator) -> dict[str, Any]:
    """Load Generator + Discriminator state dicts from a .pt checkpoint.

    Returns the checkpoint metadata dict (hyperparams, shapes).
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
    }


def load_registry(root: Path) -> dict[str, dict[str, Any]]:
    """Load the model registry from disk. Returns empty dict if missing."""
    reg_path = root / _REGISTRY_FILENAME
    if not reg_path.exists():
        return {}
    try:
        with open(reg_path) as f:
            return json.load(f)
    except Exception as exc:
        _logger.warning("Failed to load registry: %s", exc)
        return {}


def save_registry(root: Path, models: dict[str, dict[str, Any]]) -> None:
    """Persist the model registry to disk."""
    reg_path = root / _REGISTRY_FILENAME
    try:
        with open(reg_path, "w") as f:
            json.dump(models, f, indent=2, default=str)
    except Exception as exc:
        _logger.warning("Failed to save registry: %s", exc)


def register_model(
    root: Path,
    models: dict[str, dict[str, Any]],
    job_id: str,
    model_path: str,
    metrics: dict[str, Any],
    hyper: dict[str, Any],
    n_features: int,
    seq_len: int,
    X_uri: str,
    exp_id: str | None = None,
    run_id: str | None = None,
    parent_model_id: str | None = None,
    iteration: int = 0,
) -> dict[str, Any]:
    """Register a new model in the in-memory dict and persist to disk."""
    rec = {
        "id": job_id,
        "model_type": "timegan",
        "model_path": model_path,
        "metrics": metrics,
        "X_uri": X_uri,
        "experiment_id": exp_id,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "latent_dim": hyper["latent_dim"],
        "hidden_dim": hyper["hidden_dim"],
        "n_layers": hyper["n_layers"],
        "n_features": n_features,
        "seq_len": seq_len,
        "parent_model_id": parent_model_id,
        "iteration": iteration,
    }
    models[job_id] = rec
    save_registry(root, models)
    return rec
