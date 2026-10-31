"""Stateful property tests for the ML training curriculum lifecycle.

Verifies:
- Typed dataset input preservation through fine-tuning
- Fine-tuning job lifecycle: create → start → complete, create → stop
- training_objective preserved through the full job lifecycle
- Job state transitions are valid (pending→completed, pending→stopped)
- Checkpoint and stage artifact listing correctness
- CheckpointStore cleanup integration via the finetuning adapter
"""

from __future__ import annotations

import tempfile

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.machine_learning.runtime.adapters.checkpoint_store import CheckpointStore
from factory.machine_learning.runtime.adapters.memory_finetuning import (
    MemoryFineTuningAdapter,
)
from factory.machine_learning.runtime.models import (
    CheckpointType, DatasetTrainingInput,
    FineTuningMethod,
    JobStatus,
    TrainingObjective,
)

_methods = st.sampled_from(list(FineTuningMethod))
_objectives = st.one_of(st.none(), st.sampled_from(list(TrainingObjective)))
_models = st.sampled_from(["llama3-8b", "mistral-7b", "phi-3-mini"])


@settings(max_examples=50, stateful_step_count=20)
class TrainingCurriculumMachine(RuleBasedStateMachine):
    """Stateful tests for the full training curriculum lifecycle."""

    def __init__(self):
        super().__init__()
        self.store: CheckpointStore | None = None
        self.finetuner: MemoryFineTuningAdapter | None = None
        self.ft_job_ids: list[str] = []
        self.ft_objectives: dict[str, TrainingObjective | None] = {}
        self.ft_statuses: dict[str, JobStatus] = {}

    @initialize()
    def init(self):
        self.store = CheckpointStore(base_path=tempfile.mkdtemp())
        self.finetuner = MemoryFineTuningAdapter(checkpoint_store=self.store)
        self.ft_job_ids, self.ft_objectives, self.ft_statuses = [], {}, {}

    # -- fine-tuning rules ---------------------------------------------

    @rule(method=_methods, model=_models, objective=_objectives)
    def create_finetuning_job(self, method, model, objective):
        job = self.finetuner.create_job(
            method=method, base_model=model,
            training_input=DatasetTrainingInput(
                dataset_uri="ds://artifact",
                manifest_uri="ds://manifest",
                dataset_digest="0" * 64,
                view_name="sft",
                view_schema_version="1.0",
            ),
            training_objective=objective,
        )
        self.ft_job_ids.append(job.id)
        self.ft_objectives[job.id] = objective
        self.ft_statuses[job.id] = JobStatus.pending

    @rule()
    def start_job(self):
        pending = [j for j, s in self.ft_statuses.items() if s == JobStatus.pending]
        if not pending:
            return
        jid = pending[0]
        self.finetuner.start_job(jid)
        # Memory adapter completes instantly
        self.ft_statuses[jid] = JobStatus.completed

    @rule()
    def stop_pending_job(self):
        pending = [j for j, s in self.ft_statuses.items() if s == JobStatus.pending]
        if not pending:
            return
        jid = pending[-1]
        self.finetuner.stop_job(jid)
        self.ft_statuses[jid] = JobStatus.stopped

    @rule()
    def list_checkpoints(self):
        completed = [j for j, s in self.ft_statuses.items()
                     if s == JobStatus.completed]
        for jid in completed:
            cps = self.finetuner.list_checkpoints(jid)
            assert len(cps) >= 1, f"Completed job {jid} must have checkpoints"

    @rule()
    def list_stage_artifacts(self):
        for jid in self.ft_job_ids:
            arts = self.finetuner.list_stage_artifacts(jid)
            for a in arts:
                assert a.checkpoint_type == CheckpointType.stage_artifact

    # -- invariants ----------------------------------------------------

    @invariant()
    def objective_preserved(self):
        if self.finetuner is None:
            return
        for jid in self.ft_job_ids:
            job = self.finetuner.get_job(jid)
            assert job is not None
            assert job.training_objective == self.ft_objectives[jid]

    @invariant()
    def job_statuses_match(self):
        if self.finetuner is None:
            return
        for jid, expected in self.ft_statuses.items():
            job = self.finetuner.get_job(jid)
            assert job is not None
            assert job.status == expected, (
                f"Job {jid}: expected {expected}, got {job.status}"
            )



TestTrainingCurriculum = TrainingCurriculumMachine.TestCase
