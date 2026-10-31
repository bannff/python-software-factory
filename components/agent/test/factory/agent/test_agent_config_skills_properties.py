"""Property tests for ``AgentConfig.skills`` (bd:python-factory-hadbi.1).

The new field rounds-trips through ``model_dump`` / ``model_validate``
for any list of skill-dir-name strings, defaults to ``[]``, and
``extra="forbid"`` still rejects unknown keys (regression guard for
the contract change).
"""
from __future__ import annotations

import string

from hypothesis import given, settings, strategies as st
from pydantic import ValidationError
import pytest

from factory.agent.runtime.registry_contracts import AgentConfig

# Contract-valid ids (lowercase alnum + -/_, first char alnum). The
# AgentConfig.id validator (bd-67qvz) rejects a leading -/_ , so the
# strategy must only emit ids the contract accepts. Reused for ``name``
# (unconstrained) — a valid id is also a valid name.
_ids = st.from_regex(r"[a-z0-9][a-z0-9_-]{0,19}", fullmatch=True)
_models = st.sampled_from([
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "openai.gpt-oss-120b-1:0",
])
_skill_names = st.lists(
    st.text(alphabet=string.ascii_lowercase + "-",
            min_size=1, max_size=20).filter(bool),
    min_size=0, max_size=5,
)


@settings(max_examples=80, deadline=None)
@given(aid=_ids, name=_ids, model=_models, skills=_skill_names)
def test_skills_round_trip(
    aid: str, name: str, model: str, skills: list[str],
) -> None:
    """``AgentConfig.skills`` round-trips through model_dump/validate."""
    cfg = AgentConfig(
        id=aid, name=name, model=model,
        system_prompt="hi", skills=skills,
    )
    assert cfg.skills == skills
    rt = AgentConfig.model_validate(cfg.model_dump(by_alias=True))
    assert rt == cfg
    assert rt.skills == skills


def test_skills_defaults_to_empty_list() -> None:
    cfg = AgentConfig(
        id="a", name="b", model="us.anthropic.claude-sonnet-4-6",
        system_prompt="hi",
    )
    assert cfg.skills == []


def test_extra_forbid_still_active_with_skills_field() -> None:
    """Adding ``skills`` did not break ``extra="forbid"`` —
    unknown keys still raise."""
    with pytest.raises(ValidationError):
        AgentConfig.model_validate({
            "id": "a", "name": "b",
            "model": "us.anthropic.claude-sonnet-4-6",
            "system_prompt": "hi",
            "skills": [],
            "bogus_unknown_key": "x",
        })
