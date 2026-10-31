"""Test-only DCAL fixtures; never exported by the runtime/dcal package."""
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from factory.blockchain.mcp.contracts.dcal import TrustedBinding
from factory.blockchain.runtime.dcal import authorization
from factory.blockchain.runtime.dcal.trusted import TrustedEnvelope


def trusted_permit(binding: TrustedBinding) -> TrustedEnvelope:
    """Construct an opaque test double without creating a production mint path."""
    permit = object.__new__(TrustedEnvelope)
    object.__setattr__(permit, "binding", binding)
    object.__setattr__(permit, "_permit", object())
    return permit


@contextmanager
def authenticated_dcal_context(monkeypatch: Any, binding: TrustedBinding) -> Iterator[TrustedEnvelope]:
    """Temporarily resolve only this fixture's exact opaque permit."""
    permit = trusted_permit(binding)
    with monkeypatch.context() as scoped:
        scoped.setattr(
            authorization,
            "resolve_trusted_envelope",
            lambda candidate: permit if candidate is permit else None,
        )
        yield permit


@contextmanager
def unauthenticated_dcal_context(monkeypatch: Any) -> Iterator[None]:
    """Temporarily make the authorization seam reject every candidate."""
    with monkeypatch.context() as scoped:
        scoped.setattr(authorization, "resolve_trusted_envelope", lambda _: None)
        yield None
