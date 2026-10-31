"""
Property-based tests for StdioBackend using Hypothesis.

Verifies that the stdio notification backend maintains its contract
across arbitrary valid inputs: always returns "sent" status, unique
message IDs, correct backend name, and stable health checks.
"""

import asyncio
from hypothesis import given, settings, strategies as st

from factory.notification.runtime.backends.local import StdioBackend
from factory.notification.runtime.models import NotificationRequest


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_recipients = st.text(
    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
)
_content = st.one_of(st.none(), st.text(min_size=0, max_size=100))
_priority = st.sampled_from(["low", "normal", "high"])
_optional_str = st.one_of(st.none(), st.text(min_size=0, max_size=50))
_data = st.dictionaries(
    st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
    st.text(max_size=20),
    max_size=5,
)

_notification_requests = st.builds(
    NotificationRequest,
    recipient=_recipients,
    channel_id=_optional_str,
    template_id=_optional_str,
    content=_content,
    subject=_optional_str,
    data=_data,
    priority=_priority,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine synchronously for Hypothesis tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


async def _make_backend() -> StdioBackend:
    backend = StdioBackend()
    await backend.initialize({"prefix": "[TEST]"})
    return backend


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

@given(request=_notification_requests)
@settings(max_examples=50)
def test_send_returns_sent_status(request: NotificationRequest):
    """For any valid NotificationRequest, send() returns status='sent'."""

    async def _check():
        backend = await _make_backend()
        result = await backend.send(request)
        assert result.status == "sent", f"Expected 'sent', got '{result.status}'"

    _run_async(_check())


@given(request=_notification_requests)
@settings(max_examples=50)
def test_send_returns_unique_message_ids(request: NotificationRequest):
    """Multiple sends of the same request produce distinct message_ids."""

    async def _check():
        backend = await _make_backend()
        ids = {(await backend.send(request)).message_id for _ in range(5)}
        assert len(ids) == 5, f"Expected 5 unique IDs, got {len(ids)}"

    _run_async(_check())


@given(request=_notification_requests)
@settings(max_examples=50)
def test_send_backend_is_stdio(request: NotificationRequest):
    """DeliveryStatus.backend always equals 'stdio'."""

    async def _check():
        backend = await _make_backend()
        result = await backend.send(request)
        assert result.backend == "stdio", f"Expected 'stdio', got '{result.backend}'"

    _run_async(_check())


@given(data=st.data())
@settings(max_examples=50)
def test_health_check_always_true(data):
    """health_check() returns True regardless of prior operations."""

    async def _check():
        backend = await _make_backend()
        # Optionally send a notification first
        if data.draw(st.booleans()):
            req = data.draw(_notification_requests)
            await backend.send(req)
        assert await backend.health_check() is True

    _run_async(_check())


def test_name_is_stdio():
    """The name property always returns 'stdio'."""
    backend = StdioBackend()
    assert backend.name == "stdio"


@given(priority=_priority, recipient=_recipients)
@settings(max_examples=50)
def test_send_with_all_priorities(priority: str, recipient: str):
    """send() works correctly for every valid priority level."""

    async def _check():
        backend = await _make_backend()
        req = NotificationRequest(recipient=recipient, priority=priority)
        result = await backend.send(req)
        assert result.status == "sent"
        assert result.backend == "stdio"
        assert result.message_id  # non-empty

    _run_async(_check())


@given(configs=st.lists(
    st.dictionaries(st.text(min_size=1, max_size=10), st.text(max_size=20), max_size=3),
    min_size=2,
    max_size=5,
))
@settings(max_examples=50)
def test_idempotent_initialize(configs: list[dict]):
    """Calling initialize() multiple times does not raise."""

    async def _check():
        backend = StdioBackend()
        for cfg in configs:
            await backend.initialize(cfg)
        # After all inits, backend should still work
        req = NotificationRequest(recipient="user1")
        result = await backend.send(req)
        assert result.status == "sent"
        assert await backend.health_check() is True

    _run_async(_check())
