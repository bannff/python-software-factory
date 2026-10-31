"""Integration tests — NCI handoff over real UDP loopback socket.

Proves end-to-end: UdpNciTransport → real socket → LoopbackNciListener.
Uses ephemeral ports, no real-time sleeps, tight async timeouts.
"""

from __future__ import annotations

import asyncio

import pytest

from factory.launch.runtime.nci.ports import NciCommand, to_wire
from factory.launch.runtime.nci.udp import UdpNciTransport
from factory.launch.runtime.nci.loopback import LoopbackNciListener
from factory.launch.runtime.orchestrator import LaunchOrchestrator, LaunchState


@pytest.fixture
async def listener():
    """Ephemeral-port loopback listener, auto-stopped after test."""
    lis = LoopbackNciListener()
    await lis.start()
    yield lis
    await lis.stop()


@pytest.fixture
async def transport(listener: LoopbackNciListener):
    """UdpNciTransport aimed at the listener's ephemeral port."""
    t = UdpNciTransport(host="127.0.0.1", port=listener.bound_port)
    yield t
    await t.close()


class TestNciHandoffIntegration:
    """End-to-end: orchestrator → UdpNciTransport → socket → listener."""

    @pytest.mark.asyncio
    async def test_listener_receives_exact_wire_bytes_in_order(
        self, listener: LoopbackNciListener, transport: UdpNciTransport
    ):
        """(a) Listener receives EXACT NCI wire bytes for the launch command sequence."""

        # Signal ready immediately so orchestrator completes
        listener.signal_ready()

        orch = LaunchOrchestrator(
            transport=transport,
            readiness_probe=listener.readiness_probe,
            poll_interval=0.005,
            timeout=1.0,
        )
        await orch.launch("/roms/kinst.zip", core="/cores/mame.so")

        # Give UDP a moment to deliver (loopback is near-instant)
        await asyncio.sleep(0.02)

        expected = [
            to_wire(NciCommand("LOAD_CORE", ("/cores/mame.so",))),
            to_wire(NciCommand("LOAD_CONTENT", ("/roms/kinst.zip",))),
        ]
        assert listener.received == expected

    @pytest.mark.asyncio
    async def test_orchestrator_reaches_ready_on_signal(
        self, listener: LoopbackNciListener, transport: UdpNciTransport
    ):
        """(b) Orchestrator reaches READY when readiness signal arrives."""

        # Fire readiness after a short delay
        async def signal_after_delay():
            await asyncio.sleep(0.03)
            listener.signal_ready()

        asyncio.get_running_loop().create_task(signal_after_delay())

        orch = LaunchOrchestrator(
            transport=transport,
            readiness_probe=listener.readiness_probe,
            poll_interval=0.005,
            timeout=1.0,
        )
        result = await orch.launch("/roms/sf2.zip")

        assert result == LaunchState.READY
        assert orch.state == LaunchState.READY

    @pytest.mark.asyncio
    async def test_orchestrator_reaches_failed_on_timeout(
        self, listener: LoopbackNciListener, transport: UdpNciTransport
    ):
        """(c) Orchestrator reaches FAILED on readiness timeout (no signal sent)."""

        # Do NOT signal ready — orchestrator must timeout
        orch = LaunchOrchestrator(
            transport=transport,
            readiness_probe=listener.readiness_probe,
            poll_interval=0.005,
            timeout=0.05,  # Tight timeout — no real sleep
        )
        result = await orch.launch("/roms/kinst.zip")

        assert result == LaunchState.FAILED
        assert orch.state == LaunchState.FAILED

        # Commands were still sent even though readiness never arrived
        await asyncio.sleep(0.02)
        assert len(listener.received) == 1  # Only LOAD_CONTENT (no core)
        assert listener.received[0] == to_wire(NciCommand("LOAD_CONTENT", ("/roms/kinst.zip",)))
