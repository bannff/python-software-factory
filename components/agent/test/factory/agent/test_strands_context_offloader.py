"""ContextOffloader env wiring tests (issue #107, item 2).

Covers: unset backend → no plugin (default off); file backend mounts
with env thresholds; unknown backend fails loudly; s3 without bucket
fails loudly; the chat build mounts the plugin when the env is set.
"""
from __future__ import annotations

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_context_offloader import (
    offloader_plugin_from_env,
)

from ._strands_contract_fakes import NullClient, RepliedModel


def test_unset_backend_yields_no_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("STRANDS_OFFLOAD_BACKEND", "STRANDS_OFFLOAD_DIR",
                "STRANDS_OFFLOAD_MAX_TOKENS", "STRANDS_OFFLOAD_PREVIEW_TOKENS"):
        monkeypatch.delenv(var, raising=False)
    assert offloader_plugin_from_env() is None


def test_file_backend_mounts_with_env_thresholds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    monkeypatch.setenv("STRANDS_OFFLOAD_BACKEND", "file")
    monkeypatch.setenv("STRANDS_OFFLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("STRANDS_OFFLOAD_MAX_TOKENS", "9000")
    monkeypatch.setenv("STRANDS_OFFLOAD_PREVIEW_TOKENS", "300")
    plugin = offloader_plugin_from_env()
    assert plugin is not None
    assert plugin._max_result_tokens == 9_000
    assert plugin._preview_tokens == 300


def test_memory_backend_mounts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_OFFLOAD_BACKEND", "memory")
    assert offloader_plugin_from_env() is not None


def test_unknown_backend_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_OFFLOAD_BACKEND", "carrier-pigeon")
    with pytest.raises(ValueError, match="carrier-pigeon"):
        offloader_plugin_from_env()


def test_s3_without_bucket_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_OFFLOAD_BACKEND", "s3")
    monkeypatch.delenv("STRANDS_OFFLOAD_BUCKET", raising=False)
    with pytest.raises(ValueError, match="STRANDS_OFFLOAD_BUCKET"):
        offloader_plugin_from_env()


def test_chat_build_mounts_offloader_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent

    monkeypatch.setenv("STRANDS_OFFLOAD_BACKEND", "file")
    monkeypatch.setenv("STRANDS_OFFLOAD_DIR", str(tmp_path))
    chat = StrandsChatAgent(NullClient(), lambda _mid, **_kw: RepliedModel(), model_id="fake")

    async def _build() -> object:
        return await chat._agent_for("offload-thread", "companion-x-default")

    import asyncio
    agent = asyncio.run(_build())
    assert "skills" in agent.tool_registry.registry  # skills still mount
    names = list(agent._plugin_registry._plugins)
    assert "context_offloader" in names


def test_chat_build_skips_offloader_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent

    monkeypatch.delenv("STRANDS_OFFLOAD_BACKEND", raising=False)
    chat = StrandsChatAgent(NullClient(), lambda _mid, **_kw: RepliedModel(), model_id="fake")

    async def _build() -> object:
        return await chat._agent_for("no-offload-thread", "companion-x-default")

    import asyncio
    agent = asyncio.run(_build())
    names = list(agent._plugin_registry._plugins)
    assert "context_offloader" not in names
