"""Stateful model for validate, materialize, replay, conflict, and tamper."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from factory.dataset.interface import (
    dataset_get_job,
    dataset_materialize_blueprint,
    dataset_validate_blueprint,
)
from factory.dataset.runtime.blueprint_codec import blueprint_binding

from .blueprint_fixtures import approval_for, blueprint, environment_payloads


class BlueprintLifecycleMachine(RuleBasedStateMachine):
    """Shadow the one-identity immutable blueprint lifecycle."""

    def __init__(self) -> None:
        super().__init__()
        self.root = Path(tempfile.mkdtemp()) / "store"
        self.value = blueprint(self.root)
        self.divergent = blueprint(self.root, seed=42)
        self.approval = approval_for(self.value)[1]
        self.divergent_approval = approval_for(self.divergent)[1]
        self.job_id: str | None = None
        self.ref = None
        self.tampered = False
        self._env = patch.dict(os.environ, environment_payloads(self.value, self.divergent))
        self._submit = patch(
            "factory.dataset.interface.LocalDatasetExecutor.submit", lambda *_: None,
        )
        self._env.start()
        self._submit.start()

    @rule()
    def validate_without_writes(self) -> None:
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}
        result = dataset_validate_blueprint(self.value, self.root)
        assert result.binding == blueprint_binding(self.value)
        assert {path.relative_to(self.root) for path in self.root.rglob("*")} == before

    @precondition(lambda self: not self.tampered)
    @rule()
    def materialize_or_replay(self) -> None:
        result = dataset_materialize_blueprint(self.value, self.approval, self.root)
        assert result.status == "queued"
        if self.job_id is None:
            self.job_id, self.ref = result.job_id, result.blueprint
        else:
            assert (result.job_id, result.blueprint) == (self.job_id, self.ref)

    @precondition(lambda self: self.job_id is not None and not self.tampered)
    @rule()
    def divergent_identity_conflicts_without_effects(self) -> None:
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}
        result = dataset_materialize_blueprint(
            self.divergent, self.divergent_approval, self.root,
        )
        assert result.status == "conflict"
        assert result.conflict is not None
        assert result.conflict.existing_digest == self.ref.digest
        assert {path.relative_to(self.root) for path in self.root.rglob("*")} == before

    @precondition(lambda self: self.job_id is not None and not self.tampered)
    @rule()
    def tamper_fails_before_replay(self) -> None:
        binding = blueprint_binding(self.value)
        artifact = self.root / "blueprints" / "sha256" / f"{binding.digest}.json"
        artifact.chmod(0o644)
        artifact.write_bytes(b"{}")
        jobs_before = list((self.root / "jobs").glob("*.json"))
        with pytest.raises(ValueError):
            dataset_materialize_blueprint(self.value, self.approval, self.root)
        assert list((self.root / "jobs").glob("*.json")) == jobs_before
        self.tampered = True

    @invariant()
    def public_job_matches_shadow_model(self) -> None:
        jobs = list((self.root / "jobs").glob("*.json"))
        if self.job_id is None:
            assert not jobs
        else:
            assert len(jobs) == 1
            status = dataset_get_job(self.job_id, self.root)
            assert status is not None and status.status == "queued"

    def teardown(self) -> None:
        self._submit.stop()
        self._env.stop()
        shutil.rmtree(self.root.parent, ignore_errors=True)


TestBlueprintLifecycle = BlueprintLifecycleMachine.TestCase
TestBlueprintLifecycle.settings = settings(max_examples=20, stateful_step_count=10)
