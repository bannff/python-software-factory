"""Shared ScenarioPack fixtures for focused Dataset tests."""
from __future__ import annotations

import hashlib

from factory.dataset.runtime.scenario_models import ScenarioPackDraft


def draft_data(*, episodes_per_outcome: int = 2) -> dict:
    return {
        "identity": "pack-1",
        "version": "1.0",
        "sources": [
            {"source_id": "source-1", "uri": "https://example.test/one",
             "digest": hashlib.sha256(b"one").hexdigest(), "license": "CC-BY-4.0", "version": "1"},
            {"source_id": "source-2", "uri": "https://example.test/two",
             "digest": hashlib.sha256(b"two").hexdigest(), "license": "CC-BY-4.0", "version": "2"},
        ],
        "evidence": [
            {"evidence_id": "evidence-1", "source_id": "source-1",
             "locator": "section-1", "range_start": 0, "range_end": 4},
            {"evidence_id": "evidence-2", "source_id": "source-2",
             "locator": "section-2", "range_start": 4, "range_end": 8},
        ],
        "claims": [
            {"claim_id": "claim-1", "statement": "First claim",
             "evidence_ids": ["evidence-1"]},
            {"claim_id": "claim-2", "statement": "Second claim",
             "evidence_ids": ["evidence-2"]},
        ],
        "assumptions": [
            {"assumption_id": "assumption-1", "statement": "First assumption"},
            {"assumption_id": "assumption-2", "statement": "Second assumption"},
        ],
        "outcomes": [
            {"outcome_id": "outcome-1", "definition": "First outcome"},
            {"outcome_id": "outcome-2", "definition": "Second outcome"},
        ],
        "scenarios": [
            {"scenario_id": "scenario-1", "title": "One", "setup": "Setup one",
             "steps": [{"role": "user", "content": "Act one"}],
             "claim_ids": ["claim-1"], "assumption_ids": ["assumption-1"],
             "outcome_ids": ["outcome-1", "outcome-2"]},
            {"scenario_id": "scenario-2", "title": "Two", "setup": "Setup two",
             "steps": [{"role": "user", "content": "Act two"}],
             "claim_ids": ["claim-2"], "assumption_ids": ["assumption-2"],
             "outcome_ids": ["outcome-1", "outcome-2"]},
        ],
        "generation_rule": {
            "adapter": "dataset.deterministic-template", "version": "1.0",
            "episodes_per_outcome": episodes_per_outcome,
        },
    }


def draft(*, episodes_per_outcome: int = 2) -> ScenarioPackDraft:
    return ScenarioPackDraft.model_validate(
        draft_data(episodes_per_outcome=episodes_per_outcome)
    )
