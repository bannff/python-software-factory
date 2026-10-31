"""Tests for PushChannel."""

import pytest

from factory.ui.runtime import (
    ChannelType,
    PushChannel,
    ViewUpdate,
)


class TestPushChannel:
    """Tests for PushChannel."""

    def test_connect_client(self):
        """Should connect a client."""
        channel = PushChannel()
        connection = channel.connect("client-1")

        assert connection.client_id == "client-1"
        assert connection.channel_type == ChannelType.CALLBACK

    def test_disconnect_client(self):
        """Should disconnect a client."""
        channel = PushChannel()
        channel.connect("client-1")

        assert channel.disconnect("client-1") is True
        assert channel.get_client("client-1") is None

    def test_subscribe(self):
        """Should subscribe client to view."""
        channel = PushChannel()
        channel.connect("client-1")

        assert channel.subscribe("client-1", "view-1") is True

        client = channel.get_client("client-1")
        assert "view-1" in client.subscribed_views

    def test_unsubscribe(self):
        """Should unsubscribe client from view."""
        channel = PushChannel()
        channel.connect("client-1")
        channel.subscribe("client-1", "view-1")

        assert channel.unsubscribe("client-1", "view-1") is True

        client = channel.get_client("client-1")
        assert "view-1" not in client.subscribed_views

    @pytest.mark.asyncio
    async def test_push_to_subscribers(self):
        """Should push updates to subscribed clients."""
        channel = PushChannel()
        received = []

        async def callback(update):
            received.append(update)

        channel.connect("client-1", callback=callback)
        channel.subscribe("client-1", "view-1")

        update = ViewUpdate(
            view_id="view-1",
            action="full",
            payload={"test": True},
            version=1,
        )

        recipients = await channel.push(update)

        assert recipients == 1
        assert len(received) == 1
        assert received[0].view_id == "view-1"

    @pytest.mark.asyncio
    async def test_push_wildcard_subscription(self):
        """Should push to clients subscribed to all views."""
        channel = PushChannel()
        received = []

        async def callback(update):
            received.append(update)

        channel.connect("client-1", callback=callback)
        channel.subscribe("client-1", "*")  # Subscribe to all

        update = ViewUpdate(
            view_id="any-view",
            action="full",
            payload={},
            version=1,
        )

        recipients = await channel.push(update)

        assert recipients == 1

    @pytest.mark.asyncio
    async def test_push_no_subscribers(self):
        """Should return 0 when no subscribers."""
        channel = PushChannel()
        channel.connect("client-1")
        channel.subscribe("client-1", "view-1")

        update = ViewUpdate(
            view_id="view-2",  # Different view
            action="full",
            payload={},
            version=1,
        )

        recipients = await channel.push(update)

        assert recipients == 0

    def test_list_clients(self):
        """Should list all connected clients."""
        channel = PushChannel()
        channel.connect("client-1")
        channel.connect("client-2")

        clients = channel.list_clients()

        assert len(clients) == 2

    def test_get_subscribers(self):
        """Should get subscribers for a view."""
        channel = PushChannel()
        channel.connect("client-1")
        channel.connect("client-2")
        channel.subscribe("client-1", "view-1")

        subscribers = channel.get_subscribers("view-1")

        assert len(subscribers) == 1
        assert subscribers[0].client_id == "client-1"
