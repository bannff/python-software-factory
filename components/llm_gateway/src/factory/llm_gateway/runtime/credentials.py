"""Typed credential no-go for chat model builders.

The gateway is the selection/identity authority (router posture, epic #124
S3): a profile whose provider needs cloud credentials that do not resolve
must surface as a *named* ``AgentCredentialError``, never as botocore's raw
``ProfileNotFound``/``NoCredentialsError``/``AttributeError`` noise. The
message names the configuration to fix so builders, ``/api/health``, and the
side-chat planner all report the same actionable no-go.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


class AgentCredentialError(RuntimeError):
    """Named no-go: the resolved chat profile needs credentials that did not resolve."""


def credential_failure(exc: Exception) -> bool:
    """Whether ``exc`` is a credentials-resolution failure (not a transport one)."""
    import botocore.exceptions

    if isinstance(exc, AgentCredentialError):
        return False
    cred_errors = (
        botocore.exceptions.ProfileNotFound,
        botocore.exceptions.NoCredentialsError,
        botocore.exceptions.UnknownCredentialError,
        botocore.exceptions.MetadataRetrievalError,
        AttributeError,
    )
    return isinstance(exc, cred_errors)


def no_credential_message(provider: str, cause: Exception) -> str:
    """One actionable hint per provider, taken from the underlying failure."""
    detail = " ".join(str(cause).split()) or type(cause).__name__
    if provider == "bedrock":
        return (
            f"Bedrock chat model unavailable: no AWS credentials resolve "
            f"({detail}) — configure AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
            f"or AWS_PROFILE"
        )
    return f"{provider} chat model unavailable: credentials did not resolve ({detail})"


@contextmanager
def credential_gate(provider: str) -> Iterator[None]:
    """Convert credentials-resolution failures inside the block to a typed
    ``AgentCredentialError``; every other failure passes through untouched."""
    try:
        yield
    except AgentCredentialError:
        raise
    except Exception as exc:
        if not credential_failure(exc):
            raise
        raise AgentCredentialError(no_credential_message(provider, exc)) from exc


__all__ = ["AgentCredentialError", "credential_gate", "credential_failure"]
