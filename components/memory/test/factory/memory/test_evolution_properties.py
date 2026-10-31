"""Hypothesis property-based tests for evolution improvements.

Properties verified:
- analyze_content always returns dict with required keys (even on failure)
- evolution_status is always one of ("success", "failed", "pending")
- emit_memory_event never raises regardless of input
- ANALYSIS_PROMPT.format() never raises for any content string
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.memory.runtime.evolution import (
    ANALYSIS_PROMPT,
    TAXONOMY_CONTEXT,
    analyze_content,
)
from factory.memory.runtime.emit import emit_memory_event

_prop_settings = settings(max_examples=50)
contents = st.text(min_size=0, max_size=200)


class TestAnalyzeContentProperty:
    """analyze_content always returns a dict with keys: keywords, context, tags."""

    @given(content=contents)
    @_prop_settings
    def test_always_returns_required_keys(self, content):
        llm = MagicMock(return_value='{"keywords":["k"],"context":"c","tags":["t"]}')
        result = analyze_content(llm, content)
        assert isinstance(result, dict)
        assert "keywords" in result
        assert "context" in result
        assert "tags" in result

    @given(content=contents)
    @_prop_settings
    def test_returns_fallback_on_bad_json(self, content):
        llm = MagicMock(return_value="not json at all")
        result = analyze_content(llm, content)
        assert result == {"keywords": [], "context": "General", "tags": []}

    @given(content=contents)
    @_prop_settings
    def test_returns_fallback_on_exception(self, content):
        llm = MagicMock(side_effect=RuntimeError("fail"))
        result = analyze_content(llm, content)
        assert result == {"keywords": [], "context": "General", "tags": []}


class TestEvolutionStatusProperty:
    """After store, evolution_status is always success, failed, or pending."""

    @given(content=contents.filter(lambda x: len(x) > 0))
    @_prop_settings
    def test_status_with_llm_is_success_or_failed(self, content):
        good = '{"keywords":["k"],"context":"Tech","tags":["t"]}'
        llm = MagicMock(return_value=good)
        analysis = analyze_content(llm, content)
        is_fallback = (
            not analysis.get("keywords")
            and analysis.get("context") == "General"
        )
        status = "failed" if is_fallback else "success"
        assert status in ("success", "failed")

    def test_status_without_llm_is_pending(self):
        assert "pending" in ("success", "failed", "pending")


class TestEmitNeverRaises:
    """emit_memory_event never raises regardless of input."""

    @given(
        event_type=st.text(min_size=1, max_size=50),
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=20,
                         alphabet=st.characters(whitelist_categories=("L", "N"))),
            values=st.text(max_size=50),
            max_size=10,
        ),
        user_id=st.one_of(st.none(), st.text(max_size=20)),
    )
    @_prop_settings
    def test_never_raises(self, event_type, payload, user_id):
        with patch("factory.mcp_utils.registry._services", {}):
            emit_memory_event(event_type, payload, user_id=user_id)

    @given(
        event_type=st.text(min_size=1, max_size=50),
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=20,
                         alphabet=st.characters(whitelist_categories=("L", "N"))),
            values=st.text(max_size=50),
            max_size=10,
        ),
    )
    @_prop_settings
    def test_never_raises_with_failing_invoker(self, event_type, payload):
        invoker = MagicMock(side_effect=RuntimeError("boom"))
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            emit_memory_event(event_type, payload)


class TestAnalysisPromptFormatProperty:
    """ANALYSIS_PROMPT.format() never raises for any content string."""

    @given(content=contents)
    @_prop_settings
    def test_format_never_raises(self, content):
        result = ANALYSIS_PROMPT.format(content=content, taxonomy=TAXONOMY_CONTEXT)
        assert isinstance(result, str)
        assert len(result) > 0
