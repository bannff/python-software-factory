"""Immutable workflow-definition snapshot persistence."""
from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from factory.workflow.runtime.canonical import canonical_json, canonical_loads
from factory.workflow.runtime.models import WorkflowDefinition
from factory.workflow.runtime.task_ids import workflow_version_id


def persist(connect: Any, workflow: WorkflowDefinition) -> str:
    snapshot = workflow.model_dump(mode="json")
    encoded = canonical_json(snapshot)
    version_id = workflow_version_id(snapshot)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO workflow_versions VALUES(?,?,?,?,?)",
                (version_id, workflow.id, workflow.version, encoded, digest),
            )
        except sqlite3.IntegrityError:
            row = conn.execute(
                "SELECT version_id,snapshot_json FROM workflow_versions "
                "WHERE workflow_id=? AND declared_version=?",
                (workflow.id, workflow.version),
            ).fetchone()
            if row is None or row["version_id"] != version_id or row["snapshot_json"] != encoded:
                raise ValueError("workflow-version conflict")
    return version_id


def load(connect: Any, version_id: str) -> WorkflowDefinition:
    with connect() as conn:
        row = conn.execute(
            "SELECT snapshot_json,snapshot_sha256 FROM workflow_versions WHERE version_id=?",
            (version_id,),
        ).fetchone()
    if row is None:
        raise ValueError("workflow snapshot missing")
    encoded = row["snapshot_json"]
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    snapshot = canonical_loads(encoded)
    if row["snapshot_sha256"] != digest or workflow_version_id(snapshot) != version_id:
        raise ValueError("workflow snapshot integrity mismatch")
    if canonical_json(snapshot) != encoded:
        raise ValueError("workflow snapshot is not canonical")
    return WorkflowDefinition.model_validate(snapshot)
