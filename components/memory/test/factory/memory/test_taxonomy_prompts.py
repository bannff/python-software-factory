"""Tests for taxonomy-aware prompts in evolution.py.

Covers: TAXONOMY_CONTEXT content, placeholder presence in prompts,
analyze_content taxonomy formatting, EvolutionEngine.analyze taxonomy.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from factory.memory.runtime.evolution import (
    ANALYSIS_PROMPT,
    EVOLUTION_SYSTEM_PROMPT,
    TAXONOMY_CONTEXT,
    EvolutionEngine,
    NeighborInfo,
    analyze_content,
)


class TestTaxonomyContext:
    def test_non_empty(self):
        assert len(TAXONOMY_CONTEXT) > 0

    def test_contains_memory_categories(self):
        assert "Memory categories" in TAXONOMY_CONTEXT

    def test_contains_cross_domain_types(self):
        assert "KBDocument" in TAXONOMY_CONTEXT
        assert "Finding" in TAXONOMY_CONTEXT

    def test_contains_relationship_types(self):
        assert "RELATED_TO" in TAXONOMY_CONTEXT
        assert "EVOLVED_FROM" in TAXONOMY_CONTEXT


class TestAnalysisPromptPlaceholders:
    def test_contains_taxonomy_placeholder(self):
        assert "{taxonomy}" in ANALYSIS_PROMPT

    def test_contains_content_placeholder(self):
        assert "{content}" in ANALYSIS_PROMPT

    def test_formats_without_error(self):
        result = ANALYSIS_PROMPT.format(content="test text", taxonomy=TAXONOMY_CONTEXT)
        assert "test text" in result
        assert "Memory categories" in result


class TestEvolutionSystemPromptPlaceholders:
    def test_contains_taxonomy_placeholder(self):
        assert "{taxonomy}" in EVOLUTION_SYSTEM_PROMPT

    def test_contains_all_required_placeholders(self):
        for ph in ["{content}", "{context}", "{keywords}", "{neighbors}",
                   "{neighbor_count}", "{taxonomy}"]:
            assert ph in EVOLUTION_SYSTEM_PROMPT, f"Missing {ph}"


class TestAnalyzeContentTaxonomy:
    def test_taxonomy_in_llm_prompt(self):
        llm = MagicMock(return_value='{"keywords":["k"],"context":"c","tags":["t"]}')
        analyze_content(llm, "some content")
        prompt_sent = llm.call_args[0][0]
        assert "Memory categories" in prompt_sent
        assert "some content" in prompt_sent

    def test_fallback_on_llm_failure(self):
        llm = MagicMock(side_effect=RuntimeError("fail"))
        result = analyze_content(llm, "content")
        assert result == {"keywords": [], "context": "General", "tags": []}


class TestEvolutionEngineAnalyzeTaxonomy:
    def test_taxonomy_in_evolution_prompt(self):
        llm = MagicMock(return_value=json.dumps({
            "should_evolve": False, "actions": [],
            "suggested_connections": [], "tags_to_update": [],
        }))
        engine = EvolutionEngine(llm)
        neighbor = NeighborInfo(
            memory_id="n1", content="neighbor", context="ctx",
            keywords=["k"], tags=["t"],
        )
        engine.analyze(
            content="new memory", context="ctx",
            keywords=["k"], tags=["t"], neighbors=[neighbor],
        )
        prompt_sent = llm.call_args[0][0]
        assert "Memory categories" in prompt_sent
        assert "new memory" in prompt_sent

    def test_empty_neighbors_returns_default(self):
        engine = EvolutionEngine(MagicMock())
        result = engine.analyze("c", "ctx", ["k"], ["t"], neighbors=[])
        assert result.should_evolve is False
