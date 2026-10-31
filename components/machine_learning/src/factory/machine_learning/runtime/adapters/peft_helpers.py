"""Generic PEFT (LoRA) backend — the one place ``peft.LoraConfig`` is built.

Maps the brick's backend-agnostic :class:`~..models.LoRAConfig` to a real
``peft.LoraConfig``. Both :class:`ChronosTimeSeriesAdapter`'s LoRA path and
:class:`PeftFineTuningAdapter` route through this single function so the
mapping lives in exactly one place — the previous design had a
Chronos-only ``apply_lora``/``LoRAConfig`` pair in ``chronos_models.py``
that duplicated this logic and couldn't be reused for text-model
fine-tuning (bd:python-factory-q1jsr .5/.6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import LoRAConfig

if TYPE_CHECKING:  # pragma: no cover
    import peft

__all__ = ["build_peft_lora_config"]


def build_peft_lora_config(cfg: LoRAConfig | None = None) -> "peft.LoraConfig":
    """Map the generic :class:`LoRAConfig` to a real ``peft.LoraConfig``.

    ``quantization_bits`` is intentionally not encoded into the returned
    config — ``peft.LoraConfig`` has no such field. Quantized base-model
    loading (4-bit/8-bit) is the caller's responsibility via
    ``transformers.BitsAndBytesConfig`` at ``from_pretrained`` time; we
    accept the field on ``LoRAConfig`` so callers can inspect intent, but
    we don't silently invent behavior for it here.
    """
    from peft import LoraConfig

    cfg = cfg or LoRAConfig()
    return LoraConfig(
        r=cfg.rank,
        lora_alpha=cfg.alpha,
        lora_dropout=cfg.dropout,
        target_modules=list(cfg.target_modules),
        bias="none",
        task_type=None,
    )
