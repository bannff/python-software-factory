import pytest

from factory.notification.runtime.dispatcher import Dispatcher
from factory.notification.runtime.models import NotificationRequest


@pytest.mark.asyncio
async def test_stdio_dispatch():
    """Test that the dispatcher correctly uses the StdioBackend."""
    dispatcher = Dispatcher()

    # Initialize with default settings (stdio)
    settings = {"backend": {"type": "stdio", "config": {"prefix": "[TEST]"}}}
    await dispatcher.initialize("/tmp", settings)

    # Send a request
    req = NotificationRequest(recipient="test@example.com", content="Hello World")
    result = await dispatcher.send(req)

    assert result.status == "sent"
    assert result.backend == "stdio"
    assert result.message_id is not None


@pytest.mark.asyncio
async def test_dispatcher_health():
    dispatcher = Dispatcher()
    settings = {"backend": {"type": "stdio"}}
    await dispatcher.initialize("/tmp", settings)

    healthy = await dispatcher.health_check()
    assert healthy is True
