from __future__ import annotations

import base64
from email import message_from_bytes

import pytest

from factory.integrations.runtime.adapters.gmail_email import GmailEmailSender
from factory.integrations.runtime.email_models import (
    ProviderReceiptError, SendEmailRequest,
)


class Execute:
    def __init__(self, response):
        self.response = response

    def execute(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Messages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def send(self, *, userId, body):
        self.calls.append((userId, body))
        return Execute(self.response)


class Client:
    def __init__(self, response):
        self.messages_api = Messages(response)

    def users(self):
        return self

    def messages(self):
        return self.messages_api


def request() -> SendEmailRequest:
    return SendEmailRequest(
        connection_ref="email_conn_123", idempotency_key="attempt-1",
        recipients=["one@example.test", "two@example.test"],
        subject="Factory integration", body="private body",
    )


def test_gmail_adapter_maps_neutral_request_and_returns_safe_receipt():
    client = Client({"id": "abcdef0123456789"})
    receipt = GmailEmailSender(client).send(request())

    assert receipt.status == "sent"
    assert receipt.message_id == "abcdef0123456789"
    assert receipt.intent_digest == request().intent_digest()
    user_id, body = client.messages_api.calls[0]
    message = message_from_bytes(base64.urlsafe_b64decode(body["raw"] + "=="))
    assert user_id == "me"
    assert message["To"] == "one@example.test, two@example.test"
    assert message["Subject"] == "Factory integration"
    assert message.get_payload(decode=True).decode().strip() == "private body"
    assert "private body" not in receipt.model_dump_json()


@pytest.mark.parametrize(
    "response",
    [{}, {"threadId": "abcdef0123456789"}, {"id": "unsafe/provider/value"}, {"id": 7}],
)
def test_gmail_adapter_rejects_unbounded_provider_receipts(response):
    with pytest.raises(ProviderReceiptError, match="invalid provider receipt"):
        GmailEmailSender(Client(response)).send(request())


def test_gmail_adapter_does_not_intercept_provider_transport_failure():
    with pytest.raises(RuntimeError, match="provider secret canary"):
        GmailEmailSender(Client(RuntimeError("provider secret canary"))).send(request())
