"""SageMaker run/metric/artifact methods — mixin for SageMakerTracker.

Kept separate from aws.py to stay under 200 LOC per file.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from typing import Any

from ..ports import Dataset, Run

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,256}$")


def _validate_name(value: str, label: str = "name") -> str:
    if not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


class SageMakerRunsMixin:
    """Run, metric, artifact, and dataset methods for SageMaker adapter.

    Expects self._client and self._runs from SageMakerTracker.
    """

    def start_run(
        self, experiment_id: str, name: str = "", tags: dict[str, str] | None = None,
    ) -> Run:
        _validate_name(experiment_id, "experiment_id")
        run_name = name or f"run-{uuid.uuid4().hex[:8]}"
        _validate_name(run_name, "run name")
        self._client.create_trial(  # type: ignore[attr-defined]
            TrialName=run_name,
            ExperimentName=experiment_id,
            Tags=[{"Key": k, "Value": v} for k, v in (tags or {}).items()],
        )
        run = Run(id=run_name, experiment_id=experiment_id, name=run_name,
                  status="running", tags=tags or {})
        self._runs[run_name] = run  # type: ignore[attr-defined]
        return run

    def end_run(self, run_id: str, status: str = "completed") -> Run:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.status = status
            run.ended_at = datetime.now()
        return run

    def get_run(self, run_id: str) -> Run | None:
        cached = self._runs.get(run_id)  # type: ignore[attr-defined]
        if cached:
            return cached
        try:
            resp = self._client.describe_trial(TrialName=run_id)  # type: ignore[attr-defined]
            return Run(id=run_id, experiment_id=resp.get("ExperimentName", ""),
                       name=run_id, status="completed")
        except Exception:
            return None

    def list_runs(self, experiment_id: str | None = None) -> list[Run]:
        try:
            kwargs: dict[str, Any] = {}
            if experiment_id:
                kwargs["ExperimentName"] = experiment_id
            resp = self._client.list_trials(**kwargs)  # type: ignore[attr-defined]
            return [
                Run(id=t["TrialName"], experiment_id=experiment_id or "",
                    name=t["TrialName"])
                for t in resp.get("TrialSummaries", [])
            ]
        except Exception:
            return list(self._runs.values())  # type: ignore[attr-defined]

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.params[key] = value

    def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.params.update(params)

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.metrics[key] = value

    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = 0) -> None:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.metrics.update(metrics)

    def log_artifact(self, run_id: str, artifact_path: str) -> None:
        run = self._runs.get(run_id)  # type: ignore[attr-defined]
        if run:
            run.artifacts.append(artifact_path)

    def register_dataset(
        self, name: str, version: str, path: str,
        metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        digest = hashlib.sha256(f"{name}:{version}:{path}".encode()).hexdigest()[:16]
        ds = Dataset(id=str(uuid.uuid4()), name=name, version=version,
                     path=path, digest=digest, metadata=metadata or {})
        self._datasets[f"{name}:{version}"] = ds  # type: ignore[attr-defined]
        return ds

    def get_dataset(self, name: str, version: str | None = None) -> Dataset | None:
        if version:
            return self._datasets.get(f"{name}:{version}")  # type: ignore[attr-defined]
        matching = [d for k, d in self._datasets.items()  # type: ignore[attr-defined]
                    if k.startswith(f"{name}:")]
        return matching[-1] if matching else None
