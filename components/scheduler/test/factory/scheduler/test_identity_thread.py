from __future__ import annotations

import pytest

from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.scheduler.mcp.support import identity

AMBIENT = {"tenant_id": "tenant", "principal_id": "owner"}


def test_thread_comes_from_explicit_envelope_when_ambient_has_none() -> None:
    token = set_envelope(AMBIENT)
    try:
        assert identity({"thread_id": "thread-1"}) == ("tenant", "owner", "thread-1")
    finally:
        reset_envelope(token)


def test_ambient_authority_is_not_overridable_by_explicit_envelope() -> None:
    token = set_envelope(AMBIENT)
    try:
        assert identity({"tenant_id": "evil", "principal_id": "mallory", "thread_id": "t"})[:2] == (
            "tenant", "owner",
        )
    finally:
        reset_envelope(token)


def test_missing_thread_is_a_typed_identity_error() -> None:
    token = set_envelope(AMBIENT)
    try:
        with pytest.raises(ValueError, match="scheduler_identity_required"):
            identity({})
    finally:
        reset_envelope(token)
