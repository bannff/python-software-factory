"""Docs, prompts and SKILL.md snippets must call tools with args the schema accepts (#405)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ._tool_call_args import check_file, public_input_schemas

_ROOT = Path(__file__).resolve().parents[5]
_SKILLS = _ROOT / "components/agent/src/factory/agent/skills"
_DOC_SOURCES = (
    "components/security/src/factory/security/mcp/prompts.py",
    "components/kb/src/factory/kb/mcp/docs_content.py",
    "components/logger/src/factory/logger/mcp/docs.py",
)
# Tools whose call shapes were audited; extend as more docs are brought in line.
_CHECKED = frozenset({
    "dataset_submit_generation", "graph_add_entity", "graph_add_relationship",
    "agent_invoke_swarm", "storage_graph_query", "logger_info",
})
_LEGACY = ("spawn_swarm(swarm_id", "logger.info(", "graph_query(query_str")


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    found = public_input_schemas(("agent", "dataset", "graph", "storage", "logger"))
    assert _CHECKED <= found.keys(), "checked tool renamed; update _CHECKED"
    return found


def _problems(paths: list[Path], schemas: dict[str, dict]) -> list[str]:
    return [
        str(p) for f in paths
        for p in check_file(f, schemas, _CHECKED, str(f.relative_to(_ROOT)))
    ]


def test_skill_snippets_use_schema_valid_arguments(schemas: dict[str, dict]) -> None:
    assert _problems(sorted(_SKILLS.glob("*/SKILL.md")), schemas) == []


def test_prompts_and_docs_use_schema_valid_arguments(schemas: dict[str, dict]) -> None:
    assert _problems([_ROOT / p for p in _DOC_SOURCES], schemas) == []


@pytest.mark.parametrize("rel", _DOC_SOURCES)
def test_legacy_call_names_are_gone(rel: str) -> None:
    text = (_ROOT / rel).read_text()
    assert [s for s in _LEGACY if s in text] == []
