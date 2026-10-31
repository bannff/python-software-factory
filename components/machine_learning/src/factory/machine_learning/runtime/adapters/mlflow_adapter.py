"""MLflow adapter for experiment tracking brick."""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..ports import Experiment, Run, Dataset, TrackerHealth


class MLflowTracker:
    """MLflow-based experiment tracker adapter."""

    def __init__(self, tracking_uri: str | None = None, **kwargs: Any) -> None:
        self._tracking_uri = tracking_uri
        self._mlflow: Any = None
        self._client: Any = None
        self._datasets: dict[str, Dataset] = {}

    def _get_mlflow(self) -> Any:
        if self._mlflow is None:
            try:
                import mlflow
                self._mlflow = mlflow
            except ImportError:
                raise ImportError("mlflow required: pip install mlflow")
        return self._mlflow

    def _get_client(self) -> Any:
        """Lazily build MlflowClient scoped to our tracking_uri.

        The fluent API cannot target an arbitrary run by id (mlflow.end_run
        and mlflow.log_param take no usable run_id), so all run-targeted
        operations go through MlflowClient, which avoids the global
        set_tracking_uri side effect entirely.
        """
        if self._client is None:
            from mlflow import MlflowClient
            self._client = MlflowClient(tracking_uri=self._tracking_uri)
        return self._client

    def create_experiment(self, name: str, description: str = "", tags: dict[str, str] | None = None) -> Experiment:
        # All ops go through the client: fluent start_run/create_experiment
        # would honor the global tracking uri, not our tracking_uri.
        exp_id = self._get_client().create_experiment(name, tags=tags)
        return Experiment(id=exp_id, name=name, description=description, tags=tags or {})

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        try:
            exp = self._get_client().get_experiment(experiment_id)
            return Experiment(id=exp.experiment_id, name=exp.name, tags=exp.tags or {}) if exp else None
        except Exception:
            return None

    def get_experiment_by_name(self, name: str) -> Experiment | None:
        exp = self._get_client().get_experiment_by_name(name)
        return Experiment(id=exp.experiment_id, name=exp.name, tags=exp.tags or {}) if exp else None

    def list_experiments(self) -> list[Experiment]:
        return [Experiment(id=e.experiment_id, name=e.name, tags=e.tags or {})
                for e in self._get_client().search_experiments()]

    def start_run(self, experiment_id: str, name: str = "", tags: dict[str, str] | None = None) -> Run:
        run = self._get_client().create_run(experiment_id, run_name=name, tags=tags)
        return Run(id=run.info.run_id, experiment_id=experiment_id, name=name, status="running", tags=tags or {})

    def end_run(self, run_id: str, status: str = "completed") -> Run:
        # Fluent mlflow.end_run takes no run_id; use the client to terminate
        # the specific run. Status map: completed -> FINISHED, else FAILED.
        self._get_client().set_terminated(
            run_id, status="FINISHED" if status == "completed" else "FAILED"
        )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> Run | None:
        try:
            run = self._get_client().get_run(run_id)
            return Run(id=run.info.run_id, experiment_id=run.info.experiment_id, name=run.info.run_name or "",
                       status="completed" if run.info.status == "FINISHED" else run.info.status.lower(),
                       params=run.data.params, metrics=run.data.metrics, tags=run.data.tags)
        except Exception:
            return None

    def list_runs(self, experiment_id: str | None = None) -> list[Run]:
        client = self._get_client()
        if experiment_id:
            runs = client.search_runs(experiment_ids=[experiment_id])
        else:
            exp_ids = [e.experiment_id for e in client.search_experiments()]
            runs = client.search_runs(experiment_ids=exp_ids) if exp_ids else []
        return [Run(id=r.info.run_id, experiment_id=r.info.experiment_id, name=r.info.run_name or "",
                    status="completed" if r.info.status == "FINISHED" else r.info.status.lower()) for r in runs]

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        # Fluent log_param(run_id=None, param_key=None, param_value=None)
        # binds positional (key, value) to the wrong slots; the client
        # signature is unambiguous.
        self._get_client().log_param(run_id, key, value)

    def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        client = self._get_client()
        for key, value in params.items():
            client.log_param(run_id, key, value)

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        self._get_client().log_metric(run_id, key, value, step=step)

    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = 0) -> None:
        client = self._get_client()
        for key, value in metrics.items():
            client.log_metric(run_id, key, value, step=step)

    def log_artifact(self, run_id: str, artifact_path: str) -> None:
        mlflow = self._get_mlflow()
        from pathlib import Path
        if Path(artifact_path).is_dir():
            mlflow.log_artifacts(artifact_path, run_id=run_id)
        else:
            mlflow.log_artifact(artifact_path, run_id=run_id)

    def register_dataset(self, name: str, version: str, path: str, metadata: dict[str, Any] | None = None) -> Dataset:
        import hashlib
        digest = hashlib.sha256(f"{name}:{version}:{path}".encode()).hexdigest()[:16]
        dataset = Dataset(id=str(uuid.uuid4()), name=name, version=version, path=path, digest=digest, metadata=metadata or {})
        self._datasets[f"{name}:{version}"] = dataset
        return dataset

    def get_dataset(self, name: str, version: str | None = None) -> Dataset | None:
        if version:
            return self._datasets.get(f"{name}:{version}")
        matching = [d for k, d in self._datasets.items() if k.startswith(f"{name}:")]
        return matching[-1] if matching else None

    def health_check(self) -> TrackerHealth:
        start = time.perf_counter()
        try:
            self._get_mlflow()
            return TrackerHealth(healthy=True, backend="mlflow", latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return TrackerHealth(healthy=False, backend="mlflow", latency_ms=(time.perf_counter() - start) * 1000, message=str(e))
