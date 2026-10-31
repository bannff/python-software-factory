"""Recipe resolution and canonical input loading for dataset workers."""
from __future__ import annotations

import hashlib
from typing import Any

from .contracts import DatasetGenerationRequest, DatasetRecipe
from .local_inputs import path_from_uri
from .recipe_config import _populate_stage_config
from .recipe_io import load_records, records_content


from .blueprint_catalog import SCENARIO_RECIPE_SPEC, SCENARIO_RECIPE_URI
from .stage_admission import admit_recipe

_CAN_RECIPE_URIS: dict[str, tuple[str, list[dict[str, Any]]]] = {
    SCENARIO_RECIPE_URI: SCENARIO_RECIPE_SPEC,
    # Single-stage CAN recipes — useful for agents that only need one
    # pipeline phase (e.g. can-ingest for raw DBC matching, can-profile
    # for re-profiling an already-materialized artifact).
    "recipe://local/can-ingest@1": ("can-ingest-v1", [{"name": "can_ingest", "config": {}}]),
    "recipe://local/can-profile@1": ("can-profile-v1", [{"name": "can_profile", "config": {}}]),
    "recipe://local/can-synthesize@1": ("can-synthesize-v1", [{"name": "can_synthesize", "config": {}}]),
    "recipe://local/can-window@1": ("can-window-v1", [{"name": "can_window", "config": {}}]),
    "recipe://local/can-window@2": ("can-window-v2", [{"name": "can_window_v2", "config": {}}]),
    "recipe://local/can-prior-policy@1": (
        "can-prior-policy-v1", [{"name": "can_prior_policy", "config": {}}],
    ),
    "recipe://local/can-signal-schema@1": (
        "can-signal-schema-v1", [{"name": "can_signal_schema", "config": {}}],
    ),
    "recipe://local/can-augment@1": ("can-augment-v1", [{"name": "can_augment", "config": {}}]),
    "recipe://local/can-taxonomize@1": ("can-taxonomize-v1", [{"name": "can_taxonomize", "config": {}}]),
    # Context-aware single-stage recipes (context adapters).
    "recipe://local/context-ingest@1": (
        "context-ingest-v1",
        [{"name": "context_ingest", "config": {
            "sources": ["weather_openweathermap", "gps_can", "vehicle_metadata"],
        }}],
    ),
    "recipe://local/context-correlate@1": (
        "context-correlate-v1",
        [{"name": "context_correlate", "config": {
            "method": "pearson", "min_correlation": 0.3,
            "context_features": [
                "temp_c", "humidity_pct", "precipitation_mm",
                "aggressiveness_score", "odometer_km",
                "battery_health_pct", "lat", "lon",
            ],
            "failure_modes": [
                "signal_drift", "drop_to_zero", "out_of_sequence",
                "sensor_degradation", "ecu_timeout", "signal_freeze",
                "spike_noise", "correlation_break",
            ],
        }}],
    ),
    "recipe://local/context-augment@1": (
        "context-augment-v1",
        [{"name": "context_augment", "config": {
            "merge_strategy": "nearest", "max_time_delta_s": 3600,
            "fill_strategy": "last_known",
        }}],
    ),
}

_DEPRECATED_CAN_RECIPE_URIS = frozenset({
    "recipe://local/can-pipeline@1",
    "recipe://local/can-pipeline-aug@1",
    "recipe://local/can-pipeline-tax@1",
    "recipe://local/can-pipeline-timegan@1",
})


def _resolve_local_builtin_recipe(request: DatasetGenerationRequest) -> DatasetRecipe | None:
    """Resolve a built-in ``recipe://local/*`` URI; return ``None`` if not built-in.

    The digest is SHA-256 of the URI string itself (matches the legacy
    ``recipe://local/pass-through@1`` shape so callers can compute it
    deterministically without file I/O).
    """
    expected_digest = hashlib.sha256(request.recipe_uri.encode()).hexdigest()
    if request.recipe_uri in _DEPRECATED_CAN_RECIPE_URIS:
        if request.recipe_digest != expected_digest:
            raise ValueError(f"Digest mismatch for recipe: {request.recipe_uri}")
        raise ValueError(
            f"{request.recipe_uri} is deprecated because linear CAN stage routing is unsafe; "
            "use dataset_materialize_can_training_bundle or explicit single-stage jobs"
        )
    spec = _CAN_RECIPE_URIS.get(request.recipe_uri)
    if spec is None:
        return None
    if request.recipe_digest != expected_digest:
        raise ValueError(f"Digest mismatch for recipe: {request.recipe_uri}")
    version, stages = spec
    mf4_paths = [a.uri for a in request.input_artifacts if a.uri.startswith("file://")]
    jsonl_uris = [a.uri for a in request.input_artifacts if a.uri.endswith(".jsonl")]
    populated = [
        _populate_stage_config(s, request, mf4_paths, jsonl_uris)
        for s in stages
    ]
    artifact_recipes = {
        "recipe://local/can-prior-policy@1",
        "recipe://local/can-signal-schema@1",
    }
    if request.recipe_uri in artifact_recipes:
        record_schema = "can_artifact"
    elif request.recipe_uri == SCENARIO_RECIPE_URI:
        record_schema = "generic"
    else:
        record_schema = "can_frame"
    return DatasetRecipe(
        version=version, stages=populated, record_schema=record_schema,
    )  # type: ignore[arg-type]


def resolve_recipe(request: DatasetGenerationRequest) -> DatasetRecipe:
    """Load and digest-check a versioned recipe before stage execution."""
    from .scenario_request import validate_scenario_request
    validate_scenario_request(request)
    if request.recipe_uri == "recipe://local/pass-through@1":
        expected_digest = hashlib.sha256(request.recipe_uri.encode()).hexdigest()
        if request.recipe_digest != expected_digest:
            raise ValueError(f"Digest mismatch for recipe: {request.recipe_uri}")
        return admit_recipe(
            DatasetRecipe(version="local-pass-through", stages=[{"name": "local-validate"}])
        )

    builtin = _resolve_local_builtin_recipe(request)
    if builtin is not None:
        return admit_recipe(builtin)

    recipe_path = path_from_uri(request.recipe_uri)
    content = recipe_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if request.recipe_digest != digest:
        raise ValueError(f"Digest mismatch for recipe: {request.recipe_uri}")
    try:
        recipe = DatasetRecipe.model_validate_json(content)
    except Exception as error:
        raise ValueError(f"Invalid dataset recipe: {request.recipe_uri}") from error
    return admit_recipe(recipe)
