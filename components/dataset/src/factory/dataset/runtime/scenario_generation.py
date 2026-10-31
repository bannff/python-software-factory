"""Deterministic complete outcome-conditioned episode generation."""
from __future__ import annotations

import hashlib
from typing import Any

from pydantic import Field, field_validator

from .scenario_codec import canonical_json
from .scenario_errors import ScenarioGenerationError
from .scenario_models import (
    ScenarioEpisodeLineage, ScenarioPack, ScenarioPackGenerationInput,
    ScenarioPackLineage,
)
from .scenario_pack_models import FrozenModel, ScenarioOutcome, ScenarioStep, digest, token

SUPPORTED_ADAPTER = "dataset.deterministic-template"
SUPPORTED_VERSION = "1.0"


class GeneratedEpisode(FrozenModel):
    episode_id: str
    scenario_id: str
    outcome_id: str
    ordinal: int = Field(strict=True, ge=0)
    split_group: str
    seed: int = Field(strict=True, ge=0, le=2**63 - 1)
    messages: tuple[ScenarioStep, ...] = Field(min_length=3)
    terminal_outcome: ScenarioOutcome
    digest: str

    @field_validator("episode_id", "scenario_id", "outcome_id", "split_group")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "generated episode field")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "generated episode")


def _hash_text(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode()).hexdigest()


def _episode_body(pack: ScenarioPack, scenario, outcome, seed: int, ordinal: int) -> dict[str, Any]:
    key = _hash_text(pack.digest, seed, scenario.scenario_id, outcome.outcome_id, ordinal)
    messages = [{"role": "system", "content": scenario.setup}]
    messages.extend(step.model_dump(mode="json") for step in scenario.steps)
    messages.append({"role": "assistant", "content": outcome.definition})
    return {
        "episode_id": f"episode-{key[:24]}",
        "scenario_id": scenario.scenario_id,
        "outcome_id": outcome.outcome_id,
        "ordinal": ordinal,
        "split_group": f"scenario-{_hash_text(pack.digest, scenario.scenario_id)[:24]}",
        "seed": int(key[:16], 16) & (2**63 - 1),
        "messages": messages,
        "terminal_outcome": outcome.model_dump(mode="json"),
    }


def _validate_generation(pack: ScenarioPack, request: ScenarioPackGenerationInput) -> None:
    ref = request.scenario_pack
    if (ref.identity, ref.version, ref.digest) != (pack.identity, pack.version, pack.digest):
        raise ScenarioGenerationError("ScenarioPack generation reference mismatch")
    rule = pack.generation_rule
    if (request.generator_adapter, request.generator_version) != (rule.adapter, rule.version):
        raise ScenarioGenerationError(
            "Generator adapter/version does not match ScenarioPack generation rule"
        )
    if (request.generator_adapter, request.generator_version) != (
        SUPPORTED_ADAPTER, SUPPORTED_VERSION,
    ):
        raise ScenarioGenerationError(
            "Unsupported deterministic ScenarioPack generator adapter/version"
        )


def generate_episodes(
    pack: ScenarioPack, request: ScenarioPackGenerationInput,
) -> tuple[list[dict[str, Any]], ScenarioPackLineage]:
    """Generate and validate every scenario/outcome/ordinal before publication."""
    _validate_generation(pack, request)
    outcomes = {item.outcome_id: item for item in pack.outcomes}
    episodes: list[GeneratedEpisode] = []
    expected: set[tuple[str, str, int]] = set()
    for scenario in sorted(pack.scenarios, key=lambda item: item.scenario_id):
        for outcome_id in sorted(scenario.outcome_ids):
            for ordinal in range(pack.generation_rule.episodes_per_outcome):
                expected.add((scenario.scenario_id, outcome_id, ordinal))
                body = _episode_body(pack, scenario, outcomes[outcome_id], request.seed, ordinal)
                episodes.append(GeneratedEpisode.model_validate({
                    **body, "digest": hashlib.sha256(canonical_json(body)).hexdigest(),
                }))
    _validate_episode_batch(pack, episodes, expected)
    scenarios = {item.scenario_id: item for item in pack.scenarios}
    lineage = ScenarioPackLineage(
        scenario_pack=request.scenario_pack,
        sources=tuple(sorted(pack.sources, key=lambda item: item.source_id)),
        assumptions=tuple(sorted(pack.assumptions, key=lambda item: item.assumption_id)),
        generator_adapter=request.generator_adapter,
        generator_version=request.generator_version,
        seed=request.seed,
        episodes=tuple(ScenarioEpisodeLineage(
            episode_id=item.episode_id, episode_digest=item.digest,
            scenario_id=item.scenario_id, outcome_id=item.outcome_id,
            ordinal=item.ordinal, derived_seed=item.seed, split_group=item.split_group,
            claim_ids=scenarios[item.scenario_id].claim_ids,
            assumption_ids=scenarios[item.scenario_id].assumption_ids,
        ) for item in episodes),
    )
    return [item.model_dump(mode="json") for item in episodes], lineage


def _validate_episode_batch(
    pack: ScenarioPack,
    episodes: list[GeneratedEpisode],
    expected: set[tuple[str, str, int]],
) -> None:
    actual = {(item.scenario_id, item.outcome_id, item.ordinal) for item in episodes}
    if len(episodes) != len(expected) or actual != expected:
        raise ScenarioGenerationError(
            "Generated episode scenario/outcome/ordinal coverage is incomplete"
        )
    if len({item.episode_id for item in episodes}) != len(episodes):
        raise ScenarioGenerationError("Generated episode IDs must be unique")
    for item in episodes:
        body = item.model_dump(mode="json", exclude={"digest"})
        if hashlib.sha256(canonical_json(body)).hexdigest() != item.digest:
            raise ScenarioGenerationError("Generated episode digest mismatch")
        if item.terminal_outcome.outcome_id != item.outcome_id:
            raise ScenarioGenerationError("Generated terminal outcome is inconsistent")
        expected_group = f"scenario-{_hash_text(pack.digest, item.scenario_id)[:24]}"
        if item.split_group != expected_group:
            raise ScenarioGenerationError("Generated split group is inconsistent")


def validate_scenario_lineage(
    records: list[Any], lineage: ScenarioPackLineage | None,
) -> None:
    """Bind checkpoint/manifest lineage to the exact generated episode batch."""
    if lineage is None:
        raise ScenarioGenerationError("Scenario generation lineage is missing")
    if len(records) != len(lineage.episodes):
        raise ScenarioGenerationError("Scenario lineage episode count mismatch")
    by_id = {
        item.get("episode_id"): item for item in records if isinstance(item, dict)
    }
    if len(by_id) != len(records):
        raise ScenarioGenerationError("Scenario episode records must have unique IDs")
    for episode in lineage.episodes:
        record = by_id.get(episode.episode_id)
        if record is None:
            raise ScenarioGenerationError("Scenario lineage references a missing episode")
        body = {key: value for key, value in record.items() if key != "digest"}
        actual_digest = hashlib.sha256(canonical_json(body)).hexdigest()
        expected = (
            episode.episode_digest, episode.scenario_id, episode.outcome_id,
            episode.ordinal, episode.derived_seed, episode.split_group,
        )
        actual = (
            record.get("digest"), record.get("scenario_id"), record.get("outcome_id"),
            record.get("ordinal"), record.get("seed"), record.get("split_group"),
        )
        if actual != expected or actual_digest != episode.episode_digest:
            raise ScenarioGenerationError("Scenario episode lineage is inconsistent")


def validate_scenario_lineage_against_pack(
    records: list[Any], lineage: ScenarioPackLineage | None, pack: ScenarioPack,
) -> None:
    """Require all record-backed and provenance-only lineage to match the pack."""
    validate_scenario_lineage(records, lineage)
    assert lineage is not None
    generation = ScenarioPackGenerationInput(
        scenario_pack=lineage.scenario_pack,
        generator_adapter=lineage.generator_adapter,
        generator_version=lineage.generator_version,
        seed=lineage.seed,
    )
    expected_records, expected_lineage = generate_episodes(pack, generation)
    if records != expected_records or lineage != expected_lineage:
        raise ScenarioGenerationError("Scenario lineage does not match canonical pack")
