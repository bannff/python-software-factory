"""TimeGAN dual-objective loss for recursive CAN-synthesis improvement.

Replaces the single BCE multiplier (which cannot redirect the
generator's gradient direction) with three complementary signals:

1. **Standard adversarial BCE** — generator still tries to fool D,
   but the weight *decreases* as classifier AUROC rises. When the
   downstream classifier already discriminates well, we back off
   the adversarial push to avoid the G/D overshoot oscillation.
2. **Diversity loss** — penalises low per-feature standard deviation
   across the generated batch. Without this, the generator collapses
   to a single mode (always producing the same window), and
   classifier AUROC plateaus near chance.
3. **One-sided label smoothing on D** — when AUROC > 0.75 the
   discriminator's real-label target is softened from 1.0 to 0.9.
   This is the standard GAN trick to stop D from saturating on
   perfect scores and starving G of useful gradients.

Why a separate file: the original ``timegan.py`` was at the 199-LOC
ceiling; the dual-objective logic plus the discriminator-side label
smoothing is easier to unit-test in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn


@dataclass(frozen=True)
class DualObjectiveConfig:
    """Hyperparameters for the dual-objective loss.

    Attributes:
        high_auroc_threshold: Above this AUROC, the adversarial weight
            starts to taper off (0.5 is chance, 1.0 is perfect).
        min_gan_weight: Floor on the adversarial loss weight so the
            generator never completely ignores the discriminator.
        diversity_weight: Multiplier on the diversity penalty. Higher
            values push harder against mode collapse.
        diversity_scale: Sharpness of the diversity penalty. The
            penalty is ``1 / (1 + diversity_scale * std)``; larger
            scale = harsher penalty for low-variance outputs.
        label_smooth_threshold: AUROC above which the discriminator
            receives smoothed real labels (0.9 instead of 1.0).
        smoothed_real_target: Real-label value used once smoothing
            kicks in (one-sided smoothing; fake labels stay at 0.0).
    """

    high_auroc_threshold: float = 0.50
    min_gan_weight: float = 0.20
    diversity_weight: float = 0.50
    diversity_scale: float = 10.0
    label_smooth_threshold: float = 0.75
    smoothed_real_target: float = 0.90


def adversarial_weight(auroc: float, cfg: DualObjectiveConfig) -> float:
    """Linear taper of the adversarial loss weight as AUROC rises.

    AUROC <= threshold  -> weight = 1.0 (full adversarial push).
    AUROC  = 1.0       -> weight = min_gan_weight (back off hard).
    """
    if auroc <= cfg.high_auroc_threshold:
        return 1.0
    span = max(1e-6, 1.0 - cfg.high_auroc_threshold)
    progress = min(1.0, max(0.0, (auroc - cfg.high_auroc_threshold) / span))
    return 1.0 - progress * (1.0 - cfg.min_gan_weight)


def diversity_loss(generated: torch.Tensor, cfg: DualObjectiveConfig) -> torch.Tensor:
    """Penalise low per-feature std across the batch.

    ``generated`` has shape ``(B, T, F)``. We collapse T and average
    per-feature std across the batch dimension; a flat generator
    output (mode collapse) gives std ~= 0 and the penalty saturates
    near 1.0. A healthy generator gives std > 1.0 and the penalty
    drops below 0.1.
    """
    # Per-feature std over (B, T) -> shape (F,). Mean across features.
    per_feature_std = generated.std(dim=(0, 1)).mean()
    # ``1 / (1 + scale * std)`` is a smooth, bounded penalty in (0, 1].
    return 1.0 / (1.0 + cfg.diversity_scale * per_feature_std.clamp_min(0.0))


def generator_loss(
    d_fake: torch.Tensor,
    generated: torch.Tensor,
    batch_size: int,
    bce: nn.BCELoss,
    auroc: float,
    cfg: DualObjectiveConfig | None = None,
) -> tuple[torch.Tensor, dict[str, float]]:
    """Compute the dual-objective generator loss.

    Returns the loss tensor plus a dict of component scalars for
    logging. The scalar pieces do not carry gradients — useful for
    TensorBoard/MLflow dashboards.
    """
    cfg = cfg or DualObjectiveConfig()
    gan_w = adversarial_weight(auroc, cfg)
    gan = bce(d_fake, torch.ones(batch_size, 1, device=d_fake.device))
    div = diversity_loss(generated, cfg)
    total = gan_w * gan + cfg.diversity_weight * div
    return total, {
        "g_gan": float(gan.item()),
        "g_div": float(div.item()),
        "g_gan_weight": float(gan_w),
    }


def discriminator_targets(
    batch_size: int, auroc: float, device: torch.device, cfg: DualObjectiveConfig | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build real/fake targets with optional one-sided label smoothing.

    Returns ``(real_target, fake_target)`` both of shape
    ``(batch_size, 1)``. Real target is ``1.0`` normally, dropping
    to ``smoothed_real_target`` when AUROC > threshold. Fake target
    is always ``0.0`` (one-sided smoothing is standard practice).
    """
    cfg = cfg or DualObjectiveConfig()
    real_value = cfg.smoothed_real_target if auroc > cfg.label_smooth_threshold else 1.0
    real_target = torch.full((batch_size, 1), real_value, device=device)
    fake_target = torch.zeros(batch_size, 1, device=device)
    return real_target, fake_target
