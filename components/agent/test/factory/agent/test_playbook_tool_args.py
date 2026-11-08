"""Red-team eval playbooks must call tools with their real input schemas (#403)."""
from __future__ import annotations

import re

import pytest

from factory.agent.registry import redteam_eval_playbooks as playbooks
from factory.mcp_server.runtime.lazy_loader import LazyBrickLoader
from factory.mcp_server.runtime.tool_catalog import build_tool_catalog

_BRICKS = ("evals", "games", "blockchain", "metrics", "memory")
_CALL = re.compile(r"\b((?:%s)_[a-z_]+)\(" % "|".join(_BRICKS))
_OPENERS, _CLOSERS = "([{", ")]}"


class _Agg:
    def __init__(self, lazy: object) -> None:
        self._lazy = lazy


def _keywords(text: str) -> set[str]:
    """Top-level ``name=`` keywords of the call whose '(' precedes ``text``."""
    depth, quote, token, keys = 1, "", "", set()
    for ch in text:
        if quote:
            quote = "" if ch == quote else quote
            token = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
            if depth == 0:
                return keys
        elif ch == "=" and depth == 1 and token:
            keys.add(token)
        token = token + ch if ch.isalnum() or ch == "_" else ""
    raise AssertionError(f"unbalanced call: {text[:60]!r}")


def _calls() -> list[tuple[str, str, set[str]]]:
    prompts = {k: v for k, v in vars(playbooks).items() if isinstance(v, str)}
    return [
        (var, m.group(1), _keywords(prompt[m.end():]))
        for var, prompt in prompts.items()
        for m in _CALL.finditer(prompt)
    ]


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    loader = LazyBrickLoader()
    loader.set_available(list(_BRICKS))
    catalog = build_tool_catalog(_Agg(loader))
    assert not catalog["bricks_failed"], catalog["bricks_failed"]
    return {t["qualified_name"]: t["input_schema"] for t in catalog["tools"]}


def test_playbooks_reference_tool_calls():
    assert len(_calls()) >= 8


def test_every_playbook_call_matches_its_input_schema(schemas):
    problems = []
    for var, tool, keys in _calls():
        schema = schemas.get(tool)
        if schema is None:
            problems.append(f"{var}: unknown tool {tool}")
            continue
        props = set(schema.get("properties", {}))
        problems += [f"{var}: {tool} has no param {k}" for k in sorted(keys - props)]
        problems += [f"{var}: {tool} missing required {r}"
                     for r in sorted(set(schema.get("required", [])) - keys)]
    assert not problems, "\n".join(problems)


def test_reward_transfer_uses_real_wallets():
    text = playbooks.LEARN_SYNTHESIZER
    assert "from_wallet='system'" not in text
    assert "wallet-treasury" in text and "blockchain_create_wallet(" in text


def test_finding_triage_game_is_seeded_with_ground_truth():
    text = playbooks.REVIEW_GAME_MASTER
    assert "ground_truth" in text and "findings_to_triage" in text
