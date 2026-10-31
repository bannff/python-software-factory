"""Fine-tuning backend factory (machine_learning.runtime).

Extracted from ``runtime.py`` to keep that file under the 200 LOC
tenet, mirroring the existing ``timeseries_factory.py`` split. Owns
backend construction for :class:`FineTuningPort` adapters: ``memory``
(dev/test simulation), ``mlx`` (Apple Silicon LoRA via subprocess),
and ``peft`` (generic HF + peft LoRA, any text model).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

if TYPE_CHECKING:  # pragma: no cover
    from .adapters.checkpoint_store import CheckpointStore
    from .ports import FineTuningPort

FINETUNING_BACKENDS = ["memory", "mlx", "peft"]


def _resolve_dataset_resolver(config: dict[str, Any], kwargs: dict[str, Any]) -> Any:
    """Shared dataset-resolver lookup for the mlx/peft backends.

    Prefers an explicit ``dataset_resolver`` kwarg or runtime config;
    falls back to building an :class:`McpDatasetResolver` from the
    registered ``tool_invoker`` service, or ``None`` if unavailable
    (the adapter itself fails closed at ``start_job`` time).
    """
    from .adapters.dataset_resolver import McpDatasetResolver

    dataset_resolver = kwargs.pop("dataset_resolver", config.get("dataset_resolver"))
    if dataset_resolver is None:
        try:
            from factory.mcp_utils.interface import get_service
            invoker = get_service("tool_invoker")
            if callable(invoker):
                dataset_resolver = McpDatasetResolver(invoker)
        except Exception:
            dataset_resolver = None
    return dataset_resolver


def create_finetuner(
    backend: str, checkpoint_store: "CheckpointStore", config: dict[str, Any],
    **kwargs: Any,
) -> "FineTuningPort":
    """Build a fine-tuning adapter for a resolved backend name."""
    if backend == "memory":
        from .adapters.memory_finetuning import MemoryFineTuningAdapter
        return MemoryFineTuningAdapter(checkpoint_store=checkpoint_store, **kwargs)
    if backend == "mlx":
        from .adapters.mlx_finetuning import MlxFineTuningAdapter
        return MlxFineTuningAdapter(
            checkpoint_store=checkpoint_store,
            dataset_resolver=_resolve_dataset_resolver(config, kwargs),
            **kwargs,
        )
    if backend == "peft":
        from .adapters.peft_finetuning import PeftFineTuningAdapter
        return PeftFineTuningAdapter(
            checkpoint_store=checkpoint_store,
            dataset_resolver=_resolve_dataset_resolver(config, kwargs),
            **kwargs,
        )
    raise SafeDiagnostic(
        f"Unknown finetuning backend: {backend}. Available: {FINETUNING_BACKENDS}"
    )


__all__ = ["FINETUNING_BACKENDS", "create_finetuner"]
