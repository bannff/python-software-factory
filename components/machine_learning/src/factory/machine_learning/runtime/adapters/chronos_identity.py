"""Immutable Chronos-2 and PEFT identities for the native CAN probe."""
from __future__ import annotations

from importlib.metadata import version
from typing import Any

from ..models import LoRAConfig

MODEL_ID = "amazon/chronos-2"
MODEL_REVISION = "29ec3766d36d6f73f0696f85560a422f50e8498c"
PIPELINE_CLASS = "chronos.Chronos2Pipeline"
PIPELINE_IMPLEMENTATION_CLASS = "chronos.chronos2.pipeline.Chronos2Pipeline"
MODEL_CLASS = "chronos.chronos2.model.Chronos2Model"
PROBE_CLASS = (
    "factory.machine_learning.runtime.adapters.chronos_probe_head.ChronosProbeHead"
)
POOLING = "mean_patches_then_mean_channels"
EMBEDDING = "chronos2_encoder_last_hidden_state"
LORA_TARGET_MODULES = (
    "self_attention.q", "self_attention.k",
    "self_attention.v", "self_attention.o",
)
LIMITATION = "Pooled Chronos-2 CAN classifier probe; not a forecasting model."
PARITY_TOLERANCE = {"rtol": 0.0, "atol": 1e-6}


def acquisition_package_versions() -> dict[str, str]:
    """Return exact installed distributions bound to acquisition evidence."""
    return {
        name: version(name) for name in (
            "chronos-forecasting", "huggingface-hub", "peft", "safetensors",
            "torch", "transformers",
        )
    }


def package_versions() -> dict[str, str]:
    """Return the exact runtime versions sealed into every artifact/passport."""
    return {
        "chronos_version": version("chronos-forecasting"),
        "peft_version": version("peft"),
        "torch_version": version("torch"),
        "transformers_version": version("transformers"),
    }


def exact_lora_config(value: LoRAConfig | None) -> LoRAConfig:
    """Return a closed LoRA config with the literal approved attention targets."""
    config = value or LoRAConfig(target_modules=list(LORA_TARGET_MODULES))
    if (
        tuple(config.target_modules) != LORA_TARGET_MODULES
        or config.quantization_bits is not None
        or type(config.rank) is not int or config.rank <= 0
        or type(config.alpha) is not int or config.alpha <= 0
        or type(config.dropout) is not float or not 0.0 <= config.dropout < 1.0
    ):
        raise ValueError("Chronos LoRA config is outside the approved closed contract")
    return config


def lora_contract(value: LoRAConfig) -> dict[str, Any]:
    """Canonical factory fields expected in native PEFT metadata."""
    return {
        "rank": value.rank, "alpha": value.alpha, "dropout": value.dropout,
        "target_modules": list(LORA_TARGET_MODULES), "bias": "none",
        "task_type": None, "quantization_bits": None,
    }


__all__ = [
    "EMBEDDING", "LIMITATION", "LORA_TARGET_MODULES", "MODEL_CLASS", "MODEL_ID",
    "MODEL_REVISION", "PARITY_TOLERANCE", "PIPELINE_CLASS",
    "PIPELINE_IMPLEMENTATION_CLASS", "POOLING", "PROBE_CLASS",
    "acquisition_package_versions", "exact_lora_config", "lora_contract",
    "package_versions",
]
