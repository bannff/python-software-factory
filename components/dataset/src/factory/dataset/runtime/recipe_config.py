"""Built-in recipe config merging and typed artifact routing."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .can_artifact_codec import (
    load_prior_policy, load_signal_schema, ref_from_prior_policy_uri,
    ref_from_signal_schema_uri,
)
from .contracts import DatasetGenerationRequest, DatasetInputRef

_STANDALONE_INPUT_STAGES = frozenset({
    "can_profile", "can_synthesize", "can_window", "can_signal_schema",
    "can_augment", "context_ingest", "context_augment", "context_correlate",
})


def _snapshot_overrides(request: DatasetGenerationRequest, stage_name: str) -> dict[str, Any]:
    if not request.context_snapshot.uri.startswith("file://"):
        return {}
    try:
        from .recipe import path_from_uri
        payload = json.loads(path_from_uri(request.context_snapshot.uri).read_bytes())
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Context snapshot must contain a JSON object")
    stage_overrides = payload.get("stage_overrides", {})
    if not isinstance(stage_overrides, dict):
        raise ValueError("stage_overrides must be an object")
    override = stage_overrides.get(stage_name, {})
    if not isinstance(override, dict):
        raise ValueError(f"Override for {stage_name} must be an object")
    return dict(override)


def _role_ref(
    inputs: list[DatasetInputRef], role: str, *, required: bool = False,
) -> DatasetInputRef | None:
    matches = [item for item in inputs if item.artifact_role == role]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous artifact role {role!r}: {len(matches)} inputs")
    if required and not matches:
        raise ValueError(f"Missing required artifact role {role!r}")
    return matches[0] if matches else None


def _role_uri(inputs: list[DatasetInputRef], role: str, *, required: bool = False) -> str | None:
    match = _role_ref(inputs, role, required=required)
    return match.uri if match else None


def _route(cfg: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    configured = cfg.get(key)
    if configured is not None and configured != value:
        raise ValueError(f"Typed artifact routing conflicts with {key!r}")
    cfg[key] = value


def _verified_input(item: DatasetInputRef) -> bytes:
    from .recipe import path_from_uri
    raw = path_from_uri(item.uri).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item.digest:
        raise ValueError(f"Digest mismatch for input artifact: {item.uri}")
    return raw


def _artifact_routes(inputs: list[DatasetInputRef]) -> dict[str, Any]:
    policy_input = _role_ref(inputs, "prior_data_policy", required=True)
    assert policy_input is not None
    _verified_input(policy_input)
    policy_ref = ref_from_prior_policy_uri(policy_input.uri)
    load_prior_policy(policy_ref)
    schemas: dict[str, dict[str, str]] = {}
    for item in inputs:
        role = item.artifact_role or ""
        if not role.startswith("signal_schema:"):
            continue
        role_can_id = role.split(":", 1)[1]
        if not role_can_id or role_can_id in schemas:
            raise ValueError(f"Invalid or duplicate signal schema role {role!r}")
        _verified_input(item)
        ref = ref_from_signal_schema_uri(item.uri)
        schema = load_signal_schema(ref)
        if schema.can_id != role_can_id:
            raise ValueError("signal schema role CAN-ID disagrees with artifact")
        schemas[role_can_id] = ref.model_dump(mode="json")
    if not schemas:
        raise ValueError("can_window_v2 requires per-CAN signal schema roles")
    return {
        "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
        "signal_schema_refs_by_can_id": dict(sorted(schemas.items())),
    }


def _typed_routes(
    stage_name: str, request: DatasetGenerationRequest,
) -> dict[str, Any]:
    inputs = request.input_artifacts
    if stage_name == "scenario_generate":
        from .scenario_request import validate_scenario_request
        artifact = validate_scenario_request(request)
        generation = request.scenario_generation
        assert artifact is not None and generation is not None
        return {"scenario_generation": generation.model_dump(mode="json")}
    if stage_name == "context_ingest":
        decoded = _role_uri(inputs, "decoded_can")
        source_inputs = [
            item for item in inputs
            if (item.artifact_role or "").startswith("context_source:")
        ]
        roles = [item.artifact_role for item in source_inputs]
        if len(roles) != len(set(roles)):
            raise ValueError("Ambiguous indexed context source role")
        uris = ([decoded] if decoded else []) + [item.uri for item in source_inputs]
        if not uris:
            raise ValueError("context_ingest requires decoded_can or indexed context sources")
        return {"input_uris": uris}
    if stage_name == "context_augment":
        return {
            "input_uri": _role_uri(inputs, "decoded_can", required=True),
            "context_uri": _role_uri(inputs, "environment_context", required=True),
        }
    if stage_name == "context_correlate":
        return {"input_uri": _role_uri(inputs, "context_augmented_can", required=True)}
    if stage_name == "can_window_v2":
        primary = _role_ref(inputs, "primary_dataset", required=True)
        assert primary is not None
        return {"input_uri": primary.uri, **_artifact_routes(inputs)}
    primary = _role_uri(inputs, "primary_dataset")
    return {"input_uri": primary} if primary else {}


def _legacy_routes(stage_name: str, jsonl_uris: list[str]) -> dict[str, str]:
    if stage_name == "context_augment" and len(jsonl_uris) >= 2:
        return {"input_uri": jsonl_uris[0], "context_uri": jsonl_uris[1]}
    if stage_name in _STANDALONE_INPUT_STAGES and jsonl_uris:
        return {"input_uri": jsonl_uris[0]}
    return {}


def _populate_stage_config(
    stage: dict[str, Any], request: DatasetGenerationRequest,
    mf4_paths: list[str], jsonl_uris: list[str],
) -> dict[str, Any]:
    """Merge defaults → immutable overrides → typed artifact routing."""
    name = stage["name"]
    cfg = dict(stage.get("config", {}))
    cfg.update(_snapshot_overrides(request, name))
    if name == "can_ingest":
        if mf4_paths:
            configured = cfg.get("mf4_paths")
            if configured is not None and configured != mf4_paths:
                raise ValueError("Typed artifact routing conflicts with 'mf4_paths'")
            cfg["mf4_paths"] = mf4_paths
    has_roles = any(item.artifact_role is not None for item in request.input_artifacts)
    routes = (
        _typed_routes(name, request)
        if has_roles or name == "scenario_generate"
        else _legacy_routes(name, jsonl_uris)
    )
    for key, value in routes.items():
        _route(cfg, key, value)
    return {"name": name, "config": cfg}


__all__ = ["_populate_stage_config"]
