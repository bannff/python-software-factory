"""AWS SageMaker adapter for experiment tracking.

Implements ExperimentTracker protocol using SageMaker Experiments.
Run/metric methods in aws_runs.py via mixin to stay under 200 LOC.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime
from typing import Any

from ..ports import Dataset, Experiment, Run, TrackerHealth
from .aws_runs import SageMakerRunsMixin

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,256}$")


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for SageMaker adapter"
        raise ImportError(msg)


def _validate_name(value: str, label: str = "name") -> str:
    if not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


class SageMakerTracker(SageMakerRunsMixin):
    """SageMaker Experiments adapter for ExperimentTracker port.

    Maps: factory Experiment → SageMaker Experiment,
          factory Run → SageMaker Trial.
    """

    def __init__(self, region: str = "us-east-1", **kwargs: Any) -> None:
        _require_boto3()
        import boto3

        self._region = region
        self._client = boto3.client("sagemaker", region_name=region)
        self._runs: dict[str, Run] = {}
        self._datasets: dict[str, Dataset] = {}

    def create_experiment(
        self, name: str, description: str = "", tags: dict[str, str] | None = None,
    ) -> Experiment:
        _validate_name(name, "experiment name")
        self._client.create_experiment(
            ExperimentName=name,
            Description=description,
            Tags=[{"Key": k, "Value": v} for k, v in (tags or {}).items()],
        )
        return Experiment(id=name, name=name, description=description, tags=tags or {})

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        try:
            resp = self._client.describe_experiment(ExperimentName=experiment_id)
            return Experiment(
                id=experiment_id,
                name=resp.get("ExperimentName", experiment_id),
                description=resp.get("Description", ""),
            )
        except Exception:
            return None

    def get_experiment_by_name(self, name: str) -> Experiment | None:
        return self.get_experiment(name)

    def list_experiments(self) -> list[Experiment]:
        try:
            resp = self._client.list_experiments()
            return [
                Experiment(id=e["ExperimentName"], name=e["ExperimentName"])
                for e in resp.get("ExperimentSummaries", [])
            ]
        except Exception:
            return []

    def health_check(self) -> TrackerHealth:
        start = time.perf_counter()
        try:
            self._client.list_experiments(MaxResults=1)
            latency = (time.perf_counter() - start) * 1000
            return TrackerHealth(healthy=True, backend="sagemaker", latency_ms=latency)
        except Exception as e:
            return TrackerHealth(healthy=False, backend="sagemaker", message=str(e))

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "sagemaker",
            "construct": "Experiments",
            "props": {
                "features": ["experiment_tracking", "trial_management"],
                "region": self._region,
            },
        }
