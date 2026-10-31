"""Tests for launch brick — NCI framing and orchestrator state machine."""

import asyncio

import pytest

from factory.launch.runtime.nci.ports import NciCommand, to_wire
from factory.launch.runtime.nci.mock import MockNciTransport
from factory.launch.runtime.orchestrator import LaunchOrchestrator, LaunchState


# --- NCI wire format tests ---


class TestToWire:
    def test_simple_command(self):
        assert to_wire(NciCommand("QUIT")) == b"QUIT\n"

    def test_command_with_one_arg(self):
        cmd = NciCommand("LOAD_CORE", ("/usr/lib/libretro/mame_libretro.so",))
        assert to_wire(cmd) == b"LOAD_CORE /usr/lib/libretro/mame_libretro.so\n"

    def test_command_with_multiple_args(self):
        cmd = NciCommand("LOAD_CONTENT", ("/roms/kinst.zip",))
        assert to_wire(cmd) == b"LOAD_CONTENT /roms/kinst.zip\n"

    def test_menu_toggle(self):
        assert to_wire(NciCommand("MENU_TOGGLE")) == b"MENU_TOGGLE\n"

    def test_command_with_spaces_in_path(self):
        cmd = NciCommand("LOAD_CONTENT", ("/roms/my game.zip",))
        assert to_wire(cmd) == b"LOAD_CONTENT /roms/my game.zip\n"


# --- Orchestrator state machine tests ---


@pytest.fixture
def transport():
    return MockNciTransport()


class TestLaunchOrchestrator:
    @pytest.mark.asyncio
    async def test_launch_reaches_ready_on_probe_success(self, transport):
        probe_calls = 0

        async def probe():
            nonlocal probe_calls
            probe_calls += 1
            return probe_calls >= 2  # Ready on second poll

        orch = LaunchOrchestrator(transport, probe, poll_interval=0.01, timeout=1.0)
        result = await orch.launch("/roms/kinst.zip", core="/cores/mame.so")

        assert result == LaunchState.READY
        assert orch.state == LaunchState.READY
        # Should have sent LOAD_CORE then LOAD_CONTENT
        assert len(transport.commands) == 2
        assert transport.commands[0] == NciCommand("LOAD_CORE", ("/cores/mame.so",))
        assert transport.commands[1] == NciCommand("LOAD_CONTENT", ("/roms/kinst.zip",))

    @pytest.mark.asyncio
    async def test_launch_fails_on_timeout(self, transport):
        async def never_ready():
            return False

        orch = LaunchOrchestrator(transport, never_ready, poll_interval=0.01, timeout=0.05)
        result = await orch.launch("/roms/kinst.zip")

        assert result == LaunchState.FAILED
        assert orch.state == LaunchState.FAILED
        # No core specified, so only LOAD_CONTENT sent
        assert len(transport.commands) == 1
        assert transport.commands[0].name == "LOAD_CONTENT"

    @pytest.mark.asyncio
    async def test_launch_without_core(self, transport):
        async def immediate():
            return True

        orch = LaunchOrchestrator(transport, immediate, poll_interval=0.01, timeout=1.0)
        await orch.launch("/roms/sf2.zip")

        # Only LOAD_CONTENT, no LOAD_CORE
        assert len(transport.commands) == 1
        assert transport.commands[0] == NciCommand("LOAD_CONTENT", ("/roms/sf2.zip",))

    @pytest.mark.asyncio
    async def test_quit_sends_command_and_returns_idle(self, transport):
        async def immediate():
            return True

        orch = LaunchOrchestrator(transport, immediate, poll_interval=0.01, timeout=1.0)
        await orch.launch("/roms/kinst.zip")
        assert orch.state == LaunchState.READY

        await orch.quit()
        assert orch.state == LaunchState.IDLE
        assert transport.commands[-1] == NciCommand("QUIT")

    @pytest.mark.asyncio
    async def test_initial_state_is_idle(self, transport):
        async def immediate():
            return True

        orch = LaunchOrchestrator(transport, immediate)
        assert orch.state == LaunchState.IDLE
