"""Graph-backed ML store via MCP aggregator.

Persists FineTuningJob, Experiment, Run, and Checkpoint nodes to the
graph brick through MCP tool invocations — no direct Neo4j driver
usage, no cross-brick imports.

Node types:
  - FineTuningJob: fine-tuning job with lifecycle state
  - Experiment: ML experiment container
  - Run: experiment run with params and metrics
  - Checkpoint: training checkpoint
Relationships:
  - HAS_RUN: Experiment → Run
  - CHECKPOINT_OF: Checkpoint → FineTuningJob
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..models import Checkpoint, FineTuningJob
from ..ports import Experiment, Run

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a graph brick tool via the MCP aggregator (lazy-init)."""
    from factory.mcp_server.interface import get_aggregator, get_server
    get_server()
    agg = get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available for graph persistence")
    return agg.invoke_tool(tool_name, **kwargs)


class GraphMLStore:
    """Persists ML entities to the knowledge graph."""

    def persist_job(self, job: FineTuningJob) -> None:
        """Create a FineTuningJob node + Checkpoint nodes with CHECKPOINT_OF."""
        entity_id = f"ft-job-{job.id}"
        props: dict[str, Any] = {
            "method": job.method.value if hasattr(job.method, "value") else str(job.method),
            "base_model": job.base_model,
            "training_input": (
                {
                    "dataset_uri": job.training_input.dataset_uri,
                    "manifest_uri": job.training_input.manifest_uri,
                    "dataset_digest": job.training_input.dataset_digest,
                    "view_name": job.training_input.view_name,
                    "view_schema_version": job.training_input.view_schema_version,
                }
                if job.training_input else None
            ),
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "created_at": job.created_at.isoformat() if job.created_at else _utcnow(),
            "metrics": json.dumps(job.metrics) if job.metrics else "{}",
        }
        if hasattr(job, "updated_at") and job.updated_at:
            props["completed_at"] = job.updated_at.isoformat()
        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=entity_id,
                entity_type="FineTuningJob",
                properties=props,
            )
            for cp in job.checkpoints:
                self._persist_checkpoint(cp, entity_id)
        except Exception as e:
            logger.error("Failed to persist fine-tuning job %s: %s", job.id, e)

    def _persist_checkpoint(self, cp: Checkpoint, job_entity_id: str) -> None:
        """Create a Checkpoint node and CHECKPOINT_OF relationship."""
        cp_id = f"ml-ckpt-{cp.id}"
        props: dict[str, Any] = {
            "job_id": cp.job_id,
            "step": cp.step,
            "metrics": json.dumps(cp.metrics) if cp.metrics else "{}",
            "path": cp.path,
            "created_at": cp.created_at.isoformat() if cp.created_at else _utcnow(),
        }
        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=cp_id,
                entity_type="Checkpoint",
                properties=props,
            )
            _invoke(
                "graph_graph_add_relationship",
                relationship_id=f"checkpoint-of-{cp.id}",
                relationship_type="CHECKPOINT_OF",
                source_id=cp_id,
                target_id=job_entity_id,
            )
        except Exception as e:
            logger.error("Failed to persist checkpoint %s: %s", cp.id, e)

    def persist_experiment(self, experiment: Experiment) -> None:
        """Create an Experiment node."""
        entity_id = f"ml-exp-{experiment.id}"
        props: dict[str, Any] = {
            "name": experiment.name,
            "description": experiment.description,
            "tags": json.dumps(experiment.tags) if experiment.tags else "{}",
            "created_at": experiment.created_at.isoformat() if experiment.created_at else _utcnow(),
        }
        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=entity_id,
                entity_type="Experiment",
                properties=props,
            )
        except Exception as e:
            logger.error("Failed to persist experiment %s: %s", experiment.id, e)

    def persist_run(self, run: Run) -> None:
        """Create a Run node and HAS_RUN relationship to its experiment."""
        entity_id = f"ml-run-{run.id}"
        props: dict[str, Any] = {
            "experiment_id": run.experiment_id,
            "name": run.name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else _utcnow(),
            "params": json.dumps(run.params) if run.params else "{}",
            "metrics": json.dumps(run.metrics) if run.metrics else "{}",
            "created_at": _utcnow(),
        }
        if run.ended_at:
            props["ended_at"] = run.ended_at.isoformat()
        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=entity_id,
                entity_type="Run",
                properties=props,
            )
            _invoke(
                "graph_graph_add_relationship",
                relationship_id=f"has-run-{run.id}",
                relationship_type="HAS_RUN",
                source_id=f"ml-exp-{run.experiment_id}",
                target_id=entity_id,
            )
        except Exception as e:
            logger.error("Failed to persist run %s: %s", run.id, e)

    def query_jobs(self, status: str | None = None) -> list[dict]:
        """List FineTuningJob entities through the portable Graph API."""
        try:
            result = _invoke("graph_graph_find_entities", entity_type="FineTuningJob",
                             properties={"status": status} if status else None, limit=100)
            if not result or not result.ok or result.data is None:
                return []
            rows = [dict(entity.properties) for entity in result.data.entities]
            return sorted(rows, key=lambda row: str(row.get("created_at", "")), reverse=True)
        except Exception as e:
            logger.error("Failed to query fine-tuning jobs: %s", e)
            return []

    def health_check(self) -> dict[str, Any]:
        """Check graph backend availability."""
        try:
            result = _invoke("graph_graph_health_check")
            data = getattr(result, "data", None)
            return {"ok": bool(result and result.ok and data and data.healthy),
                    "backend": "graph", "graph_nodes": 0}
        except Exception as e:
            return {"ok": False, "backend": "graph", "error": str(e)}
