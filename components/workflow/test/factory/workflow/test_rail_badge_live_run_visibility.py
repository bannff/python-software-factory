"""Real end-to-end proof that a running attempt is visible via list_runs.

Backs the Sessions rail badge (frontend `useActiveBackgroundRunCount`):
proves the exact contract it polls, `workflow.list_runs`, reflects a
genuinely paused `wait_for_event` attempt (status ``waiting``) before the
matching event ever arrives, then reflects it leaving that state once the
event lands. ``status`` is an exact-match backend filter (see
``runtime/storage/runs.py::list_runs``), so the badge — and this proof —
fetch unfiltered and check status client-side rather than filtering on
the backend for ``running`` alone, which would silently miss ``waiting``.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from factory.workflow.server import create_tool_catalog

_DEFINITION = {
    "id": "badge-proof-workflow", "name": "Badge proof workflow", "version": 1,
    "steps": [
        {"id": "wait", "kind": "wait_for_event",
         "event_type": "badge.proof.continue", "next": "done"},
        {"id": "done", "kind": "noop"},
    ],
}


def _write_config(config_dir: Path) -> None:
    (config_dir / "workflows").mkdir(parents=True)
    (config_dir / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
    }))
    (config_dir / "workflows" / "badge-proof.yaml").write_text(
        yaml.safe_dump(_DEFINITION),
    )


@pytest.mark.asyncio
async def test_waiting_run_is_visible_to_the_rail_badge_query() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp) / "config"
        _write_config(config_dir)
        os.environ["WORKFLOW_CONFIG_DIR"] = str(config_dir)
        try:
            catalog = create_tool_catalog()

            async def call(name: str, args: dict) -> dict:
                return (await catalog.call_tool(name, args)).structured_content

            started = await call("workflow.start_run", {
                "workflow_name_or_id": "badge-proof-workflow", "input": {},
            })
            assert started["ok"], started
            run_id = started["data"]["run_id"]

            listed = await call("workflow.list_runs", {
                "filter": {}, "pagination": {"limit": 100},
            })
            assert listed["ok"], listed
            rows_by_id = {row["run_id"]: row for row in listed["data"]["runs"]}
            assert run_id in rows_by_id
            assert rows_by_id[run_id]["status"] == "waiting"

            await call("workflow.emit_event", {
                "run_id": run_id, "event_type": "badge.proof.continue", "payload": {},
            })
            await call("workflow.step_run", {"run_id": run_id})
            after = await call("workflow.list_runs", {
                "filter": {}, "pagination": {"limit": 100},
            })
            after_rows = {row["run_id"]: row for row in after["data"]["runs"]}
            assert after_rows[run_id]["status"] not in {"running", "waiting"}
        finally:
            os.environ.pop("WORKFLOW_CONFIG_DIR", None)
