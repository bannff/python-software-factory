"""Edge-case Hypothesis properties for the unified persona registry
(bd:python-factory-d4roe.1, meta-architect verdict ``9d6a73fb`` Q2).

Complements ``test_unified_registry_properties.py`` (which dedups both
input lists before merging) by pinning the contracts that surface only
when the inputs are NOT pre-deduped or are partially corrupt:

* in-store DUPLICATE ids resolve LAST-WINS (``merged[id] = cfg`` in
  iteration order) — the read path is deterministic for the same file
  ordering ``DiskRegistryStore`` produces (``sorted(glob)``).
* id case-collision is closed AT THE CONTRACT — ``AgentConfig.id`` is
  lowercase-only (bd-67qvz), so a case-only variant of a built-in
  (``Companion-X-Default``) can't even be constructed; a byte-exact id
  is still rejected by the merge and the built-in always wins.
* ``DiskRegistryStore`` is RESILIENT — a malformed / non-dict /
  extra-key file is logged-and-skipped (adapter docstring contract) so
  one bad file never sinks the valid personas beside it.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.agent.registry.unified import merge_personas
from factory.agent.runtime.adapters.registry_store import DiskRegistryStore
from factory.agent.runtime.registry_contracts import AgentConfig

# Contract-valid ids (lowercase alnum + -/_, first char alnum). The
# AgentConfig.id validator (bd-67qvz) rejects anything else.
_id_strategy = st.from_regex(r"[a-z0-9][a-z0-9_-]{0,23}", fullmatch=True)

# Disk-backed properties must use a CASE-STABLE id alphabet: on a
# case-insensitive filesystem (macOS APFS / Windows) two ids differing
# only by case map to the SAME ``<id>.yaml`` file, so the disk adapter
# would collapse them while an exact-keyed dict would not. That
# divergence is a real (separately tracked) finding — these properties
# deliberately avoid triggering it so they stay deterministic.
_disk_id_strategy = st.text(
    min_size=1, max_size=24,
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
).filter(lambda s: s[0].isalnum())


def _mk(id_: str, name: str = "n", model: str = "m1", prompt: str = "p") -> AgentConfig:
    return AgentConfig(id=id_, name=name, model=model, system_prompt=prompt)


@given(
    agent_id=_id_strategy,
    names=st.lists(st.text(min_size=1, max_size=12), min_size=2, max_size=6),
)
@settings(max_examples=50, deadline=None)
def test_in_store_duplicate_ids_last_wins(agent_id: str, names: list[str]) -> None:
    """Multiple store personas sharing one id collapse to a SINGLE entry
    keyed by that id, and the LAST occurrence wins (matches the
    ``dict[id] = cfg`` overlay semantics)."""
    store = [_mk(agent_id, name=nm) for nm in names]
    merged = merge_personas([], store)
    by_id = {c.id: c for c in merged}
    assert len(merged) == 1
    assert by_id[agent_id].name == names[-1]


@given(
    builtin_id=_id_strategy,
    builtin_name=st.text(min_size=1, max_size=12),
    user_name=st.text(min_size=1, max_size=12),
)
@settings(max_examples=50, deadline=None)
def test_collision_is_case_sensitive(
    builtin_id: str, builtin_name: str, user_name: str,
) -> None:
    """A byte-exact id collision drops the user persona (built-in wins),
    and a case-only variant is now closed at the CONTRACT: since
    ``AgentConfig.id`` is lowercase-only (bd-67qvz), the upper-cased
    variant cannot be constructed at all (raises ``ValidationError``),
    so it can never reach the merge to shadow a built-in."""
    builtin = _mk(builtin_id, name=builtin_name)

    # Exact collision: built-in wins, user dropped.
    exact = merge_personas([builtin], [_mk(builtin_id, name=user_name)])
    exact_by_id = {c.id: c for c in exact}
    assert exact_by_id[builtin_id] is builtin

    swapped = builtin_id.swapcase()
    if swapped != builtin_id:  # has at least one cased letter to differ on
        # The case-fold variant is REJECTED by the contract — it can't
        # be built, so it can't relocate the data-loss onto the merge.
        with pytest.raises(ValidationError):
            _mk(swapped, name=user_name)


@given(
    valid=st.lists(_disk_id_strategy, max_size=6, unique=True),
)
@settings(max_examples=50, deadline=None)
def test_disk_store_skips_corrupt_files(valid: list[str]) -> None:
    """``DiskRegistryStore.load_personas`` skips malformed / non-dict /
    extra-key files and still returns every VALID persona beside them —
    one bad file never sinks the registry, and no exception escapes."""
    tmp = Path(tempfile.mkdtemp(prefix="reg-corrupt-"))
    store = DiskRegistryStore(tmp)
    for vid in valid:
        store.save_persona(_mk(vid))

    # Inject corrupt files of several flavors (unique stems so they
    # don't clobber a valid <id>.yaml).
    (tmp / "zz_malformed.yaml").write_text("id: x\nname: [unterminated\n : :")
    (tmp / "zz_listy.yaml").write_text("- a\n- b\n")
    (tmp / "zz_extra.yaml").write_text(
        "id: zz-extra\nname: E\nmodel: m\nsystem_prompt: p\nbogus: 1\n")
    (tmp / "zz_empty.yaml").write_text("")

    loaded = {c.id for c in store.load_personas()}
    assert loaded == set(valid)


@given(
    agent_id=_disk_id_strategy,
    name=st.text(min_size=1, max_size=20),
)
@settings(max_examples=50, deadline=None)
def test_disk_store_id_derives_from_content_not_filename(
    agent_id: str, name: str,
) -> None:
    """A persona's id comes from FILE CONTENT, not the filename. A file
    whose stem differs from its ``id:`` still loads under the content
    id (the merge keys on content id, never the filename)."""
    tmp = Path(tempfile.mkdtemp(prefix="reg-namemismatch-"))
    store = DiskRegistryStore(tmp)
    cfg = _mk(agent_id, name=name)
    import yaml
    (tmp / "unrelated-filename.yaml").write_text(
        yaml.safe_dump(cfg.model_dump(), sort_keys=False))

    by_id = {c.id: c for c in store.load_personas()}
    assert agent_id in by_id
    assert by_id[agent_id] == cfg


# --- Contract id-rejection guard (bd-67qvz) -----------------------------
# The narrowed Hypothesis strategies above now emit ONLY contract-valid
# ids, so they no longer exercise the rejection path. This explicit pin
# guards the AgentConfig.id validator directly: case-fold + unicode-cased
# + path-separator ids MUST raise, so they can never reach disk/session.

@pytest.mark.parametrize(
    "bad_id",
    [
        "MyAgent",      # uppercase ASCII — the case-fold data-loss class
        "\u0162",       # unicode-cased (LATIN CAPITAL T WITH CEDILLA)
        "a/b",          # path separator — directory traversal vector
        "..",           # parent-dir reference — path-safety vector
    ],
)
def test_agent_config_id_rejects_unsafe_ids(bad_id: str) -> None:
    """``AgentConfig(id=...)`` REJECTS uppercase, unicode-cased, and
    path-separator ids (raises ``ValidationError``) — the single
    charset gate that protects every adapter + the Strands session-id
    path (bd-67qvz)."""
    with pytest.raises(ValidationError):
        AgentConfig(id=bad_id, name="n", model="m", system_prompt="p")


def test_agent_config_id_accepts_valid_lowercase_id() -> None:
    """A canonical lowercase id with '-'/'_'/digits still validates."""
    cfg = AgentConfig(
        id="my-agent_2", name="n", model="m", system_prompt="p")
    assert cfg.id == "my-agent_2"
