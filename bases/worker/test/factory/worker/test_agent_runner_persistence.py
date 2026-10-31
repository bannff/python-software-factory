"""Persistence, neutral Agent wiring, archive, and datetime tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.worker.runtime.adapters.archive_adapters import InMemoryArchive, JsonlFileArchive
from factory.worker.runtime.adapters.file_persistence import FilePersistence
from factory.worker.runtime.agent_runner_models import AgentRunnerState, InboxMessage, RunnerStatus
from factory.worker.runtime.agent_wiring import build_agent_invoke_fn
from factory.worker.runtime.archive_ports import AgentInvocationPort, ArchiveSinkPort


class TestFilePersistence:
    @pytest.fixture
    def adapter(self, tmp_path: Path) -> FilePersistence:
        return FilePersistence(tmp_path / "runner_state")

    async def test_save_and_load_round_trips(self, adapter: FilePersistence) -> None:
        state = AgentRunnerState(
            agent_id="agent-1", status=RunnerStatus.ACTIVE,
            session_id="sess-abc", turn_count=7,
            last_active_at=datetime(2026, 6, 30, 12, tzinfo=timezone.utc),
        )
        await adapter.save_state(state)
        loaded = await FilePersistence(adapter._dir).load_state("agent-1")
        assert loaded is not None
        assert loaded.to_dict() == state.to_dict()

    async def test_load_nonexistent_returns_none(self, adapter: FilePersistence) -> None:
        assert await adapter.load_state("missing") is None

    async def test_list_agents(self, adapter: FilePersistence) -> None:
        for agent_id in ("alpha", "beta", "gamma"):
            await adapter.save_state(AgentRunnerState(agent_id=agent_id))
        assert set(await adapter.list_agents()) == {"alpha", "beta", "gamma"}

    async def test_atomic_write_leaves_valid_json(self, adapter: FilePersistence) -> None:
        await adapter.save_state(AgentRunnerState(agent_id="atomic", turn_count=3))
        data = json.loads(adapter._path_for("atomic").read_text("utf-8"))
        assert data["turn_count"] == 3


class TestArchive:
    def test_in_memory_archive_is_append_only(self) -> None:
        archive = InMemoryArchive()
        archive.append("a1", {"content": "first"})
        archive.append("a1", {"content": "second"})
        assert [record[1]["content"] for record in archive.records] == ["first", "second"]

    def test_jsonl_archive_is_append_only(self, tmp_path: Path) -> None:
        archive = JsonlFileArchive(tmp_path / "archive")
        archive.append("bot", {"content": "first"})
        archive.append("bot", {"content": "second"})
        assert [item["content"] for item in archive.read_all("bot")] == ["first", "second"]

    def test_archive_sink_port_protocol(self) -> None:
        assert isinstance(InMemoryArchive(), ArchiveSinkPort)


class RecordingRuntime:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output="response", status="completed")


class TestAgentWiring:
    async def test_invokes_neutral_runtime_and_archives_turn(self) -> None:
        runtime = RecordingRuntime()
        archive = InMemoryArchive()
        invoke = build_agent_invoke_fn(
            "worker-agent", runtime=runtime, archive_sink=archive,
            system_prompt="worker prompt",
        )

        result = await invoke("session-1", "hello")

        assert isinstance(runtime, AgentInvocationPort)
        assert result.output == "response"
        assert runtime.calls == [{
            "agent_id": "worker-agent", "session_id": "session-1",
            "content": "hello", "system_prompt": "worker prompt",
        }]
        assert [record[1]["role"] for record in archive.records] == ["user", "assistant"]
        assert [record[1]["content"] for record in archive.records] == ["hello", "response"]


class TestDatetimeFix:
    def test_inbox_message_enqueued_at_is_tz_aware(self) -> None:
        assert InboxMessage(agent_id="x", content="test").enqueued_at.tzinfo == timezone.utc

    def test_agent_runner_state_round_trip(self) -> None:
        original = AgentRunnerState(
            agent_id="rt", status=RunnerStatus.ACTIVE,
            auto_wake_at=datetime(2026, 7, 1, 8, tzinfo=timezone.utc),
            session_id="s1", turn_count=5,
            last_active_at=datetime(2026, 6, 30, 23, tzinfo=timezone.utc),
        )
        assert AgentRunnerState.from_dict(original.to_dict()).to_dict() == original.to_dict()

    def test_from_dict_handles_none_timestamps(self) -> None:
        state = AgentRunnerState.from_dict({
            "agent_id": "a", "status": "parked", "auto_wake_at": None,
            "session_id": None, "turn_count": 0, "last_active_at": None,
        })
        assert state.auto_wake_at is None and state.last_active_at is None
