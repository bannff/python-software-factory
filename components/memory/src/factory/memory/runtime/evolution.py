"""Memory evolution engine — Zettelkasten-style self-evolving connections.

Implements the core A-MEM innovation: when new memories are stored,
an LLM analyzes them against existing neighbors and decides whether
to strengthen connections or update neighbor metadata.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

TAXONOMY_CONTEXT = """Memory categories: preference, fact, summary, context, custom.
Cross-domain node types: KBDocument (knowledge base), Finding (security), Event (system/agent), Agent.
Memory relationships: RELATED_TO (semantic), EVOLVED_FROM (version trail), FOLLOWED_BY (temporal).
Cross-domain edges: REFERENCES (Memory→KBDocument), MENTIONS (Memory→Finding), HAS_MEMORY (Agent→Memory).
When generating tags, prefer domain-specific terms over generic ones.
When generating context, reference which domain(s) the content relates to."""

EVOLUTION_SYSTEM_PROMPT = """You are an AI memory evolution agent responsible for managing and evolving a knowledge base.
{taxonomy}
Analyze the new memory note according to keywords and context, along with its nearest neighbor memories.
Make decisions about its evolution.

The new memory context: {context}
content: {content}
keywords: {keywords}

The nearest neighbors memories (each line starts with memory_id):
{neighbors}

Based on this information, determine:
1. Should this memory be evolved? Consider its relationships with other memories.
2. What specific actions should be taken (strengthen, update_neighbor)?
   2.1 If strengthen: which memory should it be connected to? Use the memory_id from neighbors. Give updated tags.
   2.2 If update_neighbor: update the context and tags of neighbors based on understanding of all memories.

The number of neighbors is {neighbor_count}.
Return your decision in JSON format:
{{
    "should_evolve": true or false,
    "actions": ["strengthen", "update_neighbor"],
    "suggested_connections": ["memory_id_1", "memory_id_2"],
    "tags_to_update": ["tag_1", "tag_n"],
    "new_context_neighborhood": ["new context for each neighbor"],
    "new_tags_neighborhood": [["tag_1", "tag_n"], ["tag_1", "tag_n"]]
}}"""

ANALYSIS_PROMPT = """Generate a structured analysis of the following content.

{taxonomy}

Instructions:
1. Identify the most salient keywords (nouns, verbs, key concepts). Prefer domain-specific terms.
2. Extract core themes and write a one-sentence context summary. Reference which domain(s) apply.
3. Create relevant categorical tags. Use domain-aware tags (e.g. "security", "knowledge-base", \
"agent-workflow") over generic ones.

Return JSON:
{{"keywords": ["keyword1", "keyword2"], "context": "one sentence summary referencing domain", \
"tags": ["domain-specific-tag1", "tag2"]}}

Content: {content}"""


@dataclass
class EvolutionResult:
    """Result of memory evolution analysis."""

    should_evolve: bool = False
    connections: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    neighbor_updates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NeighborInfo:
    """Lightweight neighbor data for evolution prompt."""

    memory_id: str
    content: str
    context: str
    keywords: list[str]
    tags: list[str]
    timestamp: str = ""


class EvolutionEngine:
    """Decides how new memories should connect to existing ones."""

    def __init__(self, llm_complete: Any) -> None:
        """Args:
            llm_complete: Callable (prompt: str) -> str.
                          Obtained from llm_gateway's completion interface.
        """
        self._complete = llm_complete

    def analyze(
        self,
        content: str,
        context: str,
        keywords: list[str],
        tags: list[str],
        neighbors: list[NeighborInfo],
    ) -> EvolutionResult:
        """Analyze a new memory against its neighbors for evolution."""
        if not neighbors:
            return EvolutionResult()

        neighbors_text = "\n".join(
            f"memory_id:{n.memory_id}\tcontent: {n.content}\tcontext: {n.context}\t"
            f"keywords: {n.keywords}\ttags: {n.tags}"
            for n in neighbors
        )
        prompt = EVOLUTION_SYSTEM_PROMPT.format(
            content=content,
            context=context,
            keywords=keywords,
            neighbors=neighbors_text,
            neighbor_count=len(neighbors),
            taxonomy=TAXONOMY_CONTEXT,
        )
        try:
            raw = self._complete(prompt)
            return self._parse_response(raw, neighbors)
        except Exception as e:
            logger.warning("Evolution analysis failed: %s", e)
            return EvolutionResult()

    def _parse_response(
        self, raw: str, neighbors: list[NeighborInfo]
    ) -> EvolutionResult:
        """Parse LLM JSON response into EvolutionResult."""
        data = json.loads(raw)
        if not data.get("should_evolve", False):
            return EvolutionResult()

        neighbor_updates: list[dict[str, Any]] = []
        actions = data.get("actions", [])
        if "update_neighbor" in actions:
            contexts = data.get("new_context_neighborhood", [])
            tags_list = data.get("new_tags_neighborhood", [])
            for i, n in enumerate(neighbors):
                update: dict[str, Any] = {"memory_id": n.memory_id}
                if i < len(contexts):
                    update["context"] = contexts[i]
                if i < len(tags_list):
                    update["tags"] = tags_list[i]
                neighbor_updates.append(update)

        return EvolutionResult(
            should_evolve=True,
            connections=data.get("suggested_connections", []),
            tags=data.get("tags_to_update", []),
            neighbor_updates=neighbor_updates,
        )


def analyze_content(llm_complete: Any, content: str) -> dict[str, Any]:
    """Extract keywords, context, and tags from content via LLM."""
    try:
        raw = llm_complete(ANALYSIS_PROMPT.format(
            content=content, taxonomy=TAXONOMY_CONTEXT))
        return json.loads(raw)
    except Exception as e:
        logger.warning("Content analysis failed: %s", e)
        return {"keywords": [], "context": "General", "tags": []}
