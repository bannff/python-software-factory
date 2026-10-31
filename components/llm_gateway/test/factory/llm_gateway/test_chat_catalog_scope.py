"""Deployment-scoped chat-model catalog (#136).

Before #136 ``list_chat_models`` unconditionally merged the live OpenRouter
catalog, so a 453-id provider list read as 453 *configured* models and the
picker pill could print a selector that was not what would actually run. These
tests pin the scoped projection, both opt-ins (argument and deployment knob),
``include`` resolution, and the row-ordering rule that keeps a
deployment-configured row owning its ``(provider, model)`` slot.
"""
from __future__ import annotations

import json
import time

import pytest

from factory.llm_gateway.runtime.chat_catalog import (
    MODEL_CATALOG_SCOPE_ENV,
    list_chat_models,
)

LIVE_COUNT = 453


@pytest.fixture
def live_catalog(monkeypatch, tmp_path):
    """A fresh v2 cache holding 453 provider ids, plus an OpenRouter default."""
    ids = [f"vendor{i % 7}/model-{i}" for i in range(LIVE_COUNT)]
    path = tmp_path / "models.json"
    path.write_text(json.dumps({
        "schema_version": 2, "fetched_at": time.time(),
        "models": ids, "pricing": {},
    }))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-openrouter-key")
    monkeypatch.setenv("COMPANION_X_MODEL_CATALOG_CACHE", str(path))
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "openrouter")
    monkeypatch.delenv("COMPANION_X_OPENAI_COMPAT_PROFILES", raising=False)
    monkeypatch.delenv(MODEL_CATALOG_SCOPE_ENV, raising=False)
    return ids


def test_453_model_catalog_marks_exactly_one_row_configured(live_catalog) -> None:
    """The requested pin: 453 live rows must never read as 453 configured models."""
    scoped = list_chat_models()
    assert scoped.scope == "configured"
    assert [row.model_id for row in scoped.models] == ["openrouter"]
    assert all(row.configured for row in scoped.models)
    assert scoped.hidden_count == LIVE_COUNT

    full = list_chat_models(scope="all")
    assert full.scope == "all"
    assert len(full.models) == LIVE_COUNT + 1, "the configured selector plus every live id"
    assert sum(1 for row in full.models if row.configured) == 1
    assert (full.models[0].model_id, full.models[0].configured) == ("openrouter", True)
    assert full.models[0].effective_model_id == "openrouter/deepseek/deepseek-v4-flash"
    assert full.hidden_count == 0, "nothing is withheld from the full projection"
    assert "sentinel" not in repr(full) and "API_KEY" not in repr(full)


def test_unknown_scope_env_value_serves_the_scoped_projection(live_catalog, monkeypatch) -> None:
    monkeypatch.setenv(MODEL_CATALOG_SCOPE_ENV, "banana")
    served = list_chat_models(scope="all")
    assert served.scope == "configured"
    assert [row.model_id for row in served.models] == ["openrouter"]


def test_scope_env_full_serves_the_live_catalog_without_the_argument(live_catalog, monkeypatch) -> None:
    monkeypatch.setenv(MODEL_CATALOG_SCOPE_ENV, "full")
    served = list_chat_models()
    assert served.scope == "all"
    assert len(served.models) == LIVE_COUNT + 1


def test_include_resolves_a_scoped_row_and_reports_unresolvable_selectors(live_catalog) -> None:
    served = list_chat_models(include=("openrouter/vendor0/model-0", "openrouter/"))
    by_id = {row.model_id: row for row in served.models}
    assert served.scope == "configured"
    assert by_id["openrouter"].configured is True
    assert by_id["openrouter/vendor0/model-0"].configured is False
    assert served.unresolved == ("openrouter/",), "a selector nothing can resolve is reported, not hidden"
    assert served.hidden_count == LIVE_COUNT - 1, "the included row stops being withheld"


def test_include_rows_follow_configured_and_openai_compat_rows(live_catalog, monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "lm-studio")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "sentinel-secret")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")
    # The second include resolves to the SAME model as the configured default:
    # the configured row must keep the slot (first-seen-wins, appended last).
    served = list_chat_models(
        include=("openrouter/vendor0/unlisted", "openrouter/deepseek/deepseek-v4-flash"),
    )
    assert [row.model_id for row in served.models] == [
        "openrouter", "openai-compat/lm-studio", "openrouter/vendor0/unlisted",
    ]
    assert [row.configured for row in served.models] == [True, True, False]
    assert served.unresolved == ()


def test_included_unresolvable_selector_never_fails_the_catalog(live_catalog) -> None:
    served = list_chat_models(include=("openai-compat/not-allowlisted",))
    assert [row.model_id for row in served.models] == ["openrouter"]
    assert served.unresolved == ("openai-compat/not-allowlisted",)
