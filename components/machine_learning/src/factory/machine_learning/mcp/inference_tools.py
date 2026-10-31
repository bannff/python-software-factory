"""Typed operational MCP surface for exact-passport CAN inference."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .passport_inference_dtos import (
    CanPredictionInput, CanPredictionOutput, ModelInfoInput, ModelInfoOutput,
    NeuralPassportInput, NeuralPassportOutput, WarmPredictionInput,
)
from ..runtime.passport_inference import (
    ModelNotPromotableError, get_exact_inference_bridge,
)
from ..runtime.runtime import TrackingRuntime

_MAX_NEURAL_PREDICTIONS = 4096


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    @mcp.tool()
    @operational(input_model=CanPredictionInput, output_model=CanPredictionOutput)
    def can_predict_failure(
        records: list[dict[str, Any]], contract_digest: str, model_id: str,
        model_version: str, passport_revision: int, passport_uri: str,
        passport_digest: str,
    ) -> ToolResult[CanPredictionOutput]:
        """Cold-load and score only one exact configured-store passport revision."""
        try:
            request = CanPredictionInput(
                records=records, contract_digest=contract_digest, model_id=model_id,
                model_version=model_version, passport_revision=passport_revision,
                passport_uri=passport_uri, passport_digest=passport_digest,
            )
            value = get_exact_inference_bridge(get_runtime(), request.ref()).predict_window(
                records, request_digest=contract_digest,
            )
            return CanPredictionOutput.model_construct(
                **value.model_dump(mode="python"),
            )
        except ModelNotPromotableError as exc:
            return fail(str(exc))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @operational(input_model=NeuralPassportInput, output_model=NeuralPassportOutput)
    def ml_predict_neural_passport(
        X_uri: str, model_id: str, model_version: str,
        passport_revision: int, passport_uri: str, passport_digest: str,
        live_timing_uri: str | None = None,
        live_timing_digest: str | None = None,
    ) -> ToolResult[NeuralPassportOutput]:
        """Cold-score one exact neural passport with optional live timing."""
        try:
            import numpy as np
            from ..runtime.adapters.torch_data import load_array
            from ..runtime.live_timing import LiveTimingArtifactRef
            from ..runtime.passport_composition import create_local_passport_service
            from ..runtime.passport_native_inference import load_neural_passport_scores
            request = NeuralPassportInput(
                X_uri=X_uri, model_id=model_id, model_version=model_version,
                passport_revision=passport_revision, passport_uri=passport_uri,
                passport_digest=passport_digest, live_timing_uri=live_timing_uri,
                live_timing_digest=live_timing_digest,
            )
            if (live_timing_uri is None) != (live_timing_digest is None):
                raise ValueError("live timing URI and digest must be supplied together")
            live_timing = None
            if live_timing_uri is not None:
                live_timing = LiveTimingArtifactRef(
                    uri=live_timing_uri, digest=live_timing_digest,
                )
            X = load_array(X_uri)
            if X.ndim != 3 or not 0 < len(X) <= _MAX_NEURAL_PREDICTIONS:
                raise ValueError(f"X must contain 1..{_MAX_NEURAL_PREDICTIONS} 3D windows")
            if not np.issubdtype(X.dtype, np.number) or not np.isfinite(X).all():
                raise ValueError("X must contain only finite numeric values")
            runtime = get_runtime()
            service = runtime._passport_service or create_local_passport_service()
            scores = load_neural_passport_scores(service, request.ref(), X, live_timing)
            timing = None if live_timing is None else {
                "digest": live_timing.digest, "shape": [len(X), X.shape[1]],
            }
            return NeuralPassportOutput(
                passport_ref=request.ref(), count=len(scores),
                y_pred=scores.argmax(axis=1).tolist(), y_score=scores[:, 1].tolist(),
                live_timing=timing,
            )
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool(name="can_predict_failure_warm_compat")
    @operational(input_model=WarmPredictionInput, output_model=CanPredictionOutput)
    def predict_warm_compat(
        records: list[dict[str, Any]], model_id: str, contract_digest: str,
    ) -> ToolResult[CanPredictionOutput]:
        """Non-authoritative warm-cache compatibility path."""
        try:
            value = get_runtime().get_public_inference_bridge(model_id).predict_window(
                records, request_digest=contract_digest,
            )
            return CanPredictionOutput.model_construct(
                **value.model_dump(mode="python"),
            )
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=ModelInfoInput, output_model=ModelInfoOutput)
    def can_get_model_info(model_id: str) -> ToolResult[ModelInfoOutput]:
        """Return non-authoritative warm-cache metadata for compatibility."""
        info = get_runtime().get_inference_model_info(model_id)
        if info is None:
            return ModelInfoOutput(found=False, model_id=model_id)
        return ModelInfoOutput(found=True, **info)


__all__ = ["register"]
