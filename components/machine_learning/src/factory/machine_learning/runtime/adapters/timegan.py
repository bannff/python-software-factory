"""TimeGAN adapter for synthetic time-series generation.

Implements :class:`TimeSeriesGenerationPort` with a dual-objective
loss (adversarial + diversity) that the recursive GAN loop uses to
improve across iterations. Network modules in ``timegan_models.py``;
checkpoint/registry in ``timegan_checkpoint.py``; loss in
``timegan_loss.py`` so this file stays under the 200-LOC ceiling.
"""
from __future__ import annotations
import logging, os, tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ..ports import (TimeSeriesModelType, TimeSeriesTrainingConfig, TimeSeriesTrainingJob)
from .timegan_checkpoint import (load_checkpoint, load_registry, register_model, save_checkpoint)
from .timegan_loss import (DualObjectiveConfig, discriminator_targets, generator_loss)
from .timegan_models import Discriminator, Generator

_logger = logging.getLogger(__name__)


def _load_npy(uri: str) -> np.ndarray:
    """Load a .npy file from a file:// URI or bare path (no pickle)."""
    path = urlparse(uri).path if urlparse(uri).scheme == "file" else uri
    return np.load(path, allow_pickle=False)


class TimeGANAdapter:
    """TimeGAN time-series generator (unsupervised, dual-objective loss)."""

    def __init__(self, tracker: Any = None, checkpoint_store: Any = None) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        root = os.environ.get("TIMEGAN_MODEL_DIR") or tempfile.mkdtemp(prefix="timegan_")
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._models = load_registry(self._root)

    def _tracker_log(
        self, experiment_name: str, cfg: TimeSeriesTrainingConfig,
        metrics: dict[str, float], model_path: str, hyper: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        if self._tracker is None:
            return None, None
        try:
            name = experiment_name or "can-ts-timegan"
            exp = self._tracker.get_experiment_by_name(name) or self._tracker.create_experiment(name=name)
            run = self._tracker.start_run(experiment_id=exp.id)
            self._tracker.log_params(run.id, {"model_type": "timegan", **hyper, "seed": cfg.seed})
            self._tracker.log_metrics(run.id, metrics)
            self._tracker.log_artifact(run.id, model_path)
            self._tracker.end_run(run.id)
            return exp.id, run.id
        except Exception as exc:
            _logger.warning("tracker logging failed: %s", exc)
            return None, None

    def _resolve_hyper(self, cfg: TimeSeriesTrainingConfig) -> dict[str, Any]:
        """Pull TimeGAN-specific hyperparams from config.extra with defaults."""
        ex = cfg.extra
        return {"latent_dim": int(ex.get("latent_dim", 32)),
                "hidden_dim": int(ex.get("hidden_dim", 64)),
                "n_layers": int(ex.get("n_layers", 2)),
                "batch_size": cfg.batch_size, "lr": cfg.learning_rate,
                "epochs_reconstruction": int(ex.get("epochs_reconstruction", 50)),
                "epochs_adversarial": int(ex.get("epochs_adversarial", 50))}

    def _train_loop(
        self, G: Generator, D: Discriminator, loader: DataLoader,
        hyper: dict[str, Any], auroc: float = 0.0,
    ) -> tuple[float, float, dict[str, float]]:
        """G/D phases with the dual-objective loss.

        ``auroc`` (from prior iteration) is the sole signal that
        redirects the generator: high AUROC weakens the adversarial
        weight and engages the diversity penalty; AUROC>0.75 engages
        one-sided label smoothing on D. Returns ``(g, d, components)``.
        """
        bce, loss_cfg = nn.BCELoss(), DualObjectiveConfig()
        G_opt = optim.Adam(G.parameters(), lr=hyper["lr"])
        D_opt = optim.Adam(D.parameters(), lr=hyper["lr"])
        g_loss_final = d_loss_final = 0.0
        components: dict[str, float] = {"g_gan": 0.0, "g_div": 0.0, "g_gan_weight": 1.0}
        L = hyper["latent_dim"]
        for _ in range(hyper["epochs_reconstruction"]):
            G.train(); D.eval()
            for (x_real,) in loader:
                z = torch.randn(x_real.size(0), x_real.size(1), L)
                g_out = G(z)
                g_loss, comp = generator_loss(D(g_out), g_out, x_real.size(0), bce, auroc, loss_cfg)
                G_opt.zero_grad(); g_loss.backward(); G_opt.step()
                g_loss_final = float(g_loss.item()); components = comp
        for _ in range(hyper["epochs_adversarial"]):
            D.train(); G.eval()
            for (x_real,) in loader:
                z = torch.randn(x_real.size(0), x_real.size(1), L)
                with torch.no_grad():
                    x_fake = G(z)
                real_t, fake_t = discriminator_targets(x_real.size(0), auroc, x_real.device, loss_cfg)
                d_loss = bce(D(x_real), real_t) + bce(D(x_fake), fake_t)
                D_opt.zero_grad(); d_loss.backward(); D_opt.step()
                d_loss_final = float(d_loss.item())
        return g_loss_final, d_loss_final, components

    def train(
        self, X_uri: str, config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "", parent_model_id: str | None = None,
        classifier_feedback: dict[str, float] | None = None,
    ) -> TimeSeriesTrainingJob:
        """Train or continue training a TimeGAN on windowed signals."""
        cfg = config or TimeSeriesTrainingConfig()
        hyper = self._resolve_hyper(cfg)
        torch.manual_seed(cfg.seed); np.random.seed(cfg.seed)
        X = _load_npy(X_uri).astype(np.float32)
        if X.ndim != 3:
            raise ValueError(f"TimeGAN expects 3D windows (n, T, F); got ndim={X.ndim}")
        n_samples, seq_len, n_features = X.shape
        n_train = max(1, int(n_samples * (1 - cfg.validation_split)))
        loader = DataLoader(TensorDataset(torch.from_numpy(X[:n_train])),
                            batch_size=hyper["batch_size"], shuffle=True)
        G = Generator(hyper["latent_dim"], hyper["hidden_dim"], hyper["n_layers"], n_features)
        D = Discriminator(n_features, hyper["hidden_dim"], hyper["n_layers"])
        iteration = 0
        if parent_model_id:
            rec = self._models.get(parent_model_id)
            if rec is None:
                raise KeyError(f"Model not found: {parent_model_id}")
            load_checkpoint(rec["model_path"], G, D)
            iteration = rec.get("iteration", 0) + 1
        auroc = float(classifier_feedback.get("auroc", 0.0)) if classifier_feedback else 0.0
        g_loss, d_loss, comp = self._train_loop(G, D, loader, hyper, auroc)
        job_id, model_path = save_checkpoint(self._root, G, D, hyper, n_features,
                                             seq_len, parent_model_id, iteration)
        G.eval()
        x_probe = G(torch.randn(min(64, n_samples), seq_len, hyper["latent_dim"])).detach().numpy()
        metrics = {"g_loss_final": g_loss, "d_loss_final": d_loss,
                   "real_mean": float(X[:n_train].mean()), "real_std": float(X[:n_train].std()),
                   "synthetic_mean": float(x_probe.mean()), "synthetic_std": float(x_probe.std()),
                   "n_samples_generated": len(x_probe),
                   "parent_model_id": parent_model_id, "iteration": iteration,
                   "feedback_auroc": auroc,
                   "g_gan_component": comp["g_gan"], "g_div_component": comp["g_div"],
                   "g_gan_weight": comp["g_gan_weight"]}
        exp_id, run_id = self._tracker_log(experiment_name, cfg, metrics, model_path, hyper)
        register_model(self._root, self._models, job_id, model_path, metrics, hyper,
                       n_features, seq_len, X_uri, exp_id, run_id, parent_model_id, iteration)
        return TimeSeriesTrainingJob(id=job_id, model_type=TimeSeriesModelType.timegan,
                                     status="completed", experiment_id=exp_id, run_id=run_id,
                                     config=cfg, metrics=metrics, model_path=model_path)
    def continue_train(
        self, model_id: str, X_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        classifier_feedback: dict[str, float] | None = None,
    ) -> TimeSeriesTrainingJob:
        """Continue training a TimeGAN from a previous checkpoint."""
        return self.train(X_uri, config, experiment_name,
                          parent_model_id=model_id, classifier_feedback=classifier_feedback)

    def sample(
        self, model_id: str, n_samples: int, *, seed: int = 42, temperature: float = 1.0,
    ) -> str:
        """Generate ``n_samples`` synthetic windows.

        ``temperature`` scales the latent noise: <1.0 concentrates
        near the generator's mean, >1.0 explores the latent space
        (counter-acts mode collapse between recursive iters).
        """
        rec = self._models.get(model_id)
        if rec is None:
            raise KeyError(f"Model not found: {model_id}")
        payload = torch.load(rec["model_path"], weights_only=True)
        G = Generator(payload["latent_dim"], payload["hidden_dim"],
                      payload["n_layers"], payload["n_features"])
        G.load_state_dict(payload["G_state"]); G.eval()
        gen = torch.Generator().manual_seed(seed)
        z = torch.randn(n_samples, payload["seq_len"], payload["latent_dim"],
                        generator=gen) * temperature
        with torch.no_grad():
            x_fake = G(z).numpy()
        out_path = Path(rec["model_path"]).parent / "samples.npy"
        np.save(out_path, x_fake)
        return f"file://{out_path}"


    def get_model(self, model_id: str) -> dict[str, Any] | None:
        return dict(rec) if (rec := self._models.get(model_id)) is not None else None
