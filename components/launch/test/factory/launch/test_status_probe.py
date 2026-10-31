"""Tests for B20 — NCI GET_STATUS readiness probe.

Covers: parse_status (pure parser), GetStatusProbe (with MockNciTransport),
and orchestrator integration with the real probe (no network, no real sleep).
"""

import pytest

from factory.launch.runtime.nci.ports import NciCommand
from factory.launch.runtime.nci.mock import MockNciTransport
from factory.launch.runtime.nci.status import NciState, NciStatus, parse_status
from factory.launch.runtime.nci.status_probe import GetStatusProbe
from factory.launch.runtime.orchestrator import LaunchOrchestrator, LaunchState


# --- parse_status: pure parser tests ---


class TestParseStatus:
    def test_playing_with_system_and_game(self):
        raw = "GET_STATUS PLAYING snes,Super Mario World,crc32=a0b1c2d3"
        result = parse_status(raw)
        assert result.state == NciState.PLAYING
        assert result.system_id == "snes"
        assert result.game == "Super Mario World"

    def test_playing_without_prefix(self):
        # Some RetroArch versions may omit the echo prefix
        result = parse_status("PLAYING mame,kinst,crc32=deadbeef")
        assert result.state == NciState.PLAYING
        assert result.system_id == "mame"
        assert result.game == "kinst"

    def test_contentless(self):
        result = parse_status("GET_STATUS CONTENTLESS")
        assert result.state == NciState.CONTENTLESS
        assert result.system_id is None
        assert result.game is None

    def test_paused_with_metadata(self):
        result = parse_status("GET_STATUS PAUSED arcade,sf2,crc32=12345678")
        assert result.state == NciState.PAUSED
        assert result.system_id == "arcade"
        assert result.game == "sf2"

    def test_none_input_returns_unknown(self):
        assert parse_status(None) == NciStatus(NciState.UNKNOWN)

    def test_garbage_returns_unknown(self):
        assert parse_status("garbage!!").state == NciState.UNKNOWN

    def test_empty_string_returns_unknown(self):
        assert parse_status("").state == NciState.UNKNOWN

    def test_partial_playing_no_game(self):
        result = parse_status("GET_STATUS PLAYING snes")
        assert result.state == NciState.PLAYING
        assert result.system_id == "snes"
        assert result.game is None


# --- GetStatusProbe: probe with mock transport ---


class TestGetStatusProbe:
    @pytest.mark.asyncio
    async def test_ready_when_playing(self):
        transport = MockNciTransport(
            canned_responses={"GET_STATUS": "GET_STATUS PLAYING mame,kinst,crc32=ab"}
        )
        probe = GetStatusProbe(transport)
        assert await probe() is True

    @pytest.mark.asyncio
    async def test_not_ready_when_contentless(self):
        transport = MockNciTransport(
            canned_responses={"GET_STATUS": "GET_STATUS CONTENTLESS"}
        )
        probe = GetStatusProbe(transport)
        assert await probe() is False

    @pytest.mark.asyncio
    async def test_not_ready_when_paused(self):
        transport = MockNciTransport(
            canned_responses={"GET_STATUS": "GET_STATUS PAUSED snes,smw,crc32=ff"}
        )
        probe = GetStatusProbe(transport)
        assert await probe() is False

    @pytest.mark.asyncio
    async def test_not_ready_when_no_response(self):
        transport = MockNciTransport()  # No canned response -> returns None
        probe = GetStatusProbe(transport)
        assert await probe() is False

    @pytest.mark.asyncio
    async def test_sends_get_status_command(self):
        transport = MockNciTransport(
            canned_responses={"GET_STATUS": "GET_STATUS PLAYING x,y,crc32=00"}
        )
        probe = GetStatusProbe(transport)
        await probe()
        assert transport.commands == [NciCommand("GET_STATUS")]


# --- Orchestrator integration with GetStatusProbe ---


class TestOrchestratorWithStatusProbe:
    @pytest.mark.asyncio
    async def test_reaches_ready_after_n_polls(self):
        """Probe returns CONTENTLESS N times, then PLAYING -> orchestrator READY."""
        call_count = 0
        responses = ["GET_STATUS CONTENTLESS"] * 3 + ["GET_STATUS PLAYING mame,kinst,crc32=ab"]

        class CountingTransport:
            def __init__(self):
                self.commands: list[NciCommand] = []

            async def send_command(self, cmd: NciCommand) -> None:
                self.commands.append(cmd)

            async def query(self, cmd: NciCommand, timeout: float = 1.0) -> str | None:
                nonlocal call_count
                idx = min(call_count, len(responses) - 1)
                call_count += 1
                return responses[idx]

        transport = CountingTransport()
        probe = GetStatusProbe(transport)
        orch = LaunchOrchestrator(transport, probe, poll_interval=0.001, timeout=1.0)
        result = await orch.launch("/roms/kinst.zip")

        assert result == LaunchState.READY
        assert call_count == 4  # 3 CONTENTLESS + 1 PLAYING

    @pytest.mark.asyncio
    async def test_times_out_when_never_playing(self):
        """Probe never returns PLAYING -> orchestrator FAILED."""
        transport = MockNciTransport(
            canned_responses={"GET_STATUS": "GET_STATUS CONTENTLESS"}
        )
        probe = GetStatusProbe(transport)
        orch = LaunchOrchestrator(transport, probe, poll_interval=0.001, timeout=0.02)
        result = await orch.launch("/roms/kinst.zip")

        assert result == LaunchState.FAILED
