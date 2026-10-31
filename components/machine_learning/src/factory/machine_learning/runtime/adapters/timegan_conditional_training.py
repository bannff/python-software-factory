"""Conditional TimeGAN training loop.

Single-function module extracted from ``timegan_conditional_helpers``
to keep the helper file under the 200-LOC factory ceiling. The loop
reuses the dual-objective loss from :mod:`timegan_loss` unchanged
from Phase 1; only the G and D forward calls receive the extra
``mode_onehot`` argument.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from .timegan_loss import (
    DualObjectiveConfig, discriminator_targets, generator_loss,
)
from .timegan_conditional_models import (
    ConditionalDiscriminator, ConditionalGenerator,
)


def conditional_train_loop(
    G: ConditionalGenerator, D: ConditionalDiscriminator,
    loader: DataLoader, hyper: dict[str, Any], n_modes: int, auroc: float = 0.0,
) -> tuple[float, float, dict[str, float]]:
    """Conditional G/D training with the dual-objective loss from Phase 1.

    Loader yields ``(x_real, y_onehot)`` pairs. The one-hot is fed to G
    alongside the random latent noise, and to D alongside both the
    real and the generated window. The loss is identical to the
    un-conditional version: ``adversarial + diversity`` (with AUROC
    taper). Returns ``(g_loss, d_loss, components)``.
    """
    bce, loss_cfg = nn.BCELoss(), DualObjectiveConfig()
    G_opt = optim.Adam(G.parameters(), lr=hyper["lr"])
    D_opt = optim.Adam(D.parameters(), lr=hyper["lr"])
    g_loss_final = d_loss_final = 0.0
    components: dict[str, float] = {"g_gan": 0.0, "g_div": 0.0, "g_gan_weight": 1.0}
    L = hyper["latent_dim"]
    for _ in range(hyper["epochs_reconstruction"]):
        G.train(); D.eval()
        for x_real, y_onehot in loader:
            z = torch.randn(x_real.size(0), x_real.size(1), L)
            g_out = G(z, y_onehot)
            g_loss, comp = generator_loss(
                D(g_out, y_onehot), g_out, x_real.size(0), bce, auroc, loss_cfg,
            )
            G_opt.zero_grad(); g_loss.backward(); G_opt.step()
            g_loss_final = float(g_loss.item()); components = comp
    for _ in range(hyper["epochs_adversarial"]):
        D.train(); G.eval()
        for x_real, y_onehot in loader:
            z = torch.randn(x_real.size(0), x_real.size(1), L)
            with torch.no_grad():
                x_fake = G(z, y_onehot)
            real_t, fake_t = discriminator_targets(
                x_real.size(0), auroc, x_real.device, loss_cfg,
            )
            d_loss = (
                bce(D(x_real, y_onehot), real_t)
                + bce(D(x_fake, y_onehot), fake_t)
            )
            D_opt.zero_grad(); d_loss.backward(); D_opt.step()
            d_loss_final = float(d_loss.item())
    return g_loss_final, d_loss_final, components
