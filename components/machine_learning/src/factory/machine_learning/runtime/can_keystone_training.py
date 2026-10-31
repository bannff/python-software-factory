"""Per-model training execution for the CAN keystone."""
from __future__ import annotations

import logging
from typing import Any

from .adapters.training_run_store import persist_training_run
from .can_training_config import (
    build_comparison_row, default_training_config, pick_x_uri, resolve_model_types,
)
from .ports import TimeSeriesModelConfig, TimeSeriesModelType

logger = logging.getLogger(__name__)
_default_config_for = default_training_config
_pick_x_uri = pick_x_uri


def _train_one(
    trainer: Any, model_type: TimeSeriesModelType, x_uri: str, y_uri: str,
    info: dict[str, Any], experiment_name: str, vehicle_id: str,
    model_config: TimeSeriesModelConfig | None = None,
) -> tuple[Any | None, dict[str, Any] | None]:
    """Train one family with isolated failures after successful preflight."""
    cfg = default_training_config(model_type, info["window_size"])
    chosen_x_uri = pick_x_uri(model_type, info)
    family_config = model_config
    if model_type is TimeSeriesModelType.lnn and family_config is None:
        timespans_uri = info.get("timespans_uri")
        if not timespans_uri:
            logger.warning(
                "keystone %s: LNN timing unavailable: %s", vehicle_id,
                info.get("timespans_error", "timespans are absent"),
            )
            return None, None
        family_config = TimeSeriesModelConfig(
            auxiliary_uris={"timespans": timespans_uri},
        )
    try:
        job = trainer.train(
            model_type=model_type, X_uri=chosen_x_uri, y_uri=y_uri,
            config=cfg, experiment_name=experiment_name,
            model_config=family_config,
        )
    except Exception as exc:  # noqa: BLE001 — per-family isolation is intentional
        logger.warning(
            "keystone %s: %s fit failed, skipping row: %s",
            vehicle_id, model_type.value, exc,
        )
        return None, None
    try:
        _augment_with_can_eval(trainer, job, vehicle_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "keystone %s: %s CAN eval failed, keeping training row: %s",
            vehicle_id, model_type.value, exc,
        )
    persist_training_run(job, experiment_name, source="can_keystone")
    return job, build_comparison_row(
        rank=0, arb_id="", info=info, job=job, model_type=model_type,
    )


def _augment_with_can_eval(trainer: Any, job: Any, vehicle_id: str) -> None:
    if not (job.val_y_true and job.val_y_score):
        return
    from .can_keystone_helpers import _get_invoker
    invoker = _get_invoker()
    if not invoker:
        return
    result = invoker(
        "evals_evaluate_can_model", y_true=job.val_y_true,
        y_pred=job.val_y_pred, y_score=job.val_y_score,
    )
    if not getattr(result, "ok", False) or result.data is None:
        return
    for key, value in result.data.model_dump(exclude_none=True).items():
        if isinstance(value, (int, float)):
            job.metrics[key] = value


__all__ = [
    "build_comparison_row", "resolve_model_types",
]
