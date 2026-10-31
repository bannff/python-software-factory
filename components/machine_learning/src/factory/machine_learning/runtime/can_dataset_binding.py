"""MCP-only binding to Dataset's completed CAN training bundle terminal."""
from __future__ import annotations

from typing import Any

DATASET_TOOL = "dataset_materialize_can_training_bundle"
DATASET_TOOL_IDENTITY = "dataset.materialize-can-training-bundle@v1"


def resolve_training_bundle(
    invoker: Any, dataset_request: dict[str, Any],
) -> dict[str, Any]:
    """Replay Dataset ownership and require its exact completed bundle."""
    result = invoker(DATASET_TOOL, **dataset_request)
    if not isinstance(result, dict) or result.get("schema_version") != "v1":
        raise ValueError(f"Dataset terminal returned an invalid MCP result: {result}")
    if result.get("ok") is not True or not isinstance(result.get("data"), dict):
        raise ValueError(f"Dataset training bundle request failed: {result.get('error')}")
    response = result["data"]
    if response.get("status") != "completed":
        raise ValueError(f"Dataset training bundle is not completed: {response}")
    bundle = response.get("training_bundle")
    artifacts = response.get("artifacts")
    legacy = response.get("legacy_projection")
    if (
        not isinstance(bundle, dict) or bundle.get("schema_version") != "1.0"
        or not isinstance(artifacts, dict) or not isinstance(legacy, dict)
        or not isinstance(bundle.get("training_artifacts_by_can_id"), dict)
        or response.get("vehicle_id") != bundle.get("vehicle_id")
    ):
        raise ValueError("Dataset completed terminal has invalid trusted bindings")
    return response


def exact_training_refs(
    terminal: dict[str, Any], can_id: str, model_family: str = "lightgbm",
) -> dict[str, dict[str, Any]]:
    """Return the family's exact immutable Dataset refs."""
    from .can_family_specs import family_spec
    refs = terminal["training_bundle"]["training_artifacts_by_can_id"].get(can_id)
    required = family_spec(model_family).required_refs
    if not isinstance(refs, dict) or not required.issubset(refs):
        raise ValueError(
            f"Dataset training refs are incomplete for {model_family}/{can_id}"
        )
    result = {name: refs[name] for name in sorted(required)}
    for name, ref in result.items():
        if (
            not isinstance(ref, dict) or set(ref) != {"uri", "sha256", "evidence"}
            or ref.get("evidence") != {"sha256": ref.get("sha256")}
        ):
            raise ValueError(f"Dataset exact ref is invalid: {can_id}/{name}")
    return result


__all__ = [
    "DATASET_TOOL", "DATASET_TOOL_IDENTITY", "exact_training_refs",
    "resolve_training_bundle",
]
