"""Shared fixtures for DatasetBlueprint contract and lifecycle tests."""
from __future__ import annotations

import json
from pathlib import Path

from factory.dataset.interface import dataset_publish_scenario_pack
from factory.dataset.runtime.blueprint_catalog import (
    DETERMINISTIC_TEMPLATE_REF,
    GENERIC_SCHEMA_REF,
    SCENARIO_EVIDENCE_DESCRIPTOR,
    SCENARIO_RECIPE_REF,
    SCENARIO_STAGE_REF,
)
from factory.dataset.runtime.blueprint_codec import approval_digest, canonical_digest
from factory.dataset.runtime.blueprint_models import (
    DatasetBlueprint,
    DatasetHumanApprovalRecord,
    DatasetHumanApprovalRef,
    DatasetQualityPolicyRef,
    DatasetSourceEvidenceRef,
)

from .scenario_fixtures import draft

QUALITY_POLICY = DatasetQualityPolicyRef(
    id="scenario-quality",
    revision="1",
    digest=canonical_digest({"owner": "evals", "policy": "scenario-quality", "revision": "1"}),
)


def blueprint(root: Path, *, seed: int = 41, identity: str = "scenario-blueprint") -> DatasetBlueprint:
    """Publish the non-security ScenarioPack fixture and bind a blueprint to it."""
    published = dataset_publish_scenario_pack(draft(), root)
    assert published.ref is not None
    evidence_id, evidence_version, evidence_digest = SCENARIO_EVIDENCE_DESCRIPTOR
    return DatasetBlueprint(
        identity=identity,
        version="1",
        recipe=SCENARIO_RECIPE_REF,
        stages=(SCENARIO_STAGE_REF,),
        output_schema=GENERIC_SCHEMA_REF,
        source_evidence=(DatasetSourceEvidenceRef(
            id=evidence_id,
            version=evidence_version,
            digest=evidence_digest,
            artifact=published.ref,
        ),),
        capabilities=(DETERMINISTIC_TEMPLATE_REF,),
        quality_policy=QUALITY_POLICY,
        generation_seed=seed,
        requested_views=("default",),
    )


def approval_for(value: DatasetBlueprint, *, approval_id: str | None = None) -> tuple[
    DatasetHumanApprovalRecord, DatasetHumanApprovalRef,
]:
    """Build the exact digest-bound human approval record and opaque reference."""
    record = DatasetHumanApprovalRecord(
        id=approval_id or f"approval-{value.generation_seed}",
        revision="1",
        blueprint_digest=canonical_digest(value),
        quality_policy=value.quality_policy,
    )
    return record, DatasetHumanApprovalRef(
        id=record.id,
        revision=record.revision,
        digest=approval_digest(record),
    )


def configure(monkeypatch, *values: DatasetBlueprint) -> dict[str, DatasetHumanApprovalRef]:
    """Configure exact policy and approval registries for public interface calls."""
    records_and_refs = [approval_for(value) for value in values]
    monkeypatch.setenv(
        "DATASET_QUALITY_POLICY_REFS_JSON",
        json.dumps([QUALITY_POLICY.model_dump(mode="json")]),
    )
    monkeypatch.setenv(
        "DATASET_HUMAN_APPROVALS_JSON",
        json.dumps([record.model_dump(mode="json") for record, _ in records_and_refs]),
    )
    return {value.identity + ":" + str(value.generation_seed): ref
            for value, (_, ref) in zip(values, records_and_refs, strict=True)}


def environment_payloads(*values: DatasetBlueprint) -> dict[str, str]:
    """Return process environment values for state-machine setup."""
    records = [approval_for(value)[0] for value in values]
    return {
        "DATASET_QUALITY_POLICY_REFS_JSON": json.dumps([
            QUALITY_POLICY.model_dump(mode="json"),
        ]),
        "DATASET_HUMAN_APPROVALS_JSON": json.dumps([
            record.model_dump(mode="json") for record in records
        ]),
    }
