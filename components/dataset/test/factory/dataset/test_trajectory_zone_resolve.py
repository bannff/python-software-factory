"""Resolver-verified trajectory-zone read tests (fresh file)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile

import pytest

from factory.dataset.interface import TrajectoryRowError, dataset_resolve_trajectory_zone


def _content_sha256(prefix: str = "0") -> str:
    return f"sha256:{prefix * 64}"


def _seed_zone(root: pathlib.Path, *, rows: list[dict], digest: str | None = None) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "run-a.jsonl"
    ref = root / "run-a.jsonl.ref.json"
    content = ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()
    digest = digest or f"sha256:{hashlib.sha256(content).hexdigest()}"
    path.write_bytes(content)
    ref.write_text(json.dumps({
        "schema_version": 1, "row_count": len(rows), "digest": digest,
    }))
    return path.resolve().as_uri()


def test_happy_digest_resolution_returns_validated_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        rows = [
            {"schema_version": 1, "run_id": "run-a", "attempt_id": "a1",
             "recorded_at": "2026-10-12T00:00:00Z", "content_sha256": _content_sha256("1"),
             "verdict": "scored"},
            {"schema_version": 1, "run_id": "run-a", "attempt_id": "a2",
             "recorded_at": "2026-10-12T00:00:01Z", "content_sha256": _content_sha256("2"),
             "verdict": "scored"},
        ]
        uri = _seed_zone(root, rows=rows)
        zone = dataset_resolve_trajectory_zone(uri)
        assert zone["row_count"] == 2
        assert [row["attempt_id"] for row in zone["rows"]] == ["a1", "a2"]


def test_tampered_digest_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        rows = [{"schema_version": 1, "run_id": "run-a", "attempt_id": "a1",
                 "recorded_at": "t", "content_sha256": _content_sha256("3"),
                 "verdict": "scored"}]
        uri = _seed_zone(root, rows=rows)
        path = root / "run-a.jsonl"
        path.write_bytes(path.read_bytes().replace(b"\"a1\"", b"\"a9\""))
        with pytest.raises(TrajectoryRowError, match="tampered|digest does not match"):
            dataset_resolve_trajectory_zone(uri)


def test_missing_reference_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        root.mkdir(exist_ok=True)
        (root / "run-b.jsonl").write_bytes(b"{}\n")
        uri = str((root / "run-b.jsonl").resolve().as_uri())
        with pytest.raises(TrajectoryRowError):
            dataset_resolve_trajectory_zone(uri)
