import asyncio
from pathlib import Path

import pytest

from factory.dataset.interface import (
    check_dataset_status,
    dataset_cancel_job,
    start_dataset_generation,
)
from factory.dataset.server import create_mcp_server


@pytest.mark.asyncio
async def test_dataset_generation_lifecycle(tmp_path: Path) -> None:
    config_path = tmp_path / "records.jsonl"
    config_path.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')

    job_id = await start_dataset_generation(str(config_path), storage_root=tmp_path)
    assert isinstance(job_id, str)

    status = {}
    for _ in range(100):
        status = await check_dataset_status(job_id, storage_root=tmp_path)
        if status.get("status") in {"completed", "failed"}:
            break
        await asyncio.sleep(0.05)

    assert status.get("status") == "completed"

    log_path = tmp_path / "jobs" / f"{job_id}.log"
    assert log_path.exists()
    assert log_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_dataset_cancel_job_transitions_to_failed(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"source":"cancel-test"}')

    job_id = await start_dataset_generation(str(config_path), storage_root=tmp_path)

    cancelled = dataset_cancel_job(job_id, reason="test-cancel", storage_root=tmp_path)
    assert cancelled.status == "failed"
    assert cancelled.error == "test-cancel"

    status = await check_dataset_status(job_id, storage_root=tmp_path)
    assert status["status"] == "failed"
    assert status["error"] == "test-cancel"


@pytest.mark.asyncio
async def test_dataset_job_logs_resource(tmp_path: Path) -> None:
    log_path = tmp_path / "jobs" / "job-123.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("worker output\n")

    server = create_mcp_server(storage_root=tmp_path)
    result = await server.read_resource("dataset://jobs/job-123/logs")
    assert result.contents[0].content == "worker output\n"

    missing = await server.read_resource("dataset://jobs/missing/logs")
    assert missing.contents[0].content == ""
