"""Hypothesis property tests for CollectionRegistry and KBAuthoring.

Part A — CollectionRegistry properties:
- register-then-get roundtrip
- unregister existing returns True, get returns None
- unregister nonexistent returns False
- list_all returns all registered configs
- clear empties everything

Part B — KBAuthoring properties:
- disabled by default: mutating ops return ok=False
- upsert-then-validate roundtrip
- upsert-then-delete roundtrip
- delete nonexistent returns ok=False
- path traversal blocked
- absolute path blocked
"""

from __future__ import annotations

import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.kb.authoring import KBAuthoring
from factory.kb.runtime.collections import CollectionConfig, CollectionRegistry

_ids = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_configs = st.builds(CollectionConfig, id=_ids, name=_ids)


# ── Part A: CollectionRegistry ──────────────────────────────────────────────

@settings(max_examples=50, deadline=None)
@given(config=_configs)
def test_register_then_get_roundtrip(config: CollectionConfig) -> None:
    """Registered config is retrievable by id."""
    reg = CollectionRegistry()
    reg.register(config)
    assert reg.get(config.id) == config


@settings(max_examples=50, deadline=None)
@given(config=_configs)
def test_unregister_existing_returns_true(config: CollectionConfig) -> None:
    """Unregister returns True for existing, get returns None after."""
    reg = CollectionRegistry()
    reg.register(config)
    assert reg.unregister(config.id) is True
    assert reg.get(config.id) is None


@settings(max_examples=50, deadline=None)
@given(cid=_ids)
def test_unregister_nonexistent_returns_false(cid: str) -> None:
    """Unregister returns False for unknown id."""
    reg = CollectionRegistry()
    assert reg.unregister(cid) is False


@settings(max_examples=50, deadline=None)
@given(configs=st.lists(_configs, min_size=0, max_size=10, unique_by=lambda c: c.id))
def test_list_all_returns_all(configs: list[CollectionConfig]) -> None:
    """list_all length matches number of registered configs."""
    reg = CollectionRegistry()
    for c in configs:
        reg.register(c)
    assert len(reg.list_all()) == len(configs)


@settings(max_examples=50, deadline=None)
@given(configs=st.lists(_configs, min_size=1, max_size=5, unique_by=lambda c: c.id))
def test_clear_empties_everything(configs: list[CollectionConfig]) -> None:
    """After clear(), list_all() returns []."""
    reg = CollectionRegistry()
    for c in configs:
        reg.register(c)
    reg.clear()
    assert reg.list_all() == []


# ── Part B: KBAuthoring ────────────────────────────────────────────────────

@settings(max_examples=50, deadline=None)
@given(cid=_ids)
def test_disabled_by_default(cid: str) -> None:
    """Without env var, mutating ops return ok=False."""
    old = os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        data = {"id": cid, "name": "Test", "embedding_model": "default"}
        assert auth.upsert_collection_config(cid, data)["ok"] is False
        assert auth.delete_collection_config(cid)["ok"] is False
        assert auth.validate_collections()["ok"] is False
    finally:
        if old is not None:
            os.environ["KB_ENABLE_AUTHORING_TOOLS"] = old


@settings(max_examples=50, deadline=None)
@given(cid=_ids)
def test_upsert_then_validate_roundtrip(cid: str) -> None:
    """Upsert valid config, then validate_collections returns ok=True."""
    os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        data = {"id": cid, "name": "Test", "embedding_model": "default"}
        res = auth.upsert_collection_config(cid, data)
        assert res["ok"] is True
        val = auth.validate_collections()
        assert val["ok"] is True
    finally:
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


@settings(max_examples=50, deadline=None)
@given(cid=_ids)
def test_upsert_then_delete_roundtrip(cid: str) -> None:
    """Upsert then delete returns ok=True."""
    os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        data = {"id": cid, "name": "Test", "embedding_model": "default"}
        auth.upsert_collection_config(cid, data)
        assert auth.delete_collection_config(cid)["ok"] is True
    finally:
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


@settings(max_examples=50, deadline=None)
@given(cid=_ids)
def test_delete_nonexistent_returns_error(cid: str) -> None:
    """Delete unknown collection returns ok=False."""
    os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        assert auth.delete_collection_config(cid)["ok"] is False
    finally:
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


@settings(max_examples=50, deadline=None)
@given(cid=st.from_regex(r"[a-z]{1,5}\.\.[a-z]{1,5}", fullmatch=True))
def test_path_traversal_blocked(cid: str) -> None:
    """IDs containing '..' are rejected."""
    os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        data = {"id": cid, "name": "Test", "embedding_model": "default"}
        res = auth.upsert_collection_config(cid, data)
        assert res["ok"] is False
        assert "traversal" in res["error"].lower()
    finally:
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)


@settings(max_examples=50, deadline=None)
@given(cid=st.from_regex(r"/[a-z]{1,10}", fullmatch=True))
def test_absolute_path_blocked(cid: str) -> None:
    """IDs starting with '/' are rejected."""
    os.environ["KB_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        auth = KBAuthoring(tempfile.mkdtemp())
        data = {"id": cid, "name": "Test", "embedding_model": "default"}
        res = auth.upsert_collection_config(cid, data)
        assert res["ok"] is False
        assert "absolute" in res["error"].lower() or "path" in res["error"].lower()
    finally:
        os.environ.pop("KB_ENABLE_AUTHORING_TOOLS", None)
