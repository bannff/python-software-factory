"""Compile approved failure patterns into canonical ScenarioPack artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .adapters.failure_pattern_store import LocalFailurePatternStore
from .failure_pattern_models import FailurePatternRef, FailurePatternSpec
from .scenario_models import ScenarioPackDraft, ScenarioPackRef
from .scenario_codec import parse_scenario_pack
from .scenario_store import LocalScenarioPackStore
from .atomic_io import read_bytes_no_follow
from .recipe import path_from_uri


@dataclass(frozen=True)
class FailureScenarioArtifact:
    pattern: FailurePatternRef
    scenario_pack: ScenarioPackRef


def pattern_scenario_draft(pattern: FailurePatternSpec) -> ScenarioPackDraft:
    """Map one pattern into the repository's validated ScenarioPack contract."""
    evidence_ids = tuple(item.evidence_id for item in pattern.evidence)
    role_names = ", ".join(item.role for item in pattern.roles)
    return ScenarioPackDraft.model_validate({
        "identity": f"can-failure-{pattern.pattern_id}", "version": pattern.version,
        "sources": [{
            "source_id": item.source_id, "uri": item.source_url,
            "digest": item.source_digest, "license": item.spdx_license,
            "version": item.version,
        } for item in pattern.sources],
        "evidence": [item.model_dump(mode="json") for item in pattern.evidence],
        "claims": [{
            "claim_id": "pattern-semantics",
            "statement": f"{pattern.title} applies to semantic roles: {role_names}",
            "evidence_ids": evidence_ids,
        }],
        "assumptions": [{
            "assumption_id": "approved-dbc-binding",
            "statement": "Every semantic role is bound to one signal in the approved DBC.",
        }],
        "outcomes": [{
            "outcome_id": "actual-mutation",
            "definition": "Positive labels are emitted only for observed value mutations.",
        }],
        "scenarios": [{
            "scenario_id": pattern.pattern_id, "title": pattern.title,
            "setup": "Compile the approved pattern against observed CAN profile constraints.",
            "steps": [
                {"role": "user", "content": "Apply the bound deterministic pattern."},
                {"role": "assistant", "content": "Emit mutation-derived labels and lineage."},
            ],
            "claim_ids": ["pattern-semantics"],
            "assumption_ids": ["approved-dbc-binding"],
            "outcome_ids": ["actual-mutation"],
        }],
        "generation_rule": {
            "adapter": "can-failure-pattern", "version": "1.0.0",
            "episodes_per_outcome": 1,
        },
    })


def failure_scenario_artifacts(
    values: tuple[FailureScenarioArtifact, ...],
) -> dict[str, dict]:
    artifacts = {}
    for item in values:
        content = read_bytes_no_follow(path_from_uri(item.scenario_pack.uri))
        digest = hashlib.sha256(content).hexdigest()
        key = f"failure_pattern:{item.pattern.pattern_id}@{item.pattern.version}"
        artifacts[key] = {
            "uri": item.scenario_pack.uri, "sha256": digest,
            "evidence": {"sha256": digest},
        }
    return artifacts


def failure_scenario_bundle(
    values: tuple[FailureScenarioArtifact, ...],
) -> dict[str, dict]:
    return {
        "failure_pattern_artifacts": {
            item.pattern.pattern_id:
                f"failure_pattern:{item.pattern.pattern_id}@{item.pattern.version}"
            for item in values
        },
        "failure_scenario_refs": {
            item.pattern.pattern_id: item.scenario_pack.model_dump(mode="json")
            for item in values
        },
    }


def verify_failure_scenario(ref: ScenarioPackRef) -> None:
    """Verify the exact ScenarioPack artifact carried into stage execution."""
    path = path_from_uri(ref.uri)
    if path.name != f"{ref.digest}.json" or path.parent.name != "sha256":
        raise ValueError("failure pattern ScenarioPack URI is not content-addressed")
    pack = parse_scenario_pack(read_bytes_no_follow(path))
    if (pack.identity, pack.version, pack.digest) != (
        ref.identity, ref.version, ref.digest,
    ):
        raise ValueError("failure pattern ScenarioPack reference mismatch")


def publish_failure_scenarios(
    root: Path, refs: tuple[FailurePatternRef, ...],
) -> tuple[FailureScenarioArtifact, ...]:
    patterns = LocalFailurePatternStore()
    scenarios = LocalScenarioPackStore(root)
    artifacts: list[FailureScenarioArtifact] = []
    for ref in refs:
        pattern = patterns.load(ref)
        result = scenarios.publish(pattern_scenario_draft(pattern))
        if result.status == "conflict" or result.ref is None:
            raise ValueError(f"failure pattern ScenarioPack conflict: {pattern.pattern_id}")
        artifacts.append(FailureScenarioArtifact(ref, result.ref))
    return tuple(artifacts)


__all__ = [
    "FailureScenarioArtifact", "failure_scenario_artifacts",
    "failure_scenario_bundle", "pattern_scenario_draft",
    "publish_failure_scenarios", "verify_failure_scenario",
]
