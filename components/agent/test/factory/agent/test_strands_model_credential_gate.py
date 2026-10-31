"""Typed credential no-go for the agent chat builders.

Epic #124 S3: when AWS credentials do not resolve, every builder site raises
a named :class:`AgentCredentialError` instead of letting botocore's bare
``AttributeError`` (``'NoneType' object has no attribute ...``) or
``ProfileNotFound`` leak out of the strands/LangChain construction path.
"""
from __future__ import annotations

import pytest

from factory.agent.runtime.adapters import aws_creds
from factory.agent.runtime.adapters.langchain_model import build_langchain_chat_model
from factory.agent.runtime.adapters.strands_model import build_strands_model
from factory.llm_gateway.interface import AgentCredentialError

_DEPLOYED_SELECTOR = "us.anthropic.claude-sonnet-4-6"


def _no_creds_session():
    raise AgentCredentialError("no AWS credentials resolve")


def _attr_error_session():
    raise AttributeError("'NoneType' object has no attribute 'access_key'")


def test_no_credentials_resolve_to_typed_error_not_bare_attribute_error(monkeypatch) -> None:
    """Underlying fail mode from the field: refreshable creds raise a bare
    AttributeError from botocore; the strands builder must convert it."""
    monkeypatch.setattr(aws_creds, "get_refreshable_session", _attr_error_session)

    with pytest.raises(AgentCredentialError) as excinfo:
        build_strands_model(_DEPLOYED_SELECTOR)

    assert "no AWS credentials resolve" in str(excinfo.value)


def test_bedrock_model_with_unresolved_credentials_surfacing_named_no_go(monkeypatch) -> None:
    """Passthrough shape: an already-typed no-go from the creds factory is
    re-raised verbatim by the builder (not wrapped again nor swallowed)."""
    monkeypatch.setattr(aws_creds, "get_refreshable_session", _no_creds_session)

    for build in (build_strands_model, build_langchain_chat_model):
        with pytest.raises(AgentCredentialError) as excinfo:
            build(_DEPLOYED_SELECTOR)
        assert "no AWS credentials resolve" in str(excinfo.value)


def test_aws_creds_resolver_reports_typed_error_when_none_resolve(monkeypatch) -> None:
    """Pipeline underline: the disk-read resolver itself never lets a raw
    AttributeError out of the credential resolution step."""
    class _EmptySession:
        def get_credentials(self):
            return None

    monkeypatch.setattr(
        aws_creds.botocore.session, "Session",
        staticmethod(lambda profile=None: _EmptySession()),
    )

    with pytest.raises(AgentCredentialError) as excinfo:
        aws_creds._read_creds_from_disk(None)

    assert "no AWS credentials resolve" in str(excinfo.value)
