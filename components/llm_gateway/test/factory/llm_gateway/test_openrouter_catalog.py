"""Live OpenRouter catalog: fetch, cache, offline fallback, no secret egress."""
from __future__ import annotations

import json

import httpx
import pytest

from factory.llm_gateway.runtime import openrouter_catalog as catalog
from factory.llm_gateway.runtime.chat_catalog import list_chat_models

PAYLOAD = {"data": [
    {"id": "deepseek/deepseek-v4-flash"}, {"id": "anthropic/claude-sonnet-4.6"},
    {"id": "openai/gpt-5"}, {"id": "bad id with spaces"}, {"id": 42}, {"nope": 1},
]}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "openrouter")
    monkeypatch.setenv("COMPANION_X_MODEL_CATALOG_CACHE", str(tmp_path / "models.json"))
    monkeypatch.delenv("COMPANION_X_OPENAI_COMPAT_PROFILES", raising=False)
    return tmp_path / "models.json"


def _client(monkeypatch, handler):
    calls = {"count": 0}

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return handler(request)

    real = httpx.Client
    monkeypatch.setattr(catalog.httpx, "Client", lambda **kw: real(
        transport=httpx.MockTransport(wrapped), **kw,
    ))
    return calls


def test_fetch_filters_invalid_ids_and_caches(configured, monkeypatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        seen["url"] = str(request.url)
        return httpx.Response(200, json=PAYLOAD)

    calls = _client(monkeypatch, handler)
    models = catalog.openrouter_models()
    assert models == (
        "anthropic/claude-sonnet-4.6", "deepseek/deepseek-v4-flash", "openai/gpt-5",
    )
    assert seen["auth"] == "Bearer sentinel-openrouter-key"
    assert seen["url"].endswith("/models")
    assert json.loads(configured.read_text())["models"] == list(models)
    assert catalog.openrouter_models() == models
    assert calls["count"] == 1, "fresh cache must be served without a second fetch"
    assert catalog.openrouter_models(refresh=True) == models
    assert calls["count"] == 2


def test_offline_falls_back_to_last_cache(configured, monkeypatch) -> None:
    configured.write_text(json.dumps({"fetched_at": 0, "models": ["x/y"]}))

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    _client(monkeypatch, handler)
    assert catalog.openrouter_models() == ("x/y",)


def test_no_cache_and_offline_is_empty_not_error(configured, monkeypatch) -> None:
    _client(monkeypatch, lambda _r: httpx.Response(503))
    assert catalog.openrouter_models() == ()


def test_catalog_merges_live_models_after_default_without_secrets(configured, monkeypatch) -> None:
    _client(monkeypatch, lambda _r: httpx.Response(200, json=PAYLOAD))
    models = list_chat_models(scope="all").models
    ids = [item.model_id for item in models]
    assert ids[0] == "openrouter"
    assert "openrouter/anthropic/claude-sonnet-4.6" in ids
    assert "openrouter/deepseek/deepseek-v4-flash" not in ids, "default de-duplicated by (provider, model)"
    assert all(item.provider == "openrouter" for item in models)
    assert "sentinel" not in repr(models) and "API_KEY" not in repr(models)


def test_catalog_skips_live_fetch_without_openrouter_key(configured, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY")
    calls = _client(monkeypatch, lambda _r: httpx.Response(200, json=PAYLOAD))
    assert [item.model_id for item in list_chat_models(scope="all").models] == ["openrouter"]
    assert calls["count"] == 0


PRICED_PAYLOAD = {"data": [
    {"id": "deepseek/deepseek-v4-flash", "pricing": {"prompt": "0.0000002", "completion": "0.0000008"}},
    {"id": "anthropic/claude-sonnet-4.6", "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
    {"id": "openai/gpt-5", "pricing": {"prompt": "not-a-number", "completion": "0.00001"}},  # malformed -> dropped
    {"id": "meta/llama-free"},  # no pricing key at all -> absent, not a crash
]}


def test_pricing_is_extracted_cached_and_survives_a_reload(configured, monkeypatch) -> None:
    _client(monkeypatch, lambda _r: httpx.Response(200, json=PRICED_PAYLOAD))
    pricing = catalog.openrouter_pricing()
    assert pricing["deepseek/deepseek-v4-flash"].prompt_usd_per_token == 0.0000002
    assert pricing["deepseek/deepseek-v4-flash"].completion_usd_per_token == 0.0000008
    assert pricing["anthropic/claude-sonnet-4.6"].prompt_usd_per_token == 0.000003
    assert "openai/gpt-5" not in pricing, "malformed pricing must be dropped, not crash or mislead"
    assert "meta/llama-free" not in pricing, "absent pricing key must not fabricate a $0 entry"

    on_disk = json.loads(configured.read_text())
    assert on_disk["pricing"]["deepseek/deepseek-v4-flash"] == {"prompt": 0.0000002, "completion": 0.0000008}

    # A fresh read (simulating a new process) must reconstruct the same pricing from cache alone.
    reloaded = catalog._read_cache()
    assert reloaded is not None
    assert reloaded[2]["deepseek/deepseek-v4-flash"].prompt_usd_per_token == 0.0000002


def test_list_chat_models_projects_pricing_only_for_openrouter_entries(configured, monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "lm-studio")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "sentinel")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")
    _client(monkeypatch, lambda _r: httpx.Response(200, json=PRICED_PAYLOAD))
    by_model_id = {item.model_id: item for item in list_chat_models(scope="all").models}
    # The bare "openrouter" default (deduped to the configured OPENROUTER_MODEL,
    # deepseek/deepseek-v4-flash per the `configured` fixture) carries its price.
    assert by_model_id["openrouter"].pricing is not None
    assert by_model_id["openrouter"].pricing.prompt_usd_per_token > 0
    # A distinct live-catalog entry (not deduped into the default) also prices.
    other = by_model_id["openrouter/anthropic/claude-sonnet-4.6"]
    assert other.pricing is not None and other.pricing.prompt_usd_per_token > 0
    compat = by_model_id["openai-compat/lm-studio"]
    assert compat.pricing is None, "no public pricing source for a local endpoint"


def test_negative_or_nan_pricing_is_treated_as_malformed(configured, monkeypatch) -> None:
    bad = {"data": [{"id": "x/y", "pricing": {"prompt": "-1", "completion": "0.001"}}]}
    _client(monkeypatch, lambda _r: httpx.Response(200, json=bad))
    assert catalog.openrouter_pricing() == {}


def test_pre_pricing_cache_triggers_a_live_refetch_when_reachable(configured, monkeypatch) -> None:
    """Real live bug: a cache written by the pre-pricing code (no
    `schema_version`, no `pricing` key) was being served as 'fresh' forever
    within its TTL, so pricing silently never appeared for any process that
    already had a recent cache on disk — the exact failure mode found live
    on a real smoke instance. A pre-v2 cache must never be trusted as
    complete; when the network is reachable it must trigger one real
    re-fetch instead of silently continuing to serve prices as absent."""
    configured.write_text(json.dumps({"fetched_at": __import__("time").time(), "models": ["x/y"]}))
    calls = _client(monkeypatch, lambda _r: httpx.Response(200, json=PRICED_PAYLOAD))
    pricing = catalog.openrouter_pricing()
    assert calls["count"] == 1, "an old-schema cache must not be treated as fresh"
    assert pricing["deepseek/deepseek-v4-flash"].prompt_usd_per_token > 0


def test_pre_pricing_cache_still_serves_models_when_genuinely_offline(configured, monkeypatch) -> None:
    configured.write_text(json.dumps({"fetched_at": __import__("time").time(), "models": ["x/y"]}))

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    _client(monkeypatch, handler)
    assert catalog.openrouter_models() == ("x/y",)
    assert catalog.openrouter_pricing() == {}, "an old cache has no pricing to offer offline — never fabricate it"
