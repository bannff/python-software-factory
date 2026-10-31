"""TensorBoard adapter for experiment tracking brick.

Writes scalars, params, and text via TensorBoard SummaryWriter.
Experiment/run metadata is kept in-memory (TensorBoard is write-only).
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ports import Experiment, Run, Dataset, TrackerHealth


class TensorBoardTracker:
    """TensorBoard-based experiment tracker adapter.

    Uses ``torch.utils.tensorboard.SummaryWriter`` (or the standalone
    ``tensorboard`` package) to persist scalars and text.  Experiment
    and run metadata is held in-memory because TensorBoard has no
    native concept of experiments/runs as first-class objects.
    """

    def __init__(self, log_dir: str = "runs", **kwargs: Any) -> None:
        self._log_dir = Path(log_dir)
        self._experiments: dict[str, Experiment] = {}
        self._runs: dict[str, Run] = {}
        self._writers: dict[str, Any] = {}
        self._datasets: dict[str, Dataset] = {}

    # -- writer helpers ------------------------------------------------

    def _get_writer(self, run_id: str) -> Any:
        """Lazily create a SummaryWriter for a run."""
        if run_id not in self._writers:
            try:
                from torch.utils.tensorboard import SummaryWriter
            except ImportError:
                try:
                    from tensorboard.summary.writer.event_file_writer import EventFileWriter as SummaryWriter  # noqa: N811
                except ImportError:
                    raise ImportError(
                        "tensorboard required: pip install tensorboard"
                    )
            run = self._runs.get(run_id)
            exp = self._experiments.get(run.experiment_id) if run else None
            sub = f"{exp.name}/{run.name}" if exp and run else run_id
            self._writers[run_id] = SummaryWriter(
                log_dir=str(self._log_dir / sub)
            )
        return self._writers[run_id]

    def _close_writer(self, run_id: str) -> None:
        writer = self._writers.pop(run_id, None)
        if writer and hasattr(writer, "close"):
            writer.close()

    # -- experiments ---------------------------------------------------

    def create_experiment(
        self, name: str, description: str = "", tags: dict[str, str] | None = None,
    ) -> Experiment:
        exp = Experiment(
            id=str(uuid.uuid4()), name=name,
            description=description, tags=tags or {},
        )
        self._experiments[exp.id] = exp
        return exp

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)

    def get_experiment_by_name(self, name: str) -> Experiment | None:
        return next((e for e in self._experiments.values() if e.name == name), None)

    def list_experiments(self) -> list[Experiment]:
        return list(self._experiments.values())

    # -- runs ----------------------------------------------------------

    def start_run(
        self, experiment_id: str, name: str = "", tags: dict[str, str] | None = None,
    ) -> Run:
        run = Run(
            id=str(uuid.uuid4()), experiment_id=experiment_id,
            name=name or f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            status="running", tags=tags or {},
        )
        self._runs[run.id] = run
        return run

    def end_run(self, run_id: str, status: str = "completed") -> Run:
        run = self._runs.get(run_id)
        if run:
            run.status = status
            run.ended_at = datetime.now()
            self._close_writer(run_id)
        return run

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list_runs(self, experiment_id: str | None = None) -> list[Run]:
        runs = list(self._runs.values())
        if experiment_id:
            runs = [r for r in runs if r.experiment_id == experiment_id]
        return runs

    # -- logging -------------------------------------------------------

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        run = self._runs.get(run_id)
        if run:
            run.params[key] = value
            writer = self._get_writer(run_id)
            writer.add_text(f"params/{key}", str(value))

    def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        for k, v in params.items():
            self.log_param(run_id, k, v)

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        run = self._runs.get(run_id)
        if run:
            run.metrics[key] = value
            writer = self._get_writer(run_id)
            writer.add_scalar(key, value, global_step=step)

    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = 0) -> None:
        for k, v in metrics.items():
            self.log_metric(run_id, k, v, step)

    def log_artifact(self, run_id: str, artifact_path: str) -> None:
        run = self._runs.get(run_id)
        if run:
            run.artifacts.append(artifact_path)
            writer = self._get_writer(run_id)
            writer.add_text("artifacts", artifact_path)

    # -- datasets ------------------------------------------------------

    def register_dataset(
        self, name: str, version: str, path: str, metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        digest = hashlib.sha256(f"{name}:{version}:{path}".encode()).hexdigest()[:16]
        ds = Dataset(
            id=str(uuid.uuid4()), name=name, version=version,
            path=path, digest=digest, metadata=metadata or {},
        )
        self._datasets[f"{name}:{version}"] = ds
        return ds

    def get_dataset(self, name: str, version: str | None = None) -> Dataset | None:
        if version:
            return self._datasets.get(f"{name}:{version}")
        matching = [d for k, d in self._datasets.items() if k.startswith(f"{name}:")]
        return matching[-1] if matching else None

    # -- health --------------------------------------------------------

    def health_check(self) -> TrackerHealth:
        start = time.perf_counter()
        try:
            try:
                from torch.utils.tensorboard import SummaryWriter  # noqa: F401
            except ImportError:
                from tensorboard.summary.writer.event_file_writer import EventFileWriter  # noqa: F401
            return TrackerHealth(
                healthy=True, backend="tensorboard",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except ImportError:
            return TrackerHealth(
                healthy=False, backend="tensorboard",
                latency_ms=(time.perf_counter() - start) * 1000,
                message="tensorboard not installed",
            )
