"""Dataset artifact resolver backed by the shared MCP tool invoker."""

from __future__ import annotations

from typing import Any, Callable

from ..models import DatasetTrainingInput, ResolvedTrainingDataset


class McpDatasetResolver:
    """Resolve dataset artifacts without importing the dataset brick."""

    def __init__(self, invoker: Callable[..., Any] | None = None) -> None:
        self._invoker = invoker

    def resolve(self, training_input: DatasetTrainingInput) -> ResolvedTrainingDataset:
        invoker = self._invoker or _get_tool_invoker()
        if invoker is None:
            raise RuntimeError("MCP tool invoker is not configured")

        result = invoker(
            "dataset_resolve_artifact", dataset_uri=training_input.dataset_uri,
        )
        if isinstance(result, dict) and "result" in result and len(result) == 1:
            result = result["result"]
        if (
            not isinstance(result, dict)
            or result.get("schema_version") != "v1"
            or result.get("ok") is not True
            or not isinstance(result.get("data"), dict)
        ):
            raise ValueError("dataset resolver returned no verified manifest")
        result = result["data"]

        _require_match(result, "dataset_uri", training_input.dataset_uri)
        _require_match(result, "dataset_digest", training_input.dataset_digest)
        _require_match(result, "manifest_uri", training_input.manifest_uri)
        if training_input.view_name not in result.get("training_views", []):
            raise ValueError(f"dataset view is unavailable: {training_input.view_name}")
        view_versions = result.get("view_schema_versions", {})
        if view_versions.get(training_input.view_name) != training_input.view_schema_version:
            raise ValueError(
                f"dataset view schema mismatch: {training_input.view_name}"
            )
        training_uri = result.get("training_uri")
        if not training_uri:
            raise ValueError("dataset manifest has no training_uri")

        return ResolvedTrainingDataset(
            training_uri=training_uri,
            dataset_uri=training_input.dataset_uri,
            manifest_uri=result["manifest_uri"],
            dataset_digest=training_input.dataset_digest,
            view_name=training_input.view_name,
            view_schema_version=training_input.view_schema_version,
        )


def _get_tool_invoker() -> Callable[..., Any] | None:
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        return invoker if callable(invoker) else None
    except Exception:
        return None


def _require_match(result: dict[str, Any], field: str, expected: Any) -> None:
    actual = result.get(field)
    if not actual or actual != expected:
        raise ValueError(f"dataset manifest {field} mismatch")


def resolve_and_verify(
    resolver: Any, training_input: DatasetTrainingInput | None,
) -> ResolvedTrainingDataset:
    """Resolve a training dataset and verify provenance round-trips intact.

    Shared by fine-tuning adapters (mlx, memory) so the provenance
    contract lives next to the resolver it guards.
    """
    if resolver is None:
        raise RuntimeError(
            "dataset resolution is not configured; refusing to start training"
        )
    if training_input is None:
        raise ValueError("training requires a dataset training input")
    resolved = resolver.resolve(training_input)
    if not isinstance(resolved, ResolvedTrainingDataset):
        raise TypeError("dataset resolver returned an invalid training dataset")
    if (
        resolved.dataset_uri != training_input.dataset_uri
        or resolved.manifest_uri != training_input.manifest_uri
        or resolved.dataset_digest != training_input.dataset_digest
        or resolved.view_name != training_input.view_name
        or resolved.view_schema_version != training_input.view_schema_version
    ):
        raise ValueError("dataset resolver returned mismatched training provenance")
    return resolved
