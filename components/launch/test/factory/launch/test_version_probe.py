"""Tests for VersionProbe — returns True on non-empty VERSION reply, False on empty."""

import pytest

from factory.launch.runtime.nci.version_probe import VersionProbe
from factory.launch.runtime.nci.mock import MockNciTransport


@pytest.mark.asyncio
async def test_version_probe_true_on_non_empty_reply():
    """VersionProbe returns True when transport returns a version string."""
    transport = MockNciTransport(canned_responses={"VERSION": "1.19.1"})
    probe = VersionProbe(transport)
    assert await probe() is True


@pytest.mark.asyncio
async def test_version_probe_false_on_empty_reply():
    """VersionProbe returns False when transport returns empty string."""
    transport = MockNciTransport(canned_responses={"VERSION": ""})
    probe = VersionProbe(transport)
    assert await probe() is False


@pytest.mark.asyncio
async def test_version_probe_false_on_none_reply():
    """VersionProbe returns False when transport returns None (timeout)."""
    transport = MockNciTransport(canned_responses={})  # No VERSION key → returns None
    probe = VersionProbe(transport)
    assert await probe() is False


@pytest.mark.asyncio
async def test_version_probe_false_on_whitespace_only():
    """VersionProbe returns False on whitespace-only reply."""
    transport = MockNciTransport(canned_responses={"VERSION": "   \n"})
    probe = VersionProbe(transport)
    assert await probe() is False


@pytest.mark.asyncio
async def test_version_probe_sends_version_command():
    """VersionProbe sends the VERSION NCI command."""
    transport = MockNciTransport(canned_responses={"VERSION": "1.19.1"})
    probe = VersionProbe(transport)
    await probe()
    assert len(transport.commands) == 1
    assert transport.commands[0].name == "VERSION"
