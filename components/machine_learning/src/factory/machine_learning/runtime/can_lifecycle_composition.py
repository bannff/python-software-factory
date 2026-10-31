"""Production composition for the five ML CAN lifecycle terminals."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import get_service

from .adapters.local_can_lifecycle import LocalCanLifecycleStore
from .adapters.training_run_store import _insert_record
from .can_dataset_binding import DATASET_TOOL_IDENTITY, resolve_training_bundle
from .can_evals_binding import EVALS_TOOL_IDENTITY
from .can_evaluation_request import build_evaluation_record_request
from .can_lifecycle_canonical import (
    CONFORM_OPERATION, ISSUE_OPERATION, PROJECT_OPERATION, PROMOTE_OPERATION,
    TRAIN_OPERATION,
)
from .can_lifecycle_ports import CanLifecycleStore
from .training_lifecycle_coordinator import TrainingLifecycleCoordinator
from .can_family_specs import family_spec
from .can_lifecycle_results import (
    CanConformanceResult, CanPassportResult, CanProjectResult, CanTrainResult,
)
from .can_lightgbm_operation import EVALUATOR_TOOL, EVALUATOR_TOOL_IDENTITY, train_portfolio
from .can_native_operation import train_native_portfolio
from .can_passport_operations import issue_passports, promote_passports, run_conformance
from .can_projection import project_pipeline_result
from .passport_composition import create_local_passport_service
from .passport_config import configured_passport_root
from .passport_service import ModelPassportService
from .can_lifecycle_receipts import persist_portfolio_receipts

logger = logging.getLogger(__name__)


class CanLifecycleOperations:
    """Bind durable coordination to Dataset, Evals, trainer, and passport ports."""

    def __init__(
        self, *, root: Path, runtime: Any, invoker: Any,
        passport_service: ModelPassportService, store: CanLifecycleStore,
    ) -> None:
        self.root, self.runtime, self.invoker = root, runtime, invoker
        self.passports = passport_service
        self.coordinator = TrainingLifecycleCoordinator(store)

    def train(self, request: dict[str, Any]) -> dict[str, Any]:
        tools = {
            "dataset": DATASET_TOOL_IDENTITY, "evals": EVALUATOR_TOOL_IDENTITY,
            "self": TRAIN_OPERATION,
        }

        def run(context):
            family = str(request.get("model_family", "lightgbm"))
            family_spec(family)
            top_n = int(request.get("top_n_can_ids", 5))
            if top_n <= 0:
                raise ValueError("top_n_can_ids must be positive")
            dataset_request = dict(request["dataset_request"])
            terminal = context.effect(
                "dataset-training-bundle@v1", {"dataset_request": dataset_request},
                lambda _id: resolve_training_bundle(self.invoker, dataset_request),
                lambda _id: resolve_training_bundle(self.invoker, dataset_request),
            )
            evaluator = lambda **values: self.invoker(EVALUATOR_TOOL, **values)
            common = {
                "context": context, "dataset_terminal": terminal,
                "root": self.root / "models", "evaluator": evaluator,
                "config": dict(request.get("training_config") or {}),
                "experiment_name": str(request.get("experiment_name", "")),
                "top_n": top_n,
            }
            if family == "lightgbm":
                portfolio = train_portfolio(
                    **common, tracker=self.runtime.get_tracker(),
                )
            else:
                portfolio = train_native_portfolio(
                    **common, trainer=self.runtime.get_timeseries_trainer(),
                    family=family, model_config=request.get("model_config"),
                )
            can_ids = [row["can_id"] for row in portfolio]
            return {
                "dataset_terminal": terminal, "portfolio": portfolio,
                "can_ids": can_ids,
                "evaluation_record_request": build_evaluation_record_request(
                    dataset_terminal=terminal, portfolio=portfolio,
                    experiment_name=str(request.get("experiment_name", "")),
                ),
            }

        terminal = self.coordinator.run(TRAIN_OPERATION, request, tools, run, CanTrainResult)
        persist_portfolio_receipts(terminal)
        return terminal

    def issue(self, request: dict[str, Any]) -> dict[str, Any]:
        tools = {"evals": EVALS_TOOL_IDENTITY, "self": ISSUE_OPERATION}

        def run(context):
            terminal = context.completed_terminal(
                request["training_terminal_ref"], TRAIN_OPERATION,
            )
            return issue_passports(
                context, training_terminal=terminal,
                evaluation_pointers=request["evaluation_pointers"], invoker=self.invoker,
                service=self.passports, passport_root=self.root,
            )

        return self.coordinator.run(ISSUE_OPERATION, request, tools, run, CanPassportResult)

    def conform(self, request: dict[str, Any]) -> dict[str, Any]:
        tools = {"evals": EVALS_TOOL_IDENTITY, "self": CONFORM_OPERATION}
        return self.coordinator.run(
            CONFORM_OPERATION, request, tools,
            lambda context: run_conformance(
                context, passport_refs=request["passport_refs"], invoker=self.invoker,
                service=self.passports,
            ), CanConformanceResult,
        )

    def promote(self, request: dict[str, Any]) -> dict[str, Any]:
        tools = {"evals": EVALS_TOOL_IDENTITY, "self": PROMOTE_OPERATION}
        return self.coordinator.run(
            PROMOTE_OPERATION, request, tools,
            lambda context: promote_passports(
                context, conformance_receipt_refs=request["conformance_receipt_refs"],
                invoker=self.invoker, service=self.passports,
            ), CanPassportResult,
        )

    def project(self, request: dict[str, Any]) -> dict[str, Any]:
        tools = {"self": PROJECT_OPERATION}

        def run(context):
            training = context.completed_terminal(
                request["training_terminal_ref"], TRAIN_OPERATION,
            )
            promotion = context.completed_terminal(
                request["promotion_terminal_ref"], PROMOTE_OPERATION,
            )
            return project_pipeline_result(
                training_terminal=training, promotion_terminal=promotion,
                service=self.passports,
            )

        return self.coordinator.run(PROJECT_OPERATION, request, tools, run, CanProjectResult)


def create_can_lifecycle(runtime: Any, root: str | Path | None = None) -> CanLifecycleOperations:
    trust_root = configured_passport_root(root)
    invoker = get_service("tool_invoker")
    if invoker is None:
        raise ValueError("tool_invoker unavailable for ML CAN lifecycle")
    service = runtime._passport_service or create_local_passport_service(trust_root)
    return CanLifecycleOperations(
        root=trust_root, runtime=runtime, invoker=invoker, passport_service=service,
        store=LocalCanLifecycleStore(trust_root),
    )


__all__ = ["CanLifecycleOperations", "create_can_lifecycle"]
