"""MCP-boundary regression for the trajectory-zone output contract.

The resolver-level suite (test_trajectory_zone_resolve.py) pins row_count and
tamper rejection at the *runtime* layer. This file pins the *wire* contract:
the runtime returns a JSON array of rows, so the typed egress model must
accept a ``list`` — a ``tuple[...]`` field under ``strict=True`` rejects the
array and the @deterministic wrapper collapses the ValidationError into an
opaque ``tool_execution_failed`` on every live call.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib

from factory.dataset.server import create_mcp_server


def _seed_zone(root: pathlib.Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "run-a.jsonl"
    rows = [
        {"schema_version": 1, "run_id": "run-a", "attempt_id": "a1",
         "recorded_at": "2026-10-12T00:00:00Z",
         "content_sha256": f"sha256:{'1' * 64}", "verdict": "scored"},
        {"schema_version": 1, "run_id": "run-a", "attempt_id": "a2",
         "recorded_at": "2026-10-12T00:00:01Z",
         "content_sha256": f"sha256:{'2' * 64}", "verdict": "abandoned"},
    ]
    content = ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()
    path.write_bytes(content)
    (root / "run-a.jsonl.ref.json").write_text(json.dumps({
        "schema_version": 1, "row_count": len(rows),
        "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
    }))
    return path.resolve().as_uri()


def _boundary_tool(root: pathlib.Path):
    server = create_mcp_server(root)
    return asyncio.run(server.get_tool("dataset_resolve_trajectory_zone")).fn


def test_trajectory_zone_boundary_returns_verified_rows(tmp_path: pathlib.Path) -> None:
    uri = _seed_zone(tmp_path)
    result = _boundary_tool(tmp_path)(dataset_uri=uri)
    assert result.ok is True
    assert result.error is None
    assert result.data is not None
    assert result.data.row_count == 2
    assert [row.attempt_id for row in result.data.rows] == ["a1", "a2"]
    assert result.data.rows[0].verdict == "scored"
    assert result.data.rows[0].content_sha256 == f"sha256:{'1' * 64}"


def test_trajectory_zone_boundary_rejects_tampered_zone(tmp_path: pathlib.Path) -> None:
    uri = _seed_zone(tmp_path)
    path = tmp_path / "run-a.jsonl"
    path.write_bytes(path.read_bytes().replace(b'"a1"', b'"a9"'))
    result = _boundary_tool(tmp_path)(dataset_uri=uri)
    assert result.ok is False
    assert result.error == "tool_execution_failed"
