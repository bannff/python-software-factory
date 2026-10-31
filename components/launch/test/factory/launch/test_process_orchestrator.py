"""Tests for ProcessLaunchOrchestrator — including Darwin trampoline awareness."""

from __future__ import annotations

import asyncio

import pytest

from factory.launch.interface import (
    ProcessLaunchOrchestrator,
    LaunchState,
    FakeProcessLauncher,
    FakeProcessHandle,
)


# --- Fake probe ---

class FakeProbe:
    """Readiness probe that succeeds after N calls."""

    def __init__(self, *, succeed_after: int = 0, always_fail: bool = False):
        self._calls = 0
        self._succeed_after = succeed_after
        self._always_fail = always_fail

    async def __call__(self) -> bool:
        self._calls += 1
        if self._always_fail:
            return False
        return self._calls > self._succeed_after


# --- Linux (non-trampoline) behavior ---

class TestLinuxBehavior:
    """Standard behavior: process exit = failure; probe success = READY."""

    def test_ready_on_probe_success(self):
        launcher = FakeProcessLauncher()
        probe = FakeProbe(succeed_after=1)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=5.0, poll_interval=0.05)
        state = asyncio.run(orch.launch(["retroarch", "-L", "core", "rom"]))
        assert state == LaunchState.READY

    def test_failure_on_process_exit(self):
        launcher = FakeProcessLauncher(_exit_code=1, _stderr="core not found")
        probe = FakeProbe()
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=5.0)
        state = asyncio.run(orch.launch(["retroarch", "-L", "core", "rom"]))
        assert state == LaunchState.FAILED
        assert "exited with code 1" in orch.failure_reason

    def test_timeout_on_unreachable(self):
        launcher = FakeProcessLauncher()
        probe = FakeProbe(always_fail=True)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=0.3, poll_interval=0.05)
        state = asyncio.run(orch.launch(["retroarch"]))
        assert state == LaunchState.FAILED
        assert "Timeout" in orch.failure_reason


# --- Darwin trampoline behavior ---

class TestDarwinTrampoline:
    """When argv starts with `open`, returncode==0 is expected (trampoline handoff).
    Only the NCI VERSION probe determines success. Non-zero = rejection."""

    def test_trampoline_exit_0_keeps_polling_until_ready(self):
        """open exits 0 immediately — orchestrator does NOT treat it as failure."""
        launcher = FakeProcessLauncher(_exit_code=0)  # exits immediately
        probe = FakeProbe(succeed_after=2)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=5.0, poll_interval=0.05)
        # argv starts with "open" — triggers trampoline mode
        state = asyncio.run(orch.launch(["open", "-a", "RetroArch.app", "--args", "-L", "core"]))
        assert state == LaunchState.READY

    def test_trampoline_exit_nonzero_is_failure(self):
        """open exits non-zero = trampoline rejected (app not found)."""
        launcher = FakeProcessLauncher(_exit_code=1, _stderr="Unable to find application")
        probe = FakeProbe(always_fail=True)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=5.0)
        state = asyncio.run(orch.launch(["open", "-a", "Nonexistent.app"]))
        assert state == LaunchState.FAILED
        assert "Trampoline rejected" in orch.failure_reason

    def test_trampoline_timeout_when_probe_never_succeeds(self):
        """open exits 0, but RetroArch never responds to NCI VERSION."""
        launcher = FakeProcessLauncher(_exit_code=0)
        probe = FakeProbe(always_fail=True)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=0.3, poll_interval=0.05)
        state = asyncio.run(orch.launch(["open", "-a", "RA.app", "--args"]))
        assert state == LaunchState.FAILED
        assert "Timeout" in orch.failure_reason

    def test_non_trampoline_exit_0_still_fails(self):
        """Sanity: a raw binary exiting 0 without readiness = timeout (not 'success')."""
        launcher = FakeProcessLauncher(_exit_code=0)
        probe = FakeProbe(always_fail=True)
        orch = ProcessLaunchOrchestrator(launcher, probe, timeout=0.3, poll_interval=0.05)
        # NOT a trampoline — raw retroarch that exited
        state = asyncio.run(orch.launch(["retroarch", "-L", "c"]))
        # On Linux, exit = failure (any exit is abnormal)
        assert state == LaunchState.FAILED
        assert "exited with code 0" in orch.failure_reason
