"""Dataset-owned CAN stage composition for the synchronous terminal."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from .can_terminal_artifacts import (
    DEFAULT_PRIOR_CONTEXT, bind_training_refs, build_terminal, load_contract_refs,
    load_profile, publish_sample, stage_artifacts,
)
from .can_terminal_canonical import CanonicalCanRequest
from .can_terminal_models import CanTerminalRequest
from .can_terminal_prepare import prepare_training_bundle
from .can_terminal_stage import CanTerminalStageRunner
from .helpers import load_records_from_uri
from .failure_pattern_scenario import failure_scenario_artifacts, failure_scenario_bundle, publish_failure_scenarios

_RECIPES = {
    "ingest": "recipe://local/can-ingest@1", "profile": "recipe://local/can-profile@1",
    "synthesize": "recipe://local/can-synthesize@1", "window": "recipe://local/can-window@2",
    "augment": "recipe://local/can-augment@1",
    "context_ingest": "recipe://local/context-ingest@1",
    "context_augment": "recipe://local/context-augment@1",
    "context_correlate": "recipe://local/context-correlate@1",
    "prior_data_policy": "recipe://local/can-prior-policy@1",
    "signal_schema": "recipe://local/can-signal-schema@1",
}

class CanTerminalPipeline:
    """Compose existing Dataset recipes into the causal ML handoff bundle."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def run(
        self, request: CanTerminalRequest, canonical: CanonicalCanRequest,
    ) -> dict[str, Any]:
        runner = CanTerminalStageRunner(
            self.root, request.attempt_id, canonical.request_sha256,
        )
        overrides = request.config_overrides
        stages: dict[str, dict[str, Any]] = {}
        ingest_config = {
            **dict(overrides.get("ingest") or {}),
            "dbc_path": str(canonical.dbc_path), "vehicle_id": request.vehicle_id,
            "dbc_definition": canonical.dbc_definition.model_dump(mode="json"),
        }
        stages["ingest"] = runner.run(
            "ingest", _RECIPES["ingest"],
            [path.as_uri() for path in canonical.mf4_paths], ingest_config,
        )
        stages["profile"] = runner.run(
            "profile", _RECIPES["profile"], [stages["ingest"]["dataset_uri"]],
            dict(overrides.get("profile") or {}), input_roles=["primary_dataset"],
        )
        profile, profile_digest = load_profile(stages["profile"]["dataset_uri"])
        source_uri = stages["ingest"]["dataset_uri"]
        context_jobs: dict[str, str] = {}
        context_uris: dict[str, str] = {}
        if request.use_context:
            source_uri, context_jobs, context_uris = self._context(
                runner, request, canonical, stages,
            )
        records = load_records_from_uri(source_uri)
        sampled = _reservoir(records, request.max_samples)
        sampled_uri, sampled_artifact = publish_sample(
            sampled, self.root, request.vehicle_id,
        )
        scenario_values = publish_failure_scenarios(
            self.root, request.failure_pattern_refs,
        ) if request.failure_pattern_refs else ()
        synth_config = {
            **dict(overrides.get("synthesize") or {}),
            "vehicle_id": request.vehicle_id, "constraint_schema": profile,
        }
        if request.failure_pattern_refs:
            synth_config.update({
                "failure_pattern_refs": [item.model_dump(mode="json") for item in request.failure_pattern_refs],
                "failure_scenario_refs": [item.scenario_pack.model_dump(mode="json")
                                          for item in scenario_values],
                "dbc_definition": canonical.dbc_definition.model_dump(mode="json"),
            })
        stages["synthesize"] = runner.run(
            "synthesize", _RECIPES["synthesize"], [sampled_uri], synth_config,
            input_roles=["primary_dataset"],
        )
        contracts = self._contracts(
            runner, request, profile, profile_digest, stages,
        )
        policy, schemas, policy_ref, schema_refs = load_contract_refs(contracts)
        schema_items = sorted(schema_refs.items())
        window_config = {
            "window_size_ms": 5000, "step_size_ms": 5000,
            "grid_resolution_ms": 10, "observation_cutoff_ms": 5000,
            "label_horizon_ms": 1000, "emit_timespans": request.emit_timespans,
            **dict(overrides.get("window") or {}),
        }
        stages["window"] = runner.run(
            "window", _RECIPES["window"], [
                stages["synthesize"]["dataset_uri"],
                contracts["prior_data_policy"]["dataset_uri"],
                *[contracts[f"signal_schema:{can_id}"]["dataset_uri"]
                  for can_id, _ in schema_items],
            ], window_config, input_roles=[
                "primary_dataset", "prior_data_policy",
                *[f"signal_schema:{can_id}" for can_id, _ in schema_items],
            ],
        )
        stages["augment"] = runner.run(
            "augment", _RECIPES["augment"], [stages["window"]["dataset_uri"]],
            dict(overrides.get("augment") or {}), input_roles=["primary_dataset"],
        )
        all_stages = {**stages, **contracts}
        bundle, prepared_artifacts = prepare_training_bundle(
            augmented_uri=stages["augment"]["dataset_uri"],
            augmented_digest=stages["augment"]["digest"], policy=policy,
            policy_ref=policy_ref, schemas=schemas, schema_refs=schema_refs,
            root=self.root, request_sha256=canonical.request_sha256,
        )
        artifacts = stage_artifacts(all_stages)
        artifacts.update(failure_scenario_artifacts(scenario_values))
        artifacts["sampled_can"] = sampled_artifact
        artifacts.update(prepared_artifacts)
        bundle.update(failure_scenario_bundle(scenario_values))
        bundle.update({
            "augmented_dataset_artifact": "augment:dataset",
            "augmented_manifest_artifact": "augment:manifest",
            "context_artifacts": {
                key: f"{key}:dataset" for key in sorted(context_uris)
            },
        })
        bind_training_refs(bundle, artifacts, request.vehicle_id, context_uris)
        return build_terminal(
            request=request, canonical=canonical, stages=all_stages,
            contracts=contracts, bundle=bundle, artifacts=artifacts,
            context_jobs=context_jobs, context_uris=context_uris,
        )

    def _context(self, runner, request, canonical, stages):
        overrides = request.config_overrides
        sources = [path.as_uri() for path in canonical.context_paths]
        stages["context_ingest"] = runner.run(
            "context_ingest", _RECIPES["context_ingest"],
            [stages["ingest"]["dataset_uri"], *sources],
            {**dict(overrides.get("context_ingest") or {}),
             "vehicle_id": request.vehicle_id},
            input_roles=["decoded_can", *[f"context_source:{i}" for i in range(len(sources))]],
        )
        stages["context_augment"] = runner.run(
            "context_augment", _RECIPES["context_augment"], [
                stages["ingest"]["dataset_uri"], stages["context_ingest"]["dataset_uri"],
            ], dict(overrides.get("context_augment") or {}),
            input_roles=["decoded_can", "environment_context"],
        )
        stages["context_correlate"] = runner.run(
            "context_correlate", _RECIPES["context_correlate"],
            [stages["context_augment"]["dataset_uri"]],
            dict(overrides.get("context_correlate") or {}),
            input_roles=["context_augmented_can"],
        )
        jobs = {name: stages[name]["job_id"] for name in (
            "context_ingest", "context_augment", "context_correlate",
        )}
        uris = {name: stages[name]["dataset_uri"] for name in jobs}
        return stages["context_augment"]["dataset_uri"], jobs, uris

    def _contracts(self, runner, request, profile, profile_digest, stages):
        contracts = {}
        for can_id in sorted(map(str, profile["can_ids"])):
            role = f"signal_schema:{can_id}"
            contracts[role] = runner.run(
                role, _RECIPES["signal_schema"], [stages["profile"]["dataset_uri"]],
                {"can_id": can_id, "source_digests": [profile_digest]},
                input_roles=["primary_dataset"],
            )
        context_config = request.config_overrides.get("context_augment") or {}
        raw_columns = context_config.get("context_fields")
        default_columns = DEFAULT_PRIOR_CONTEXT if request.use_context else []
        columns = list(default_columns if raw_columns is None else raw_columns)
        contracts["prior_data_policy"] = runner.run(
            "prior_data_policy", _RECIPES["prior_data_policy"], [],
            {"use_context": request.use_context,
             "prior_data_allowlist": sorted(set(columns))},
        )
        return contracts

def _reservoir(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(records) <= limit:
        return list(records)
    rng = random.Random(42)
    result = list(records[:limit])
    for index, record in enumerate(records[limit:], start=limit):
        target = rng.randint(0, index)
        if target < limit:
            result[target] = record
    return result

__all__ = ["CanTerminalPipeline"]
