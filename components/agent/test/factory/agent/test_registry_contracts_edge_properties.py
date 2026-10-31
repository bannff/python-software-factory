"""Supplementary property tests for registry_contracts (bd uffq verify).

QA gaps beyond the implementer's 8 properties:
- E1 JSON round-trip (``model_dump_json`` -> ``model_validate_json``)
- E2 Concurrent contract construction (no shared mutable state)
- E3 ``CustomNodeRef.config`` alias='class' round-trips with by_alias
- E4 ``_LazyRegistry`` concurrent ``__getitem__`` resolves
- E5 Union TypeAdapter preserves discriminator across dump/validate
- E6 Empty / nested-node boundary inputs
"""
from __future__ import annotations

import json
import string
import threading

from hypothesis import given, settings, strategies as st
from pydantic import TypeAdapter, ValidationError
import pytest

from factory.agent.registry.factories import (
    FACTORY_REGISTRY, known_factories,
)
from factory.agent.runtime.registry_contracts import (
    AgentNodeRef, CustomNodeRef, GraphConfig, NodeRef,
    RegistryConfig, SwarmAgentConfig, SwarmConfig, WorkflowConfig,
)

_ids = st.text(alphabet=string.ascii_lowercase + string.digits + "-_",
               min_size=1, max_size=20).filter(bool)
_models = st.sampled_from(["us.anthropic.claude-sonnet-4-6",
                           "openai.gpt-oss-120b-1:0"])
_known = st.sampled_from(list(known_factories()))

_NODE_ADAPTER: TypeAdapter[NodeRef] = TypeAdapter(NodeRef)
_REG_ADAPTER: TypeAdapter[RegistryConfig] = TypeAdapter(RegistryConfig)


# --- E1: JSON round-trip ---

@settings(max_examples=50, deadline=None)
@given(gid=_ids, name=_ids)
def test_e1_graph_json_roundtrip(gid: str, name: str) -> None:
    g = GraphConfig(id=gid, name=name)
    assert GraphConfig.model_validate_json(g.model_dump_json()) == g


@settings(max_examples=50, deadline=None)
@given(wid=_ids, name=_ids, fkey=_known)
def test_e1_workflow_json_roundtrip(
    wid: str, name: str, fkey: str,
) -> None:
    w = WorkflowConfig(id=wid, kind="workflow", factory=fkey, name=name)
    assert WorkflowConfig.model_validate_json(w.model_dump_json()) == w


@settings(max_examples=50, deadline=None)
@given(sid=_ids, name=_ids, ep=_ids, model=_models)
def test_e1_swarm_json_roundtrip(
    sid: str, name: str, ep: str, model: str,
) -> None:
    sw = SwarmConfig(
        id=sid, name=name, entry_point=ep,
        agents=[SwarmAgentConfig(id=ep, model=model, system_prompt="hi")],
    )
    assert SwarmConfig.model_validate_json(sw.model_dump_json()) == sw


# --- E2: Concurrent construction (no shared mutable state) ---

def test_e2_concurrent_construction_isolated() -> None:
    """20 threads × 50 constructions each. No thread bleed."""
    fkey = next(iter(known_factories()))
    results: list[WorkflowConfig] = []
    lock = threading.Lock()

    def _build(i: int) -> None:
        for j in range(50):
            w = WorkflowConfig(
                id=f"w-{i}-{j}", kind="workflow",
                factory=fkey, name=f"n-{i}-{j}",
            )
            with lock:
                results.append(w)

    threads = [threading.Thread(target=_build, args=(i,))
               for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({w.id for w in results}) == 1000


# --- E3: CustomNodeRef alias=`class` ---

def test_e3_custom_node_ref_alias_dump() -> None:
    n = CustomNodeRef(id="n", type="custom",
                      **{"class": "MyClass", "config": {"x": 1}})
    aliased = n.model_dump(by_alias=True)
    assert aliased["class"] == "MyClass" and "class_name" not in aliased
    plain = n.model_dump()
    assert plain["class_name"] == "MyClass"


def test_e3_custom_node_ref_alias_via_adapter() -> None:
    n = CustomNodeRef(id="n", type="custom",
                      **{"class": "Plug", "config": {}})
    dumped = _NODE_ADAPTER.dump_python(n, by_alias=True)
    assert _NODE_ADAPTER.validate_python(dumped) == n


@settings(max_examples=50, deadline=None)
@given(nid=_ids, cls=st.text(alphabet=string.ascii_letters,
                             min_size=1, max_size=20))
def test_e3_custom_node_json_alias_property(
    nid: str, cls: str,
) -> None:
    n = CustomNodeRef(id=nid, type="custom", **{"class": cls})
    parsed = json.loads(n.model_dump_json(by_alias=True))
    assert parsed["class"] == cls
    assert CustomNodeRef.model_validate(parsed) == n


# --- E4: _LazyRegistry concurrent resolution ---

def test_e4_lazy_registry_concurrent_resolve() -> None:
    """20 threads × 100 lookups. get_factory is idempotent + safe."""
    errors: list[Exception] = []
    barrier = threading.Barrier(20)

    def _hammer() -> None:
        try:
            barrier.wait()
            for _ in range(100):
                fn = FACTORY_REGISTRY["sast_targeted"]
                assert callable(fn)
                assert isinstance(fn({"vuln_class": "idor"}), list)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_hammer) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors


# --- E5: Union TypeAdapter preserves discriminator ---

@settings(max_examples=50, deadline=None)
@given(gid=_ids, name=_ids)
def test_e5_union_preserves_kind_graph(gid: str, name: str) -> None:
    g = GraphConfig(id=gid, name=name)
    revived = _REG_ADAPTER.validate_python(
        _REG_ADAPTER.dump_python(g, by_alias=True))
    assert isinstance(revived, GraphConfig) and revived.kind == "graph"


@settings(max_examples=50, deadline=None)
@given(wid=_ids, name=_ids, fkey=_known)
def test_e5_union_preserves_kind_workflow(
    wid: str, name: str, fkey: str,
) -> None:
    w = WorkflowConfig(id=wid, kind="workflow", factory=fkey, name=name)
    revived = _REG_ADAPTER.validate_python(
        _REG_ADAPTER.dump_python(w, by_alias=True))
    assert isinstance(revived, WorkflowConfig)
    assert revived.kind == "workflow"


# --- E6: Empty / nested-node boundaries ---

def test_e6_graph_empty_collections_valid() -> None:
    g = GraphConfig(id="g", name="n")
    assert g.nodes == [] and g.edges == [] and g.entry_points == []
    assert g.tool_allowlist is None


def test_e6_graph_with_nested_node_ref_validates() -> None:
    g = GraphConfig(
        id="g", name="n",
        nodes=[AgentNodeRef(id="a1", type="agent",
                            agent_id="x", context={"k": "v"})],
    )
    revived = GraphConfig.model_validate_json(g.model_dump_json())
    assert isinstance(revived.nodes[0], AgentNodeRef)
    assert revived.nodes[0].context == {"k": "v"}


def test_e6_workflow_unknown_factory_via_validator() -> None:
    with pytest.raises(ValidationError) as ei:
        WorkflowConfig(id="w", kind="workflow",
                       factory="zzz_not_real", name="n")
    assert "factory" in str(ei.value).lower()
