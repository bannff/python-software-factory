"""Conditional TimeGAN adapter for failure-mode-conditioned generation.

Extends :class:`TimeGANAdapter` (Phase 1) with a one-hot failure-mode
side channel that is concatenated with both the generator's latent
noise and the discriminator's input window:

* Generator:  ``concat(z, mode_onehot) → LSTM → window``
* Discriminator: ``concat(window, mode_onehot) → LSTM → P(real)``

The mode-label registry (``mode_names``: ``list[str]``) is stored in
the checkpoint so :meth:`sample` can convert ``failure_mode='amplitude_spike'``
into the matching one-hot. Training loop, checkpoint I/O, validation,
and metrics helpers live in :mod:`timegan_conditional_helpers` so this
file stays under the 200-LOC factory ceiling.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ..ports import (
    TimeSeriesModelType, TimeSeriesTrainingConfig, TimeSeriesTrainingJob,
)
from .scania_label_builder import DEFAULT_MODE_NAMES
from .timegan import TimeGANAdapter, _load_npy
from .timegan_conditional_helpers import (
    build_conditional_loader, build_conditional_metrics,
    load_conditional_checkpoint, register_conditional_model,
    save_conditional_checkpoint, validate_conditional_inputs,
)
from .timegan_conditional_models import (
    ConditionalDiscriminator, ConditionalGenerator,
)
from .timegan_conditional_training import conditional_train_loop

_logger = logging.getLogger(__name__)


class ConditionalTimeGANAdapter(TimeGANAdapter):
    """TimeGAN with failure-mode conditioning for SCANIA failure generation.

    Training consumes a window tensor ``X`` of shape ``(N, T, F)``
    plus a one-hot label tensor ``Y`` of shape ``(N, n_modes)``.
    Sampling takes a ``failure_mode`` string resolved against the
    model registry's ``mode_names`` list.
    """

    def __init__(self, tracker: Any = None, checkpoint_store: Any = None) -> None:
        # Inherit registry, root path, and (optional) experiment tracker.
        super().__init__(tracker=tracker, checkpoint_store=checkpoint_store)

    # ----- Conditioning helpers -------------------------------------------

    @staticmethod
    def _onehot(idx: int, n_modes: int) -> torch.Tensor:
        """Return a ``(1, n_modes)`` one-hot tensor for mode index ``idx``."""
        v = torch.zeros(1, n_modes)
        v[0, idx] = 1.0
        return v

    def _resolve_mode_index(self, mode_names: list[str], failure_mode: str) -> int:
        """Map a failure-mode string to its index; raise on unknown mode."""
        try:
            return mode_names.index(failure_mode)
        except ValueError:
            raise KeyError(
                f"Unknown failure_mode={failure_mode!r}; "
                f"available modes: {mode_names}",
            ) from None

    # ----- Training --------------------------------------------------------

    def train(
        self, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        parent_model_id: str | None = None,
        classifier_feedback: dict[str, float] | None = None,
    ) -> TimeSeriesTrainingJob:
        """Train or continue training a conditional TimeGAN.

        ``X_uri`` is a 3D window tensor ``(N, T, F)`` and ``y_uri`` a
        one-hot label tensor ``(N, n_modes)``. The mode vocabulary
        defaults to the SCANIA triplet so the adapter works with the
        output of :mod:`scania_label_builder` out of the box.
        """
        cfg = config or TimeSeriesTrainingConfig()
        hyper = self._resolve_hyper(cfg)
        torch.manual_seed(cfg.seed); np.random.seed(cfg.seed)

        X = _load_npy(X_uri).astype(np.float32)
        Y = _load_npy(y_uri).astype(np.float32)
        n_modes = Y.shape[1]
        # Mode vocabulary: explicit extra.mode_names wins; else SCANIA
        # triplet (works with scania_label_builder output); else placeholders.
        explicit = cfg.extra.get("mode_names")
        if explicit is not None:
            mode_names = list(explicit)
        elif n_modes == len(DEFAULT_MODE_NAMES):
            mode_names = list(DEFAULT_MODE_NAMES)
        else:
            mode_names = [f"mode_{i}" for i in range(n_modes)]
        n_samples, seq_len, n_features = validate_conditional_inputs(
            X, Y, n_modes, mode_names,
        )
        n_train = max(1, int(n_samples * (1 - cfg.validation_split)))
        loader = build_conditional_loader(X, Y, n_train, hyper["batch_size"])
        G = ConditionalGenerator(hyper["latent_dim"], n_modes, hyper["hidden_dim"],
                                 hyper["n_layers"], n_features)
        D = ConditionalDiscriminator(n_features, n_modes, hyper["hidden_dim"],
                                    hyper["n_layers"])
        iteration = 0
        if parent_model_id:
            rec = self._models.get(parent_model_id)
            if rec is None:
                raise KeyError(f"Model not found: {parent_model_id}")
            load_conditional_checkpoint(rec["model_path"], G, D)
            iteration = rec.get("iteration", 0) + 1
        auroc = float(classifier_feedback.get("auroc", 0.0)) if classifier_feedback else 0.0
        g_loss, d_loss, comp = conditional_train_loop(G, D, loader, hyper, n_modes, auroc)

        job_id, model_path = save_conditional_checkpoint(
            self._root, G, D, hyper, n_features, seq_len, n_modes,
            mode_names, parent_model_id, iteration,
        )
        # Quick distribution probe (first 64 windows, mode=0 for shape sanity).
        G.eval()
        probe_c = self._onehot(0, n_modes).repeat(min(64, n_samples), 1)
        x_probe = G(torch.randn(min(64, n_samples), seq_len, hyper["latent_dim"]),
                    probe_c).detach().numpy()
        metrics = build_conditional_metrics(
            g_loss, d_loss, comp, auroc, X, n_train, x_probe,
            n_modes, mode_names, parent_model_id, iteration,
        )
        exp_id, run_id = self._tracker_log(experiment_name, cfg, metrics, model_path, hyper)
        register_conditional_model(
            self._root, self._models, job_id, model_path, metrics, hyper,
            n_features, seq_len, n_modes, mode_names, X_uri, y_uri,
            exp_id, run_id, parent_model_id, iteration,
        )
        return TimeSeriesTrainingJob(
            id=job_id, model_type=TimeSeriesModelType.timegan,
            status="completed", experiment_id=exp_id, run_id=run_id,
            config=cfg, metrics=metrics, model_path=model_path,
        )

    def continue_train(
        self, model_id: str, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        classifier_feedback: dict[str, float] | None = None,
    ) -> TimeSeriesTrainingJob:
        """Continue training a conditional TimeGAN from a previous checkpoint."""
        return self.train(
            X_uri, y_uri, config, experiment_name,
            parent_model_id=model_id, classifier_feedback=classifier_feedback,
        )

    # ----- Sampling --------------------------------------------------------

    def sample(
        self, model_id: str, n_samples: int, failure_mode: str,
        *, seed: int = 42, temperature: float = 1.0,
    ) -> str:
        """Generate ``n_samples`` windows conditioned on ``failure_mode``.

        ``temperature`` scales the latent noise: ``<1.0`` concentrates
        near the generator's mean (cleaner but less diverse); ``>1.0``
        explores the latent space (counter-acts mode collapse).
        """
        rec = self._models.get(model_id)
        if rec is None:
            raise KeyError(f"Model not found: {model_id}")
        # Build G from the checkpoint; D is built only because the loader
        # needs an instance to populate (it is not used at sample time).
        G = ConditionalGenerator(rec["latent_dim"], rec["n_modes"],
                                 rec["hidden_dim"], rec["n_layers"], rec["n_features"])
        D = ConditionalDiscriminator(rec["n_features"], rec["n_modes"],
                                     rec["hidden_dim"], rec["n_layers"])
        load_conditional_checkpoint(rec["model_path"], G, D)
        mode_idx = self._resolve_mode_index(rec["mode_names"], failure_mode)
        G.eval()
        gen = torch.Generator().manual_seed(seed)
        z = torch.randn(n_samples, rec["seq_len"], rec["latent_dim"],
                        generator=gen) * temperature
        c = self._onehot(mode_idx, rec["n_modes"]).repeat(n_samples, 1)
        with torch.no_grad():
            x_fake = G(z, c).numpy()
        out_path = Path(rec["model_path"]).parent / "samples.npy"
        np.save(out_path, x_fake)
        return f"file://{out_path}"
