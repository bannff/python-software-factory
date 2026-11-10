"""Scaffolded .env must carry the keys runtime actually reads (#378)."""
from __future__ import annotations

from factory.foreman.scaffold_make import generate_env_example


def _keys(bricks: list[str]) -> set[str]:
    lines = generate_env_example("demo", ["api"], bricks).splitlines()
    return {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}


def test_graph_and_memory_emit_the_backend_keys_runtime_reads() -> None:
    keys = _keys(["graph", "memory", "cache", "kb", "events"])
    assert {"GRAPH_BACKEND", "MEMORY_BACKEND", "CACHE_BACKEND", "KB_BACKEND", "EVENTS_BACKEND"} <= keys


def test_inert_adapter_keys_are_not_scaffolded_for_get_infra_bricks() -> None:
    keys = _keys(["graph", "memory", "cache", "kb", "events"])
    inert = {f"FACTORY_{b}_ADAPTER" for b in ("GRAPH", "MEMORY", "CACHE", "KB", "EVENTS")}
    assert not inert & keys
