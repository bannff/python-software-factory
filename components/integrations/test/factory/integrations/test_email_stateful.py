from __future__ import annotations

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.integrations.runtime.adapters.fake_email import FakeEmailSender
from factory.integrations.runtime.email_models import (
    EmailIdempotencyConflict, EmailReceipt, SendEmailRequest,
)
from factory.integrations.runtime.runtime import IntegrationsRuntime


class EmailRegistryMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.runtime = IntegrationsRuntime()
        self.senders = {"tenant-a": FakeEmailSender(), "tenant-b": FakeEmailSender()}
        for tenant, sender in self.senders.items():
            self.runtime.register_email_connection(
                tenant, "owner", "email_conn_123", sender,
            )
        self.intents: dict[tuple[str, str], str] = {}

    @rule(
        tenant=st.sampled_from(["tenant-a", "tenant-b"]),
        key=st.integers(min_value=0, max_value=8),
        body=st.integers(min_value=0, max_value=8),
    )
    def send(self, tenant: str, key: int, body: int) -> None:
        request = SendEmailRequest(
            connection_ref="email_conn_123", idempotency_key=f"attempt-{key}",
            recipients=["to@example.test"], subject="subject", body=f"body-{body}",
        )
        model_key = (tenant, request.idempotency_key)
        previous = self.intents.get(model_key)
        result = self.runtime.send_email(tenant, "owner", request)
        if previous is None:
            self.intents[model_key] = request.intent_digest()
            assert isinstance(result, EmailReceipt)
        elif previous == request.intent_digest():
            assert isinstance(result, EmailReceipt)
        else:
            assert isinstance(result, EmailIdempotencyConflict)

    @rule(tenant=st.sampled_from(["tenant-a", "tenant-b"]))
    def foreign_owner_cannot_resolve(self, tenant: str) -> None:
        request = SendEmailRequest(
            connection_ref="email_conn_123", idempotency_key="foreign-1",
            recipients=["to@example.test"], subject="subject", body="body",
        )
        assert self.runtime.send_email(tenant, "foreign", request) is None

    @invariant()
    def effects_equal_unique_tenant_key_intents(self) -> None:
        for tenant, sender in self.senders.items():
            expected = len({key for key in self.intents if key[0] == tenant})
            assert sender.send_count == expected


TestEmailRegistryStateMachine = EmailRegistryMachine.TestCase
TestEmailRegistryStateMachine.settings = settings(
    max_examples=50, stateful_step_count=30, deadline=None,
)
